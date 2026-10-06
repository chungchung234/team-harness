#!/usr/bin/env python3
"""remote — 문서 총괄의 에이전트가 Bitbucket 저장소를 만들고 기본 설정을 건다. 사람이 웹에서 일곱 번 클릭하지 않게.

    python3 remote.py create backend [product …]     # 비공개 저장소 생성 (+ 기본 브랜치 main)
    python3 remote.py setup  backend --owners backend-owners   # Pipelines + main 보호: 직접 push 금지, 머지는 소유자 그룹만, 승인 1·빌드 1(권고)
    python3 remote.py --dry-run create backend        # 호출할 API와 페이로드만 출력

- 인증: BITBUCKET_TOKEN (워크스페이스 액세스 토큰, repository:admin) 또는 BITBUCKET_USER + BITBUCKET_APP_PASSWORD.
- 워크스페이스는 remotes.json의 base에서 읽는다.
- ⚠️ 이 킷을 만들 때 Bitbucket에 접근할 수 없어 실호출은 미검증. "Require issue keys in commit messages"는 API가 없어 웹에서 한 번 켠다 (SETUP 4a).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "remotes.json").read_text(encoding="utf-8"))
WS = re.search(r"bitbucket\.org/([^/]+)/?", CFG["base"]).group(1)
API = "https://api.bitbucket.org/2.0"


def auth_header():
    tok, user, pw = os.environ.get("BITBUCKET_TOKEN"), os.environ.get("BITBUCKET_USER"), os.environ.get("BITBUCKET_APP_PASSWORD")
    if tok:
        return f"Bearer {tok}"
    if user and pw:
        return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
    sys.exit("BITBUCKET_TOKEN 또는 BITBUCKET_USER+BITBUCKET_APP_PASSWORD 가 필요하다 (워크스페이스 관리자 권한)")


def call(method, path, payload, dry):
    if dry:
        print(method, API + path); print(json.dumps(payload, ensure_ascii=False, indent=2)); return {}
    req = urllib.request.Request(API + path, data=json.dumps(payload).encode() if payload is not None else None, method=method,
                                 headers={"Content-Type": "application/json", "Authorization": auth_header()})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} 실패 HTTP {e.code}: {e.read().decode('utf-8','replace')[:300]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create"); c.add_argument("repos", nargs="+")
    s = sub.add_parser("setup"); s.add_argument("repos", nargs="+"); s.add_argument("--owners", default=None, help="main에 머지할 수 있는 워크스페이스 그룹 slug (예: product-owners). 없으면 머지 제한을 걸지 않는다"); s.add_argument("--mode", choices=["pr", "direct"], default="pr", help="pr: main 직접 push 금지(기본). direct: PR 없이 push 허용 — product가 'PR 없음'을 택하면")
    a = ap.parse_args()
    for name in a.repos:
        if a.cmd == "create":
            call("POST", f"/repositories/{WS}/{name}", {"scm": "git", "is_private": True, "name": name,
                 "description": f"{name}", "fork_policy": "no_public_forks"}, a.dry_run)
            print(f"생성 {WS}/{name} (비공개). 첫 push가 main을 만든다")
        else:
            call("PUT", f"/repositories/{WS}/{name}/pipelines_config", {"enabled": True}, a.dry_run)
            main_ = {"branch_match_kind": "glob", "pattern": "main"}
            # 직접 push 금지(아무도) · 히스토리 재작성·삭제 금지 — 에이전트는 PR로만 main에 닿는다
            if a.mode == "pr":
                call("POST", f"/repositories/{WS}/{name}/branch-restrictions", {"kind": "push", "users": [], "groups": [], **main_}, a.dry_run)
            call("POST", f"/repositories/{WS}/{name}/branch-restrictions", {"kind": "force", **main_}, a.dry_run)
            call("POST", f"/repositories/{WS}/{name}/branch-restrictions", {"kind": "delete", **main_}, a.dry_run)
            if a.owners:  # 머지는 소유자 그룹만 — Premium 없이도 "소유자가 승인한다"가 강제된다
                call("POST", f"/repositories/{WS}/{name}/branch-restrictions", {"kind": "restrict_merges", "users": [], "groups": [{"slug": a.owners, "owner": {"username": WS}}], **main_}, a.dry_run)
            call("POST", f"/repositories/{WS}/{name}/branch-restrictions", {"kind": "require_approvals_to_merge", "value": 1, **main_}, a.dry_run)
            call("POST", f"/repositories/{WS}/{name}/branch-restrictions", {"kind": "require_passing_builds_to_merge", "value": 1, **main_}, a.dry_run)
            print(f"설정 {WS}/{name}: Pipelines 켬 · main {'직접 push 금지' if a.mode == 'pr' else '직접 push 허용(direct)'}·force·delete 금지 · 머지는 {a.owners or '(제한 없음 — --owners 권장)'} · 승인 1·빌드 1(권고) · 이슈 키 요구는 웹에서(SETUP 4a)")


if __name__ == "__main__":
    main()
