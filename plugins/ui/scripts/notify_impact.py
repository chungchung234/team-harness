#!/usr/bin/env python3
"""notify_impact — main에 push가 들어오면(CI) 바뀐 문서를 전제로 삼은 **다른 저장소의 문서**를 찾아, 그 문서의 Jira 티켓에 댓글을 단다.
감지는 서버(push)가 하고, 사람은 Jira가 부른다 — 누군가 세션을 열 때까지 기다리지 않는다.

    # Bitbucket Pipelines (branches: main) — 저장소 변수 JIRA_EMAIL·JIRA_TOKEN·HARNESS_TOKEN
    python3 .harness/plugins/core/scripts/notify_impact.py --ci
    # 로컬 시험 — 옆 폴더에 다른 저장소가 받아져 있을 때
    python3 notify_impact.py --repo ../product --siblings .. --range HEAD~1..HEAD --dry-run

- 바뀐 문서 = 범위(기본 push 직전..HEAD)의 docs/ 변경 중 ID 패턴(POL-01, SPEC-04 …)을 가진 파일.
- 하류 문서 = 다른 저장소 docs/ 의 프론트매터 `related`에 `<이 저장소>/<ID>`를 가진 문서. CI에서는 repos.json의 저장소들을 `docs/`만 sparse clone 해서 본다(HARNESS_TOKEN, 읽기).
- 티켓 = 하류 문서 프론트매터 `issues: [KEY-N]`. 있으면 댓글 한 건(문서마다, 같은 push에서 한 번). 없으면 알릴 곳이 없다 — 그 저장소의 다음 세션이 `[영향]`으로 안다(기존 경로).
- 댓글은 `issue.py comment`(에이전트 표식 붙음). Jira가 담당자·워처에게 알린다. 에이전트는 이 댓글에 자동 반응하지 않는다.
- 같은 커밋에 대해 두 번 달지 않도록 댓글 본문에 커밋 해시를 넣고, 쓰기 전에 최근 댓글을 읽어 같은 해시가 있으면 건너뛴다(--dry-run·--no-dedupe면 생략).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402 — work/tokens.txt → 환경변수(없는 것만)
creds.load()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "repos.json").read_text(encoding="utf-8"))
ID_RE = re.compile(r"^([A-Z]{2,5}-\d+)")


def git(repo: Path, *args):
    r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def changed_ids(repo: Path, rng: str):
    code, out, _ = git(repo, "diff", "--name-status", rng, "--", "docs")
    if code != 0:
        code, out, _ = git(repo, "show", "--name-status", "--format=", "HEAD", "--", "docs")
    ids = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        path = parts[-1]
        if path.endswith("INDEX.md"):
            continue
        m = ID_RE.match(Path(path).stem)
        if m:
            ids[m.group(1)] = (parts[0][0], path)
    return ids


def frontmatter(p: Path) -> dict:
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {}
    if not txt.startswith("---"):
        return {}
    end = txt.find("\n---", 3)
    fm = {}
    for line in txt[3:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm


def list_items(v: str):
    return [x.strip().strip("'\"") for x in v.strip("[]").split(",") if x.strip()]


def downstream(sib_docs: Path, upstream: str, ids: set):
    hits = []
    for f in sib_docs.rglob("*.md"):
        fm = frontmatter(f)
        rel = list_items(fm.get("related", ""))
        hit_ids = [i for i in ids if f"{upstream}/{i}" in rel]
        if hit_ids:
            hits.append((f, fm.get("id") or f.stem, hit_ids, list_items(fm.get("issues", ""))))
    return hits


def sparse_docs(name: str, into: Path) -> Path | None:
    base = CFG.get("base", "").rstrip("/") + "/"
    tok = os.environ.get("HARNESS_TOKEN", "")
    url = base + name + ".git"
    if tok and url.startswith("https://"):
        url = url.replace("https://", f"https://x-token-auth:{tok}@", 1)
    dst = into / name
    r = subprocess.run(["git", "clone", "--quiet", "--depth", "1", "--filter=blob:none", "--sparse", url, str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    subprocess.run(["git", "-C", str(dst), "sparse-checkout", "set", "docs"], capture_output=True)
    return dst


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", default=".", help="push가 들어온(바뀐) 저장소 — 기본 현재 폴더")
    ap.add_argument("--siblings", help="다른 저장소들이 받아져 있는 부모 폴더(로컬 시험). 없으면 --ci처럼 clone")
    ap.add_argument("--ci", action="store_true", help="Pipelines: repos.json의 저장소들을 docs/만 clone해서 본다")
    ap.add_argument("--range", default=None, help="바뀐 범위. 기본: Pipelines면 BITBUCKET_COMMIT 직전..HEAD, 아니면 HEAD~1..HEAD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-dedupe", action="store_true")
    a = ap.parse_args()

    repo = Path(a.repo).resolve()
    me = repo.name
    try:
        hj = json.loads((repo / ".claude" / "harness.json").read_text(encoding="utf-8"))
        me = hj.get("repo") or me
    except Exception:
        pass
    rng = a.range or "HEAD~1..HEAD"
    ids = changed_ids(repo, rng)
    if not ids:
        print(f"{me}: 바뀐 문서 없음 ({rng})"); return 0
    code, subj, _ = git(repo, "log", "-1", "--format=%h %s")
    print(f"{me}: 바뀐 문서 {len(ids)} — " + " ".join(f"{k}({v[0]})" for k, v in ids.items()) + f"  [{subj}]")

    names = [n for n in CFG.get("reads", {}).keys() if n not in (me, "harness", "memo")] or [n for n in ("product", "backend", "agent", "frontend", "ui", "infra") if n != me]
    tmp = None
    sib_root: Path
    if a.siblings:
        sib_root = Path(a.siblings).resolve()
    else:
        tmp = tempfile.mkdtemp(prefix="ni-")
        sib_root = Path(tmp)
        for n in names:
            if sparse_docs(n, sib_root) is None:
                print(f"  {n}: 받지 못함(없거나 권한) — 건너뜀")

    planned = []
    for n in names:
        d = sib_root / n / "docs"
        if not d.is_dir():
            continue
        for f, did, hit_ids, issues in downstream(d, me, set(ids)):
            what = ", ".join(f"{me}/{i}" for i in hit_ids)
            if not issues:
                print(f"  {n}/{did} ← {what}  (티켓 없음 — 그 저장소의 다음 세션이 [영향]으로 안다)")
                continue
            for key in issues:
                text = f"{what} 바뀜 [{subj}] — {n}/{did}의 전제. 반영 전에 바뀐 문서를 연다 (하네스 자동 알림)"
                planned.append((key, text, n, did))

    if not planned:
        print("  알릴 티켓 없음"); return 0
    rc = 0
    short = subj.split()[0] if subj else ""
    for key, text, n, did in planned:
        if not a.dry_run and not a.no_dedupe and short:
            r = subprocess.run([sys.executable, str(HERE / "issue.py"), "comments", key], capture_output=True, text=True, encoding="utf-8", env=os.environ)
            if f"[{short}" in (r.stdout or ""):
                print(f"  {key}: 같은 커밋 알림이 이미 있다 — 건너뜀"); continue
        cmd = [sys.executable, str(HERE / "issue.py"), "comment", key, text] + (["--dry-run"] if a.dry_run else [])
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=os.environ)
        ok = r.returncode == 0
        print(f"  {key} ← {n}/{did}: {'댓글' if ok else '실패 ' + (r.stderr.strip()[-120:] or r.stdout.strip()[-120:])}" + (" (dry-run)" if a.dry_run else ""))
        if r.returncode == 3:
            print("  Jira 토큰 없음 — 알림 못 함. 세션 피드 [영향]만 남는다"); return 3
        rc = rc or (0 if ok else 1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
