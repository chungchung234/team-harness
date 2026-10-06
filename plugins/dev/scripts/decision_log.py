#!/usr/bin/env python3
"""decision_log — 결정 기록(docs/decisions/결정-기록.md)에 한 줄을 붙인다. append-only, 한 결정 = 한 줄.

    python3 <플러그인>/scripts/decision_log.py add "문서는 git 저장소에 둔다" --source "M-20260929-b #1" --affects D-20,ADR-004
    python3 <플러그인>/scripts/decision_log.py add "product는 PR 없이 커밋" --source "M-20260929-b 잠정 #9" --status 잠정 --date 2026-09-29
    python3 <플러그인>/scripts/decision_log.py recent            # 최근 10줄 (gen_index·팀 현황·세션 피드가 읽는다)
    python3 <플러그인>/scripts/decision_log.py recent -n 5 --repo ../product

왜 있나: 회의록 원문은 notes/에 있어 목차에 오르지 않는다 — 그래서 "회의에서 무엇이 정해졌는가"를
다른 저장소의 에이전트가 알 길이 없었다. 결정 요지는 정제된 것이므로 docs/에 둔다.
/minutes가 회의록을 만들며 여기에 한 줄씩 붙이고, gen_index가 최근 10줄을 INDEX 맨 위에 올리고, 세션 피드가 새 줄을 알린다.

- 파일이 없으면 만든다 (id DOC-000 — 저장소마다 하나, 살아있는 문서, type backlog라 신선도 경고 없음).
- 줄은 표의 한 행: | 날짜 | 결정 | 출처 | 영향 | 상태 | . 지우거나 고치지 않는다 — 뒤집혔으면 새 줄로 "번복: …".
- owner는 --owner, 없으면 git user.name, 그것도 없으면 '하네스담당'.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REL = Path("docs/decisions/결정-기록.md")
HEAD = "| 날짜 | 결정 | 출처 | 영향 | 상태 |\n|---|---|---|---|---|\n"
ROW = re.compile(r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.*?)\|(.*?)\|(.*?)\|(.*?)\|\s*$")


def esc(s: str) -> str:
    return str(s).replace("|", "／").replace("\n", " ").strip()


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "docs").is_dir() and ((p / "AGENTS.md").exists() or (p / "CLAUDE.md").exists() or (p / "scripts").is_dir()):
            return p
    return start


def owner_default(repo: Path) -> str:
    try:
        n = subprocess.run(["git", "config", "user.name"], cwd=repo, capture_output=True, text=True, encoding="utf-8").stdout.strip()
        return n or "하네스담당"
    except Exception:
        return "하네스담당"


def ensure(repo: Path, owner: str | None, today: str) -> Path:
    f = repo / REL
    if f.exists():
        return f
    f.parent.mkdir(parents=True, exist_ok=True)
    o = owner or owner_default(repo)
    f.write_text(
        "---\n"
        "id: DOC-000\n"
        "type: backlog\n"
        f"title: 결정 기록 — {repo.name}에서 정해진 것, 한 줄씩 (append-only)\n"
        "status: ACCEPTED\n"
        f"owner: {esc(o)}\n"
        f"created: {today}\n"
        f"updated: {today}\n"
        "related: [DOC-000]\n"
        "---\n\n"
        f"# 결정 기록 — {repo.name}\n\n"
        "> **append-only.** 회의(`/minutes`)·ADR에서 정해진 것을 한 줄씩 붙인다. 지우거나 고치지 않는다 — 뒤집혔으면 새 줄에 \"번복: …\".\n"
        "> 원문은 `notes/meetings/`·`docs/decisions/ADR-*.md`. 여기는 요지와 출처만. `gen_index`가 최근 10줄을 INDEX 맨 위에 올리고, 세션 시작 피드가 새 줄을 알린다.\n"
        "> 상태: `확정`(ACCEPTED 회의·ADR) · `잠정`(DRAFT 회의록, 참석자 확인 전) · `번복`.\n\n"
        + HEAD,
        encoding="utf-8", newline="\n",
    )
    return f


def rows(f: Path) -> list[tuple[str, str, str, str, str]]:
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8-sig").splitlines():
        m = ROW.match(line)
        if m and not m.group(2).strip().startswith("---") and m.group(1) != "날짜":
            out.append(tuple(x.strip() for x in m.groups()))
    return out


def add(repo: Path, text: str, source: str, affects: str, status: str, date: str, owner: str | None) -> str:
    f = ensure(repo, owner, date)
    body = f.read_text(encoding="utf-8")
    line = f"| {date} | {esc(text)} | {esc(source)} | {esc(affects) or '—'} | {esc(status)} |"
    if line in body:
        return line  # 같은 줄은 두 번 붙이지 않는다 (멱등)
    if not body.endswith("\n"):
        body += "\n"
    body += line + "\n"
    body = re.sub(r"^updated: .*$", f"updated: {date}", body, count=1, flags=re.M)
    f.write_text(body, encoding="utf-8", newline="\n")
    return line


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", help="저장소 경로 (기본: 현재 위치에서 위로 찾음)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("text"); a.add_argument("--source", required=True, help="M-YYYYMMDD[-a] #n · ADR-NNN")
    a.add_argument("--affects", default="", help="D-NN,ADR-NNN,POL-NN (쉼표)"); a.add_argument("--status", default="잠정", choices=["확정", "잠정", "번복"])
    a.add_argument("--date", default=dt.date.today().isoformat()); a.add_argument("--owner")
    r = sub.add_parser("recent"); r.add_argument("-n", type=int, default=10); r.add_argument("--since", help="YYYY-MM-DD 이후만")
    args = ap.parse_args()
    repo = Path(args.repo).resolve() if args.repo else find_root(Path.cwd().resolve())
    if args.cmd == "add":
        line = add(repo, args.text, args.source, args.affects.replace(",", " · ") if args.affects else "", args.status, args.date, args.owner)
        print(f"{REL.as_posix()} ← {line}")
        return 0
    rs = rows(repo / REL)
    if args.since:
        rs = [x for x in rs if x[0] >= args.since]
    for d, t, s, a_, st in rs[-args.n:]:
        print(f"| {d} | {t} | {s} | {a_} | {st} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
