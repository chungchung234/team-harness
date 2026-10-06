#!/usr/bin/env python3
"""prompt_check — UserPromptSubmit 훅. 사람이 말을 걸 때마다(기본 45초에 한 번) 원격을 확인해, **이 세션이 열린 뒤** 저장소에 들어온 것을 `[지금]` 한 줄로 컨텍스트에 넣는다.

세션 시작 피드(session_start.py)가 "지난 세션 이후"라면 이것은 "방금"이다 — 대화는 다음 날이 아니라 **다음 말에** 안다.
- 자기 저장소: 깨끗한 main이면 당기고(ff-only), 작업 중이면 당기지 않고 "origin에 새 커밋 n"만 알린다.
- 읽는 저장소(settings.json additionalDirectories): 당기고 목차를 다시 만든다.
- 한 번 알린 커밋은 다시 알리지 않는다(상태 파일 `announced`). 세션 시작 피드의 기준점(`heads`)도 당긴 저장소에 대해 갱신한다 — 다음 세션이 같은 것을 또 말하지 않게.
- 원격이 없거나 오프라인이면 조용히 끝난다. 첫 fetch가 실패하면 나머지도 건너뛴다(오프라인에서 저장소마다 기다리지 않게).
- 간격은 HARNESS_CHECK_INTERVAL(초). 비용: 45초에 한 번 `git fetch` 한 번씩 — LAN에서 저장소당 1초 안팎.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

try:
    data = json.load(sys.stdin) if not sys.stdin.isatty() else {}
except Exception:
    data = {}
root = Path(data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
if not ((root / ".claude" / "harness.json").exists() or (root / "docs").is_dir()):
    sys.exit(0)
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)
SCRIPTS = PLUGIN_ROOT / "scripts"
STATE = root / ".claude" / "harness-state.json"
INTERVAL = int(os.environ.get("HARNESS_CHECK_INTERVAL", "45"))
DECISION_LOG = "docs/decisions/결정-기록.md"
ROW = re.compile(r"^\+\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.*?)\|(.*?)\|")


def git(repo: Path, *args, timeout=12):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except Exception:
        pass


def is_raw(repo: Path) -> bool:
    try:
        return bool(json.loads((repo / ".claude" / "harness.json").read_text(encoding="utf-8")).get("raw"))
    except Exception:
        return False


def remote_head(repo: Path):
    for br in ("main", "master"):
        code, out = git(repo, "rev-parse", f"origin/{br}")
        if code == 0 and re.fullmatch(r"[0-9a-f]{40}", out):
            return out, br
    return None, None


def local_head(repo: Path):
    code, out = git(repo, "rev-parse", "HEAD")
    return out if code == 0 and re.fullmatch(r"[0-9a-f]{40}", out) else None


def clean_main(repo: Path, own: bool):
    code, out = git(repo, "status", "--porcelain", "--untracked-files=no")
    if code != 0:
        return False
    dirty = [l for l in out.splitlines() if l.strip()]
    if dirty and not own and all(l.strip().endswith("docs/INDEX.md") for l in dirty):   # 읽는 저장소의 목차는 생성물 — 되돌리고 당긴다(옛 저장소는 목차가 추적될 수 있다)
        git(repo, "checkout", "--", "docs/INDEX.md"); dirty = []
    if dirty:
        return False
    code, br = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    return br in ("main", "master")


def summarize(repo: Path, seen: str, new: str, raw: bool):
    """seen..new 사이의 docs·notes 변경을 한 줄로. raw(memo)는 사람 폴더의 건수만."""
    code, log = git(repo, "log", "--format=%h%x09%s", f"{seen}..{new}", "--", "docs", "notes", "people", "retro")
    commits = [l for l in log.splitlines() if l.strip()] if code == 0 else []
    if not commits:
        return None, []
    code, ns = git(repo, "diff", "--name-status", seen, new, "--", "docs", "notes", "people", "retro")
    files = [l.split("\t") for l in ns.splitlines() if "\t" in l] if code == 0 else []
    if raw:
        who = {}
        for st, *p in files:
            path = p[-1]
            if path.startswith("people/") and not path.endswith(".gitkeep"):
                who[path.split("/")[1]] = who.get(path.split("/")[1], 0) + 1
            elif path.startswith("retro/") and not path.endswith(".gitkeep"):
                who["회고"] = who.get("회고", 0) + 1
        if not who:
            return None, []
        return f"[지금] 메모 — " + " · ".join(f"{k} {v}" for k, v in who.items()) + " — 생각이지 근거가 아니다", []
    shown = []
    for st, *p in files:
        path = p[-1]
        if path.endswith("INDEX.md"):
            continue
        shown.append(f"{Path(path).stem}({st[0]})")
    line = f"[지금] {repo.name} — 방금 커밋 {len(commits)}: " + " ".join(shown[:5]) + (" …" if len(shown) > 5 else "")
    code, diff = git(repo, "diff", seen, new, "--", DECISION_LOG)
    rows = []
    if code == 0:
        for l in diff.splitlines():
            m = ROW.match(l)
            if m:
                rows.append(f"[결정] {m.group(1)[5:]} {m.group(2).strip()[:70]}")
    return line, rows + [f"{Path(p[-1])}" for st, *p in files]  # 두 번째 값: 결정 줄 + 바뀐 경로(영향 계산용)


def impact(changed_paths: list[str], upstream: str):
    """바뀐 상류 문서 ID를 related에 가진 내 docs 문서 — 전제가 바뀌었다."""
    ids = {Path(p).stem.split("-")[0] + "-" + Path(p).stem.split("-")[1] for p in changed_paths if re.match(r"^[A-Z]{2,5}-\d+", Path(p).stem)}
    if not ids or not (root / "docs").is_dir():
        return []
    hits = []
    for f in (root / "docs").rglob("*.md"):
        try:
            head_txt = f.read_text(encoding="utf-8", errors="ignore")[:1500]
        except Exception:
            continue
        m = re.search(r"^related:\s*\[(.*?)\]", head_txt, re.M)
        if not m:
            continue
        rel = m.group(1)
        for i in ids:
            if f"{upstream}/{i}" in rel:
                hits.append(f.stem)
                break
    return [f"[영향] 전제가 바뀐 내 문서 {len(hits)}: " + " · ".join(hits[:5])] if hits else []


state = load_state()
now = time.time()
if now - float(state.get("last_check", 0)) < INTERVAL:
    sys.exit(0)
state["last_check"] = now
heads = state.setdefault("heads", {})
announced = state.setdefault("announced", {})

repos = [(root, True)]
try:
    settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    for rel in settings.get("permissions", {}).get("additionalDirectories", []):
        sib = (root / rel).resolve()
        if sib.is_dir() and (sib / ".git").exists():
            repos.append((sib, False))
except Exception:
    pass

lines = []
offline = False
for repo, own in repos:
    if offline or not (repo / ".git").exists():
        continue
    code, _ = git(repo, "remote", "get-url", "origin")
    if code != 0:
        continue
    code, _ = git(repo, "fetch", "--quiet", "--no-tags", "origin")
    if code != 0:
        offline = True
        break
    rh, br = remote_head(repo)
    if not rh:
        continue
    seen = heads.get(str(repo)) or local_head(repo)
    if not seen:
        continue
    if rh == seen or announced.get(str(repo)) == rh:
        continue
    line, extra = summarize(repo, seen, rh, is_raw(repo))
    announced[str(repo)] = rh
    if not line:
        continue
    decisions = [e for e in extra if e.startswith("[결정]")]
    paths = [e for e in extra if not e.startswith("[결정]")]
    if clean_main(repo, own):
        code, _ = git(repo, "pull", "--ff-only", "--quiet", timeout=20)
        if code == 0:
            heads[str(repo)] = rh
            g = SCRIPTS / "gen_index.py"
            if g.exists() and (repo / "docs").is_dir():
                subprocess.run([sys.executable, str(g), "docs", "--write"], cwd=repo, capture_output=True)
            line += " — 받았다" if not own else ""
        else:
            line += " — origin에 있다(당기지 못함)"
    else:
        line += " — 내 작업 중이라 당기지 않았다, origin에 있다" if own else " — 작업 중인 폴더라 당기지 않았다"
    lines.append(line)
    lines += decisions[:3]
    if not own:
        lines += impact(paths, repo.name)

save_state(state)

if lines:
    q = SCRIPTS / "questions.py"
    if q.exists():
        try:
            r = subprocess.run([sys.executable, str(q), "--brief", "--repo", str(root)], capture_output=True, text=True, encoding="utf-8", timeout=20)
            if r.stdout.strip():
                lines.append(r.stdout.rstrip())
        except Exception:
            pass
    sys.stdout.write("\n".join(lines[:12]) + "\n")
