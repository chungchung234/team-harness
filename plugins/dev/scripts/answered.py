#!/usr/bin/env python3
"""answered — 에이전트가 사람 대신 답한 질문을 한 줄씩 남기고, 주인에게 모아 보이고, 틀렸으면 바로잡은 줄을 붙인다.

    python3 <플러그인>/scripts/answered.py add Q-01 "결제 완료 시각" --basis "POL-01 규칙 1"   # answer 스킬이 ANSWERED로 답할 때
    python3 <플러그인>/scripts/answered.py brief --mark      # 세션 시작 훅 — 주인이 아직 못 본 줄만, 보였으면 표시
    python3 <플러그인>/scripts/answered.py correct Q-01 "주문 접수 시각" --basis "기획자 확인"   # 주인이 "아니야"라고 했을 때
    python3 <플러그인>/scripts/answered.py list

왜 있나: 작은 범위의 질문은 문서를 근거로 바로 답한다(기다리게 하지 않는다). 그 대신 주인이 모르는 답이 쌓이면 안 되므로,
대신 답한 것은 여기 남고 주인이 다음에 세션을 열 때 모아서 보인다. 아무 말이 없으면 맞는 것으로 둔다.

- 기록 파일: notes/대신-답한-기록.md (목차 밖, git에 올린다, 지우거나 고치지 않는다 — 바로잡음도 새 줄).
- 근거(--basis)는 이 저장소 문서 id(POL-01 등)를 담아야 한다. 근거가 없으면 대신 답하지 않는다 — NEEDS-DECISION으로 올린다.
- 바로잡을 때는 근거로 사람의 확인을 적을 수 있다. 그 질문을 related로 가리키는 다른 저장소 문서를 함께 보여 준다(그 문서 주인에게 알린다).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from downstream import dependents, find_root, front  # noqa: E402

REL = Path("notes/대신-답한-기록.md")
HEAD = "| 날짜 | 질문 | 물은 곳 | 답 | 근거 | 상태 |\n|---|---|---|---|---|---|\n"
ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|\s*$")
DOC_ID = re.compile(r"\b(?:POL|SPEC|ADR|DSN|RS|DOC)-\d{2,3}\b")
STATE_KEY = "answered_seen"


def esc(s) -> str:
    return str(s).replace("|", "／").replace("\n", " ").strip()


def rows(f: Path) -> list[tuple[str, ...]]:
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        m = ROW.match(line)
        if m and m.group(1) != "날짜":
            out.append(tuple(x.strip() for x in m.groups()))
    return out


def ensure(repo: Path) -> Path:
    f = repo / REL
    if not f.exists():
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(
            f"# 대신 답한 기록 — {repo.name}\n\n"
            "> 에이전트가 이 저장소의 문서를 근거로 사람 대신 답한 질문. 한 줄씩 붙이고 지우지 않는다.\n"
            "> 주인이 세션을 열면 아직 못 본 줄이 보인다. 틀렸으면 \"아니야\"라고 하면 바로잡는다 — 바로잡은 것도 새 줄로.\n\n" + HEAD,
            encoding="utf-8", newline="\n")
    return f


def question(repo: Path, qid: str) -> tuple[dict, Path | None]:
    for p in sorted((repo / "docs" / "questions").glob(f"{qid}-*.md")) + sorted((repo / "docs" / "questions").glob(f"{qid}.md")):
        fm = front(p)
        if str(fm.get("id")) == qid:
            return fm, p
    return {}, None


def append(repo: Path, line: str) -> None:
    f = ensure(repo)
    body = f.read_text(encoding="utf-8")
    if line in body:
        return
    f.write_text(body + ("" if body.endswith("\n") else "\n") + line + "\n", encoding="utf-8", newline="\n")


def known_ids(repo: Path) -> set[str]:
    return {str(front(p).get("id")) for p in (repo / "docs").rglob("*.md") if p.name != "INDEX.md"}


def state(repo: Path) -> tuple[Path, dict]:
    p = repo / ".claude" / "harness-state.json"
    try:
        return p, json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return p, {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", help="저장소 경로 (기본: 현재 위치에서 위로 찾음)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a_ = sub.add_parser("add", parents=[common]); a_.add_argument("qid"); a_.add_argument("answer"); a_.add_argument("--basis", required=True)
    a_.add_argument("--date", default=dt.date.today().isoformat())
    c_ = sub.add_parser("correct", parents=[common]); c_.add_argument("qid"); c_.add_argument("answer"); c_.add_argument("--basis", default="주인 확인")
    c_.add_argument("--date", default=dt.date.today().isoformat())
    b_ = sub.add_parser("brief", parents=[common]); b_.add_argument("--mark", action="store_true"); b_.add_argument("--today", default=dt.date.today().isoformat())
    sub.add_parser("list", parents=[common])
    a = ap.parse_args()
    repo = Path(a.repo).resolve() if a.repo else find_root(Path.cwd().resolve())
    f = repo / REL

    if a.cmd in ("add", "correct"):
        fm, qp = question(repo, a.qid)
        if not qp:
            sys.exit(f"{a.qid}: 이 저장소 docs/questions/에 그런 질문이 없다")
        if a.cmd == "add":
            ids = set(DOC_ID.findall(a.basis))
            if not ids:
                sys.exit("근거에 이 저장소 문서 id(POL-01 등)가 없다 — 근거 없이 대신 답하지 않는다. 사람의 결정이 필요하면 NEEDS-DECISION으로 올린다")
            unknown = ids - known_ids(repo)
            if unknown:
                sys.exit(f"근거 {', '.join(sorted(unknown))}가 이 저장소에 없다 — 이 저장소 문서로만 대신 답한다")
        asked = str(fm.get("asked_by", "")).split("/")[0].strip() or "?"
        status = "대신 답함" if a.cmd == "add" else "바로잡음"
        line = f"| {a.date} | {esc(a.qid)} {esc(fm.get('title', ''))} | {esc(asked)} | {esc(a.answer)} | {esc(a.basis)} | {status} |"
        append(repo, line)
        print(f"{REL.as_posix()} ← {line}")
        if a.cmd == "correct":
            deps = dependents(repo, a.qid)
            print("다음: 질문 파일의 회신 절에 \"바로잡음(날짜): …\"을 붙이고 status를 ANSWERED로(묻는 쪽이 다시 반영하도록).")
            if deps:
                print(f"이 질문에 기대는 다른 저장소 문서 {len(deps)} — 그 주인에게 바뀐 답이 간다(변경 알림·티켓 댓글):")
                for d in deps:
                    print(f"  - {d['repo']}/{d['id']} {d['title']}" + (f" · 티켓 {', '.join(map(str, d['issues']))}" if d["issues"] else ""))
            else:
                print(f"이 질문을 related로 가리키는 문서는 없다 — 물은 곳({asked})에 /core:ask 회신으로 직접 알린다.")
        return 0

    rs = rows(f)
    if a.cmd == "list":
        for r in rs:
            print("| " + " | ".join(r) + " |")
        if not rs:
            print("(없음)")
        return 0

    # brief — 주인이 아직 못 본 줄. 처음이면 지난 7일.
    sp, st = state(repo)
    seen = st.get(STATE_KEY)
    if seen is None:
        since = (dt.date.fromisoformat(a.today) - dt.timedelta(days=7)).isoformat()
        new = [r for r in rs if r[0] >= since]
    else:
        new = rs[int(seen):]
    if new:
        items = " · ".join(f"{r[1]} → {r[3]} (근거 {r[4]}{', ' + r[5] if r[5] != '대신 답함' else ''})" for r in new[:5])
        print(f"[대신 답함] 지난번 이후 에이전트가 이 저장소 문서를 근거로 대신 답한 것 {len(new)}: {items}"
              + (" · …" if len(new) > 5 else "")
              + " — 사람에게 먼저 한 줄로 보이고 \"아니면 말씀해 주세요\"라고 한다. 아니라고 하면 answer 스킬의 바로잡기.")
    if a.mark:
        st[STATE_KEY] = len(rs)
        try:
            sp.parent.mkdir(parents=True, exist_ok=True)
            sp.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
