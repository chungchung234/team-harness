#!/usr/bin/env python3
"""pr — 현재 브랜치를 푸시하고 Bitbucket PR을 만든다. 스킬이 마지막에 부르는 한 줄. 사람은 git을 만지지 않는다.
       그리고 소유자 쪽: 내 저장소에 열린 PR을 보고, 대화에서 "승인"하면 그 사람의 자격증명으로 승인·머지한다 — Bitbucket 웹에 들어가지 않아도 된다.

    python3 <플러그인>/scripts/pr.py "SSY-12 Q-03 이탈 임계" --body "질문 한 문장…" [--repo ../product] [--dest main] [--dry-run]
    python3 <플러그인>/scripts/pr.py inbox [--brief]          # 이 저장소에 열린 PR (번호·제목·작성자)
    python3 <플러그인>/scripts/pr.py show 12                  # PR 하나의 설명·바뀐 파일 목록 (에이전트가 이걸 읽고 사람 말로 요약한다)
    python3 <플러그인>/scripts/pr.py merge 12 [--comment "…"] # 승인 + 머지. 사람이 대화에서 "승인"이라고 한 뒤에만. 코멘트에 승인 근거를 남긴다

- 승인·머지는 **그 사람의** 자격증명(개인 API 토큰 BITBUCKET_API_TOKEN — 앱 비밀번호는 2026-06-09에 폐지됐다)이어야 Bitbucket에 그 사람이 머지한 것으로 남고 owners 그룹 제한을 통과한다.
  저장소 액세스 토큰(BITBUCKET_TOKEN)은 PR 생성엔 되지만 머지 주체가 사람이 아니게 되므로 merge에는 쓰지 않는다(거부).

- 토큰: BITBUCKET_API_TOKEN(사람의 Atlassian API 토큰 — Bitbucket 범위, Bearer) · BITBUCKET_TOKEN(저장소 액세스 토큰, CI·하네스 담당, Bearer) · (옛) BITBUCKET_USER + BITBUCKET_APP_PASSWORD(Basic — 2026-06-09 이후 동작 안 함).
  둘 다 없으면 푸시만 하고 **PR을 만드는 웹 주소를 출력**한다 — 사람이 그 링크를 눌러 만든다(브라우저 한 번).
- 제목에 이슈 키가 없으면 멈춘다(저장소 설정이 거부하는 것과 같은 규칙).
- 원격 URL에서 workspace/slug를 읽는다 (https·ssh 둘 다). 
- 푸시 전에 origin/<dest> 위로 rebase한다(충돌이면 멈추고 파일을 알린다). 생성물(docs/INDEX.md)은 커밋되지 않으므로 충돌 원인이 아니다.
- 표준 라이브러리만 쓴다 (urllib). Python 3.9+.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402 — work/tokens.txt → 환경변수(없는 것만)
creds.load()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
KEY = re.compile(r"\b[A-Z][A-Z0-9]+-[0-9]+\b")


def git(repo: Path, *args: str, check=True) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} 실패:\n{r.stderr.strip()}")
    return r.stdout.strip()


def parse_remote(url: str):
    m = re.search(r"bitbucket\.org[:/]([^/]+)/([^/.]+?)(?:\.git)?/?$", url)
    return (m.group(1), m.group(2)) if m else (None, None)


def api(method: str, path: str, payload, *, user_only=False):
    """Bitbucket API 호출. 자격증명이 없으면 None. user_only면 사람 자격증명만 받는다."""
    tok, user, pw = os.environ.get("BITBUCKET_API_TOKEN") or os.environ.get("BITBUCKET_TOKEN"), os.environ.get("BITBUCKET_USER"), os.environ.get("BITBUCKET_APP_PASSWORD")
    if os.environ.get("BITBUCKET_API_TOKEN"):
        user = pw = None   # 개인 API 토큰이 있으면 그것으로(Bearer) — 사람 이름으로 남는다
    req = urllib.request.Request("https://api.bitbucket.org/2.0" + path, data=json.dumps(payload).encode("utf-8") if payload is not None else None,
                                 method=method, headers={"Content-Type": "application/json", "Accept": "application/json"})
    if user and pw:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
    elif tok and (not user_only or os.environ.get("BITBUCKET_API_TOKEN")):   # 개인 API 토큰은 사람의 것 — 승인·머지에 쓸 수 있다
        req.add_header("Authorization", f"Bearer {tok}")
    else:
        return None
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} 실패 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def repo_ids(repo: Path):
    ws, slug = parse_remote(git(repo, "remote", "get-url", "origin"))
    if not ws:
        sys.exit("origin이 Bitbucket이 아니다")
    return ws, slug


def cmd_inbox(repo: Path, brief: bool, dry: bool) -> int:
    ws, slug = repo_ids(repo)
    path = f"/repositories/{ws}/{slug}/pullrequests?state=OPEN&pagelen=20"
    if dry:
        print("GET", path); return 0
    res = api("GET", path, None)
    if res is None:
        if not brief:
            print("자격증명이 없어 PR 목록을 못 본다 — Bitbucket 웹에서 본다")
        return 0
    prs = res.get("values", [])
    if brief:
        if prs:
            print(f"[pr] 이 저장소에 열린 PR {len(prs)}건 — 소유자면 /approve 로 본다: " + ", ".join(f"#{x['id']} {x['title']}" for x in prs[:8]))
        return 0
    for x in prs:
        print(f"#{x['id']:<4} {x['title']}  ← {x.get('author', {}).get('display_name', '?')}  ({x['source']['branch']['name']} → {x['destination']['branch']['name']})")
    if not prs:
        print("열린 PR 없음")
    return 0


def cmd_show(repo: Path, pr_id: str, dry: bool) -> int:
    ws, slug = repo_ids(repo)
    base = f"/repositories/{ws}/{slug}/pullrequests/{pr_id}"
    if dry:
        print("GET", base); print("GET", base + "/diffstat"); return 0
    x = api("GET", base, None)
    if x is None:
        sys.exit("자격증명이 없다 — 개인 API 토큰 BITBUCKET_API_TOKEN (`/core:init --check`로 확인)")
    stat = api("GET", base + "/diffstat", None) or {}
    print(f"#{x['id']} {x['title']}\n작성자: {x.get('author', {}).get('display_name', '?')} · {x['source']['branch']['name']} → {x['destination']['branch']['name']} · 상태 {x['state']}")
    print("설명:\n" + (x.get("description") or "(없음)"))
    print("바뀐 파일:")
    for f in stat.get("values", []):
        new = (f.get("new") or {}).get("path") or (f.get("old") or {}).get("path")
        print(f"  {str(f.get('status')):9} +{f.get('lines_added', 0)} -{f.get('lines_removed', 0)}  {new}")
    print(f"웹: {x.get('links', {}).get('html', {}).get('href', '')}")
    return 0


def cmd_merge(repo: Path, pr_id: str, comment: str, dry: bool) -> int:
    ws, slug = repo_ids(repo)
    base = f"/repositories/{ws}/{slug}/pullrequests/{pr_id}"
    body = {"type": "pullrequest_merge", "merge_strategy": "merge_commit", "close_source_branch": True}
    if dry:
        print("POST", base + "/comments", json.dumps({"content": {"raw": comment}}, ensure_ascii=False) if comment else "(코멘트 없음)")
        print("POST", base + "/approve"); print("POST", base + "/merge", json.dumps(body)); return 0
    if not (os.environ.get("BITBUCKET_API_TOKEN") or (os.environ.get("BITBUCKET_USER") and os.environ.get("BITBUCKET_APP_PASSWORD"))):
        sys.exit("승인·머지는 사람의 자격증명(개인 API 토큰 BITBUCKET_API_TOKEN)으로만 한다 — 저장소 토큰으로는 하지 않는다. 없으면 웹에서 버튼을 누른다: " + f"https://bitbucket.org/{ws}/{slug}/pull-requests/{pr_id}")
    if comment:
        api("POST", base + "/comments", {"content": {"raw": comment}}, user_only=True)
    api("POST", base + "/approve", None, user_only=True)
    res = api("POST", base + "/merge", body, user_only=True) or {}
    print(f"머지됨 #{pr_id} → {res.get('destination', {}).get('branch', {}).get('name', 'main')}. 다른 사람은 다음 세션에 훅이 당겨서 본다")
    return 0


def create_pr(ws: str, slug: str, payload: dict) -> dict:
    req = urllib.request.Request(f"https://api.bitbucket.org/2.0/repositories/{ws}/{slug}/pullrequests",
                                 data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    tok, user, pw = os.environ.get("BITBUCKET_API_TOKEN") or os.environ.get("BITBUCKET_TOKEN"), os.environ.get("BITBUCKET_USER"), os.environ.get("BITBUCKET_APP_PASSWORD")
    if os.environ.get("BITBUCKET_API_TOKEN"):
        user = pw = None   # 개인 API 토큰이 있으면 그것으로(Bearer) — 사람 이름으로 남는다
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    elif user and pw:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode())
    else:
        return {}
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        sys.exit(f"PR 생성 실패 HTTP {e.code}: {body}\n→ 토큰 권한(pullrequest:write)·대상 브랜치·이미 열린 PR을 확인한다")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("inbox", "show", "merge"):
        sp = argparse.ArgumentParser(); sp.add_argument("cmd"); sp.add_argument("pr_id", nargs="?"); sp.add_argument("--repo", default=".")
        sp.add_argument("--brief", action="store_true"); sp.add_argument("--comment", default=""); sp.add_argument("--dry-run", action="store_true")
        a = sp.parse_args(); repo = Path(a.repo).resolve()
        if a.cmd == "inbox":
            return cmd_inbox(repo, a.brief, a.dry_run)
        if not a.pr_id:
            sys.exit("PR 번호가 필요하다")
        return cmd_show(repo, a.pr_id, a.dry_run) if a.cmd == "show" else cmd_merge(repo, a.pr_id, a.comment, a.dry_run)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("title")
    ap.add_argument("--body", default="")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--dest", default=None, help="대상 브랜치 (기본: origin의 HEAD, 없으면 main)")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--direct", action="store_true", help="PR 없이 main에 바로 push. main에 있어야 하고 rebase 후 push한다")
    ap.add_argument("--dry-run", action="store_true", help="푸시·API 호출 없이 무엇을 할지 출력")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    if not KEY.search(a.title):
        sys.exit("PR 제목에 Jira 이슈 키가 없다 (예: `SSY-12 …`). 커밋과 같은 규칙이다.")
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if a.direct:
        if branch not in ("main", "master"):
            sys.exit(f"--direct는 main에서만 쓴다 (지금 {branch})")
        if a.dry_run:
            print(json.dumps({"direct": True, "branch": branch, "steps": ["fetch", "rebase origin/" + branch, "push"]}, ensure_ascii=False)); return 0
        git(repo, "fetch", "--quiet", "origin", branch)
        rb = subprocess.run(["git", "rebase", f"origin/{branch}"], cwd=repo, capture_output=True, text=True, encoding="utf-8")
        if rb.returncode != 0:
            conflicted = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=repo, capture_output=True, text=True).stdout.split()
            subprocess.run(["git", "rebase", "--abort"], cwd=repo, capture_output=True)
            sys.exit("다른 사람이 먼저 고친 것과 충돌: " + ", ".join(conflicted or ["?"]) + "\n→ 에이전트가 상대의 변경을 설명하고 사람이 정한 뒤 다시 반영한다. 안 되면 하네스 담당에게.")
        git(repo, "push", "origin", branch)
        print(f"main에 직접 반영했다 ({a.title}). PR 없음 — 이 저장소의 정책이다. 다른 사람은 다음 세션에 훅이 당겨서 본다")
        return 0
    if branch in ("main", "master"):
        sys.exit(f"{branch}에서 PR을 만들 수 없다 — feature/KEY-123-설명 브랜치를 먼저 만든다 (PR 없는 저장소면 --direct)")
    remote = git(repo, "remote", "get-url", "origin")
    ws, slug = parse_remote(remote)  # Bitbucket이 아니면(로컬 시험 등) 푸시까지만 하고 PR은 만들지 않는다
    dest = a.dest
    if not dest:
        head = git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", check=False)
        dest = head.rsplit("/", 1)[-1] if head else "main"
    payload = {"title": a.title, "description": a.body, "source": {"branch": {"name": branch}},
               "destination": {"branch": {"name": dest}}, "close_source_branch": True}
    web_new = f"https://bitbucket.org/{ws}/{slug}/pull-requests/new?source={branch}&dest={dest}&t=1" if ws else None
    if a.dry_run:
        print(json.dumps({"repo": f"{ws}/{slug}" if ws else remote, "push": not a.no_push, "payload": payload, "fallback_url": web_new}, ensure_ascii=False, indent=2))
        return 0
    if not a.no_push:
        # 먼저 대상 브랜치 위로 올려 놓는다 — 머지 버튼에서 충돌이 나면 비개발자가 풀 수 없다
        git(repo, "fetch", "--quiet", "origin", dest)
        rb = subprocess.run(["git", "rebase", f"origin/{dest}"], cwd=repo, capture_output=True, text=True, encoding="utf-8")
        if rb.returncode != 0:
            conflicted = subprocess.run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=repo, capture_output=True, text=True).stdout.split()
            subprocess.run(["git", "rebase", "--abort"], cwd=repo, capture_output=True)
            sys.exit("origin/" + dest + " 위로 올리다 충돌: " + ", ".join(conflicted or ["?"]) + "\n→ 그 파일을 main 기준으로 다시 반영하고(백로그처럼 같은 절을 둘이 고친 경우) 다시 pr.py. 안 되면 하네스 담당에게.")
        git(repo, "push", "--force-with-lease", "-u", "origin", branch)
    if not ws:
        print(f"푸시했다. origin이 Bitbucket이 아니라 PR은 만들지 않았다: {remote}")
        return 0
    res = create_pr(ws, slug, payload)
    if not res:
        print(f"푸시했다. 토큰이 없어 PR은 사람이 만든다 — 이 링크를 열면 제목·브랜치가 채워져 있다:\n{web_new}")
        return 0
    url = (res.get("links") or {}).get("html", {}).get("href", "?")
    print(f"PR #{res.get('id')} 생성: {url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
