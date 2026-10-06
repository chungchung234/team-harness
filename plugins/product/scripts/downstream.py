#!/usr/bin/env python3
"""downstream — 이 저장소의 문서 하나에 **다른 저장소의 어떤 문서가 기대고 있는지** 센다. 결정의 크기를 가를 때 쓴다.

    python3 <플러그인>/scripts/downstream.py POL-01            # 이 저장소의 POL-01에 기대는 문서
    python3 <플러그인>/scripts/downstream.py POL-01 --repo ../product
    python3 <플러그인>/scripts/downstream.py Q-03 --json

- 기대는 문서 = 옆 저장소(같은 부모 폴더) docs/ 의 프론트매터 `related`에 `<이 저장소>/<ID>`가 있는 문서.
- 이 저장소를 읽는 저장소(repos.json의 reads) 중 이 컴퓨터에 없는 것은 "세지 못함"으로 따로 말한다 — 없다고 단정하지 않는다.
- 크기 판정은 하지 않는다. 사람의 말이 **뜻을 바꾸는지**는 에이전트가 본다. 이 스크립트는 "기대는 문서가 있는가"와 "한 사람 더"의 기본값(저장소 주인)만 준다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def cfg() -> dict:
    try:
        return json.loads((HERE / "repos.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def front(p: Path) -> dict:
    try:
        m = FM.match(p.read_text(encoding="utf-8-sig"))
    except OSError:
        return {}
    if not m:
        return {}
    try:
        import yaml
        d = yaml.safe_load(m.group(1)) or {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def refs(fm: dict) -> set[str]:
    r = fm.get("related") or []
    if isinstance(r, str):
        r = [x for x in r.strip("[]").split(",")]
    return {str(x).strip().strip("'\"") for x in r if str(x).strip()}


def find_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "docs").is_dir() and ((p / "AGENTS.md").exists() or (p / "CLAUDE.md").exists()):
            return p
    return start


def dependents(repo: Path, doc_id: str) -> list[dict]:
    """옆 저장소들에서 `<repo.name>/<doc_id>`를 related로 가진 문서."""
    key = f"{repo.name}/{doc_id}"
    out = []
    for sib in sorted(repo.parent.iterdir()) if repo.parent.is_dir() else []:
        if sib == repo or not (sib / "docs").is_dir():
            continue
        for p in sorted((sib / "docs").rglob("*.md")):
            if p.name == "INDEX.md" or "templates" in p.parts:
                continue
            fm = front(p)
            if key in refs(fm):
                out.append({"repo": sib.name, "id": str(fm.get("id", p.stem)), "title": str(fm.get("title", "")),
                            "status": str(fm.get("status", "")), "issues": fm.get("issues") or [],
                            "path": f"{sib.name}/{p.relative_to(sib).as_posix()}"})
    return out


def readers(me: str, c: dict) -> list[str]:
    return sorted(n for n, rs in (c.get("reads") or {}).items() if me in rs and n != me)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("id")
    ap.add_argument("--repo")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    repo = Path(a.repo).resolve() if a.repo else find_root(Path.cwd().resolve())
    c = cfg()
    deps = dependents(repo, a.id)
    missing = [n for n in readers(repo.name, c) if not (repo.parent / n / "docs").is_dir()]
    owner = (c.get("owners") or {}).get(repo.name, "")
    if a.json:
        print(json.dumps({"id": f"{repo.name}/{a.id}", "dependents": deps, "not_checked": missing, "owner": owner}, ensure_ascii=False, indent=1))
        return 0
    if deps:
        print(f"{repo.name}/{a.id}에 기대는 다른 저장소 문서 {len(deps)}:")
        for d in deps:
            print(f"  - {d['repo']}/{d['id']} {d['title']} ({d['status']})" + (f" · 티켓 {', '.join(map(str, d['issues']))}" if d["issues"] else ""))
        print("→ 뜻이 바뀌는 변경이면 큰 결정이다 (RULES '결정의 크기').")
    else:
        print(f"{repo.name}/{a.id}에 기대는 다른 저장소 문서: 없음")
    if missing:
        print(f"세지 못함: {', '.join(missing)} — 이 저장소를 읽지만 이 컴퓨터에 없다. 없다고 단정하지 않는다.")
    if owner:
        print(f"한 사람 더(기본): 이 저장소 주인 — {owner}. 바꾸는 사람이 주인이면 회의 안건으로.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
