#!/usr/bin/env python3
"""issue — Jira 이슈를 만들고 키를 돌려준다. 커밋·브랜치·PR에 필요한 이슈 키를 사람이 Jira에 들어가 만들지 않게.

    python3 <플러그인>/scripts/issue.py "주문 취소 API 스펙" [--type Task] [--desc "…"] [--component backend]
    → 출력: ORD-42
    python3 <플러그인>/scripts/issue.py status ORD-41 ORD-42        # 구현 상태는 Jira가 갖는다 — 읽어 온다: `ORD-41  진행 중  주문 취소 API  (10-28)`
    python3 <플러그인>/scripts/issue.py transition ORD-41 "완료"     # 사람이 "됐다"고 한 뒤 — 수용 확인을 Jira 상태로 남긴다
    python3 <플러그인>/scripts/issue.py comment ORD-41 "[하네스] product/POL-03 바뀜 — SPEC-04 확인 필요"   # 티켓 댓글 — 질문·알림. 담당자에게 Jira 알림이 간다
    python3 <플러그인>/scripts/issue.py comments ORD-41 [--since 2026-10-01T09:00]                         # 댓글 읽기 (사람이 쓴 것과 에이전트가 쓴 것을 구분해 보인다)

- 설정: scripts/repos.json 의 jira.site·jira.project. 인증: 환경변수 JIRA_EMAIL + JIRA_TOKEN(Atlassian API 토큰).
- 토큰이 없으면 만들 수 없다고 말하고 exit 3 — 스킬은 그때만 사람에게 키를 묻는다.
- 표준 라이브러리만. Jira Cloud REST v3 (POST /rest/api/3/issue).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402 — work/tokens.txt → 환경변수(없는 것만)
creds.load()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
CFG = json.loads((Path(__file__).resolve().parent / "repos.json").read_text(encoding="utf-8")).get("jira", {})


def _auth(email, token):
    return {"Accept": "application/json", "Content-Type": "application/json",
            "Authorization": "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()}


def _req(url, headers, method="GET", payload=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8") if payload is not None else None, method=method, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def status(keys, site, email, token, dry):
    """키마다 한 줄: KEY  상태  요약  (갱신일). 읽기만 한다."""
    if dry:
        print(json.dumps({"url": f"{site}/rest/api/3/issue/{keys[0]}?fields=status,summary,updated,assignee", "keys": keys}, ensure_ascii=False)); return 0
    if not (email and token):
        print("JIRA_EMAIL·JIRA_TOKEN 환경변수가 없어 상태를 읽을 수 없다 — Jira에서 사람이 본다", file=sys.stderr); return 3
    rc = 0
    for k in keys:
        try:
            d = _req(f"{site}/rest/api/3/issue/{k}?fields=status,summary,updated,assignee", _auth(email, token))
            f = d.get("fields", {})
            who = (f.get("assignee") or {}).get("displayName", "")
            print(f"{k}  {f.get('status', {}).get('name', '?')}  {f.get('summary', '')}  ({(f.get('updated') or '')[:10]}{' · ' + who if who else ''})")
        except urllib.error.HTTPError as e:
            print(f"{k}  읽기 실패 HTTP {e.code}", file=sys.stderr); rc = 1
    return rc


def transition(key, target, site, email, token, dry):
    """이름으로 전이(대소문자·공백 무시). 사람이 말한 뒤에만 부른다."""
    if dry:
        print(json.dumps({"url": f"{site}/rest/api/3/issue/{key}/transitions", "payload": {"transition": {"name": target}}}, ensure_ascii=False)); return 0
    if not (email and token):
        print("JIRA_EMAIL·JIRA_TOKEN 환경변수가 없어 상태를 바꿀 수 없다 — Jira에서 사람이 바꾼다", file=sys.stderr); return 3
    h = _auth(email, token)
    try:
        ts = _req(f"{site}/rest/api/3/issue/{key}/transitions", h).get("transitions", [])
        norm = lambda x: re.sub(r"\s+", "", x).lower()
        hit = next((t for t in ts if norm(t.get("name", "")) == norm(target) or norm(t.get("to", {}).get("name", "")) == norm(target)), None)
        if not hit:
            print(f"{key}: '{target}'로 가는 전이가 없다 — 가능한 것: " + ", ".join(t.get("name", "") for t in ts), file=sys.stderr); return 1
        _req(f"{site}/rest/api/3/issue/{key}/transitions", h, method="POST", payload={"transition": {"id": hit["id"]}})
        print(f"{key}  → {hit.get('to', {}).get('name', target)}"); return 0
    except urllib.error.HTTPError as e:
        print(f"{key}: 전이 실패 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}", file=sys.stderr); return 1


AGENT_TAG = "[에이전트]"   # 에이전트가 쓴 댓글은 이 말로 시작한다 — 자기가 에이전트임을 밝힌다. 봇은 봇의 댓글에 반응하지 않는다(R2)


def comment(key, text, site, email, token, dry):
    """티켓에 댓글 한 건. 본문은 ADF 문단 하나. 에이전트 표식을 앞에 붙인다."""
    body = text if text.startswith(AGENT_TAG) else f"{AGENT_TAG} {text}"
    payload = {"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": body}]}]}}
    if dry:
        print(json.dumps({"url": f"{site}/rest/api/3/issue/{key}/comment", "payload": payload}, ensure_ascii=False)); return 0
    if not (email and token):
        print("JIRA_EMAIL·JIRA_TOKEN 환경변수가 없어 댓글을 쓸 수 없다 — 사람에게 말로 전한다", file=sys.stderr); return 3
    try:
        d = _req(f"{site}/rest/api/3/issue/{key}/comment", _auth(email, token), method="POST", payload=payload)
        print(f"{key}  댓글 {d.get('id', '')}"); return 0
    except urllib.error.HTTPError as e:
        print(f"{key}: 댓글 실패 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}", file=sys.stderr); return 1


def _adf_text(node) -> str:
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")
        return "".join(_adf_text(c) for c in node.get("content", [])) + ("\n" if node.get("type") == "paragraph" else "")
    if isinstance(node, list):
        return "".join(_adf_text(c) for c in node)
    return ""


def comments(key, since, site, email, token, dry):
    """댓글을 시간순으로. 줄 머리: `사람 ·`/`에이전트 ·` — 에이전트 댓글은 답할 것이 아니다."""
    url = f"{site}/rest/api/3/issue/{key}/comment?orderBy=created&maxResults=50"
    if dry:
        print(json.dumps({"url": url, "since": since}, ensure_ascii=False)); return 0
    if not (email and token):
        print("JIRA_EMAIL·JIRA_TOKEN 환경변수가 없어 댓글을 읽을 수 없다", file=sys.stderr); return 3
    try:
        d = _req(url, _auth(email, token))
    except urllib.error.HTTPError as e:
        print(f"{key}: 댓글 읽기 실패 HTTP {e.code}", file=sys.stderr); return 1
    n = 0
    for c in d.get("comments", []):
        created = (c.get("created") or "")[:16]
        if since and created < since:
            continue
        text = _adf_text(c.get("body")).strip()
        who = (c.get("author") or {}).get("displayName", "?")
        kind = "에이전트" if text.startswith(AGENT_TAG) else "사람"
        print(f"{created}  {kind} · {who}: {text[:300]}")
        n += 1
    if n == 0:
        print(f"{key}: 새 댓글 없음")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("summary", nargs="+", help='이슈 제목 — 또는 `status KEY…` / `transition KEY "<상태>"` / `comment KEY "<글>"` / `comments KEY`')
    ap.add_argument("--since", default=None, help="comments: 이 시각(YYYY-MM-DDTHH:MM) 이후만")
    ap.add_argument("--type", default="Task")
    ap.add_argument("--desc", default="")
    ap.add_argument("--component", default=None, help="저장소 이름 = Jira 컴포넌트 (기본: 현재 폴더 이름)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    site, project = CFG.get("site", "").rstrip("/"), CFG.get("project", "")
    email, token = os.environ.get("JIRA_EMAIL"), os.environ.get("JIRA_TOKEN")
    words = a.summary
    if words[0] == "status" and len(words) > 1:
        return status(words[1:], site, email, token, a.dry_run)
    if words[0] == "transition" and len(words) > 2:
        return transition(words[1], " ".join(words[2:]), site, email, token, a.dry_run)
    if words[0] == "comment" and len(words) > 2:
        return comment(words[1], " ".join(words[2:]), site, email, token, a.dry_run)
    if words[0] == "comments" and len(words) > 1:
        return comments(words[1], a.since, site, email, token, a.dry_run)
    a.summary = " ".join(words)
    comp = a.component or Path.cwd().resolve().name
    payload = {"fields": {"project": {"key": project}, "summary": a.summary, "issuetype": {"name": a.type},
               "components": [{"name": comp}],
               "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": a.desc or a.summary}]}]}}}
    if a.dry_run:
        print(json.dumps({"url": f"{site}/rest/api/3/issue", "payload": payload}, ensure_ascii=False, indent=2)); return 0
    if not (site and project) or "CHANGE-ME" in site or project == "KEY":
        print("Jira 설정이 없다 (scripts/repos.json의 jira.site·jira.project) — 문서 총괄이 채운다", file=sys.stderr); return 3
    if not (email and token):
        print("JIRA_EMAIL·JIRA_TOKEN 환경변수가 없어 이슈를 만들 수 없다 — 사람에게 이슈 키를 묻는다", file=sys.stderr); return 3
    req = urllib.request.Request(f"{site}/rest/api/3/issue", data=json.dumps(payload).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "Accept": "application/json",
                                          "Authorization": "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(json.loads(resp.read().decode("utf-8"))["key"]); return 0
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if "components" in body:  # 컴포넌트가 없으면 빼고 한 번 더
            del payload["fields"]["components"]
            req.data = json.dumps(payload).encode("utf-8")
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    print(json.loads(resp.read().decode("utf-8"))["key"]); return 0
            except urllib.error.HTTPError as e2:
                body = e2.read().decode("utf-8", "replace")[:300]
        print(f"이슈 생성 실패 HTTP {e.code}: {body}", file=sys.stderr); return 1


if __name__ == "__main__":
    sys.exit(main())
