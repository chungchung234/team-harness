#!/usr/bin/env python3
"""questions — 이 저장소가 답해야 할 질문과, 이 저장소가 물어서 답이 온 질문을 보여준다.

    python3 <플러그인>/scripts/questions.py            # 표
    python3 <플러그인>/scripts/questions.py --brief    # 세션 시작 훅용 — 있을 때만 몇 줄, 없으면 아무것도 안 찍는다

- 답할 것: docs/questions/*.md 중 status OPEN · NEEDS-DECISION
- 회신 온 것: ../*/docs/questions/*.md 중 asked_by가 이 저장소이고 status ANSWERED (묻는 쪽이 반영하고 CLOSED로 닫는다)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def fm(p: Path) -> dict:
    m = FM.match(p.read_text(encoding="utf-8-sig"))
    if not m:
        return {}
    try:
        import yaml
        d = yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}
    return {k: ("" if v is None else str(v)) for k, v in d.items()} if isinstance(d, dict) else {}


def scan(qdir: Path):
    if not qdir.is_dir():
        return []
    return [(p, fm(p)) for p in sorted(qdir.glob("*.md")) if fm(p).get("type") == "question"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    me = repo.name

    todo = [(p, f) for p, f in scan(repo / "docs" / "questions") if f.get("status") in ("OPEN", "NEEDS-DECISION")]
    answered, waiting = [], []
    for sib in sorted(repo.parent.iterdir()) if repo.parent.is_dir() else []:
        if sib == repo or not (sib / "docs" / "questions").is_dir():
            continue
        for p, f in scan(sib / "docs" / "questions"):
            if f.get("asked_by", "").split("/")[0].strip() != me:
                continue
            if f.get("status") == "ANSWERED":
                answered.append((sib.name, p, f))
            elif f.get("status") == "NEEDS-DECISION":
                waiting.append((sib.name, p, f))

    if a.brief:
        if not todo and not answered and not waiting:
            return 0
        if todo:
            print(f"[questions] 이 저장소가 답할 질문 {len(todo)}건 — 먼저 본다 (규칙: 답할 수 있으면 ANSWERED, 결정이 필요하면 NEEDS-DECISION):")
            for p, f in todo:
                print(f"  - {f.get('id')} [{f.get('status')}] {f.get('title')}  ← {f.get('asked_by','?')}  ({p.relative_to(repo).as_posix()})")
        if answered:
            print(f"[questions] 이 저장소가 물었고 답이 온 질문 {len(answered)}건 — 반영하고 CLOSED로 닫는다:")
            for r, p, f in answered:
                print(f"  - {r}/{f.get('id')} {f.get('title')}  ({r}/{p.relative_to(p.parents[2]).as_posix()})")
        if waiting:
            print(f"[questions] 이 저장소가 물었고 사람의 결정을 기다리는 질문 {len(waiting)}건 — 그 답을 추측해 구현하지 않는다: " + ", ".join(f"{r}/{f.get('id')}" for r, p, f in waiting))
        return 0

    print(f"답할 질문 ({me}/docs/questions)")
    for p, f in todo or []:
        print(f"  {f.get('id'):6} {f.get('status'):15} {f.get('updated','')}  {f.get('title')}  ← {f.get('asked_by','?')}")
    if not todo:
        print("  (없음)")
    print("회신 온 질문 (내가 물은 것)")
    for r, p, f in answered or []:
        print(f"  {r}/{f.get('id'):6} ANSWERED  {f.get('updated','')}  {f.get('title')}")
    if not answered:
        print("  (없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
