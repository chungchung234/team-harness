#!/usr/bin/env python3
"""team_plan — 팀 구성(team.json)을 보이고, 고친 안을 검사하고, 바뀌는 점을 계산하고, 승인 뒤 적는다. 구조 대화 스킬(team)이 부른다.

    python3 <플러그인>/scripts/team_plan.py show                          # 지금 팀 구성을 표로
    python3 <플러그인>/scripts/team_plan.py show  --file team-proposal.json   # 제안을 표로
    python3 <플러그인>/scripts/team_plan.py check team-proposal.json         # 제안이 맞는 모양인지
    python3 <플러그인>/scripts/team_plan.py diff  team-proposal.json [--work ../work]   # 지금과 무엇이 다른가 (옮길 문서 포함)
    python3 <플러그인>/scripts/team_plan.py apply team-proposal.json         # 사람이 "승인"한 뒤에만 — team.json에 적는다

- 하네스 저장소(team.json과 sync.py가 있는 폴더)를 현재 폴더부터 위로 찾는다. --harness로 지정할 수 있다.
- apply는 check를 통과한 안만 적는다. 적은 뒤에 할 일(build.py, sync.py)을 출력한다 — 저장소를 만들거나 지우지는 않는다.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PLUGINS = {"core", "product", "dev", "frontend", "ui", "infra"}


def find_harness(start: Path) -> Path | None:
    for d in [start, *start.parents]:
        if (d / "team.json").exists() and (d / "sync.py").exists():
            return d
    return None


def load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def check(team: dict, doc_types_fallback: dict | None = None) -> list[str]:
    errs = []
    repos = team.get("repos") or {}
    if not repos:
        return ["저장소가 하나도 없다 (repos)"]
    doc_types = team.get("doc_types") or doc_types_fallback or {}
    for n, r in repos.items():
        if not n.replace("-", "").isalnum() or n != n.lower():
            errs.append(f"{n}: 저장소 이름은 영문 소문자·숫자·하이픈만")
        if not r.get("purpose"):
            errs.append(f"{n}: 담는 것(purpose)이 비었다")
        if not r.get("owner"):
            errs.append(f"{n}: 주인(owner)이 비었다 — 역할을 적는다(공개 저장소에는 사람 이름을 넣지 않는다)")
        if r.get("plugin", "core") not in PLUGINS:
            errs.append(f"{n}: 플러그인 '{r.get('plugin')}'은 없다 — {', '.join(sorted(PLUGINS))} 중 하나")
        for x in r.get("reads", []):
            if x.get("repo") not in repos:
                errs.append(f"{n}: 읽는 저장소 '{x.get('repo')}'가 팀 구성에 없다")
            if x.get("repo") == n:
                errs.append(f"{n}: 자기 자신을 읽는다")
            if not x.get("why"):
                errs.append(f"{n}: '{x.get('repo')}'를 읽는 이유(why)가 비었다")
        for k in r.get("docs", []):
            if doc_types and k not in doc_types:
                errs.append(f"{n}: 문서 종류 '{k}'가 doc_types에 없다")
    for role, n in (team.get("roles") or {}).items():
        if n not in repos and n != "harness":
            errs.append(f"역할 '{role}' → '{n}': 그런 저장소가 없다")
    return errs


def table(team: dict) -> str:
    dt = team.get("doc_types") or {}
    rows = ["| 저장소 | 담는 것 | 주인 | 읽는 저장소 | 쓰는 문서 | 플러그인 |", "|---|---|---|---|---|---|"]
    for n, r in team["repos"].items():
        reads = " · ".join(x["repo"] for x in r.get("reads", [])) or "—"
        docs = " · ".join(dt.get(k, {}).get("label", k) for k in r.get("docs", [])) or "(양식 없음)"
        rows.append(f"| {n} | {r.get('label') or r.get('purpose', '')} | {r.get('owner', '')} | {reads} | {docs} | {r.get('plugin', 'core')} |")
    roles = " · ".join(f"{k} → {v}" for k, v in (team.get("roles") or {}).items())
    return "\n".join(rows) + f"\n\n역할: {roles}"


def diff(old: dict, new: dict, work: Path | None = None) -> list[str]:
    out = []
    o, n = old.get("repos", {}), new.get("repos", {})
    for k in n.keys() - o.keys():
        out.append(f"+ 새 저장소 {k} — {n[k].get('purpose', '')} (주인 {n[k].get('owner', '')})")
    for k in o.keys() - n.keys():
        line = f"- 없어지는 저장소 {k}"
        if work and (work / k / "docs").is_dir():
            docs = sorted(str(p.relative_to(work / k)) for p in (work / k / "docs").rglob("*.md") if p.name != "INDEX.md" and "templates" not in p.parts)
            line += f" — 옮겨야 할 문서 {len(docs)}개" + ("".join(f"\n    {d}" for d in docs) if docs else "")
        out.append(line)
    for k in sorted(o.keys() & n.keys()):
        a, b = o[k], n[k]
        for f in ("owner", "purpose", "plugin"):
            if a.get(f) != b.get(f):
                out.append(f"~ {k}.{f}: {a.get(f)} → {b.get(f)}")
        ra, rb = {x["repo"] for x in a.get("reads", [])}, {x["repo"] for x in b.get("reads", [])}
        if ra != rb:
            out.append(f"~ {k} 읽는 저장소: +{sorted(rb - ra) or '없음'} −{sorted(ra - rb) or '없음'} (변경 알림이 가는 길이 바뀐다)")
        da, db = set(a.get("docs", [])), set(b.get("docs", []))
        if da != db:
            out.append(f"~ {k} 쓰는 문서: +{sorted(db - da) or '없음'} −{sorted(da - db) or '없음'}")
    ro, rn = old.get("roles", {}), new.get("roles", {})
    for r in sorted(set(ro) | set(rn)):
        if ro.get(r) != rn.get(r):
            out.append(f"~ 역할 {r}: {ro.get(r)} → {rn.get(r)}")
    return out or ["바뀌는 것 없음"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["show", "check", "diff", "apply"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--file", dest="file_opt")
    ap.add_argument("--harness")
    ap.add_argument("--work", help="팀 저장소들이 받아져 있는 폴더 — 없어지는 저장소의 문서를 센다")
    a = ap.parse_args()
    h = Path(a.harness).resolve() if a.harness else find_harness(Path.cwd().resolve())
    if not h:
        sys.exit("하네스 저장소(team.json + sync.py)를 찾지 못했다 — 하네스 저장소 폴더에서 실행하거나 --harness")
    cur = load(h / "team.json")
    f = a.file or a.file_opt
    if a.cmd == "show":
        print(table(load(Path(f)) if f else cur))
        return 0
    if not f:
        sys.exit("제안 파일이 필요하다")
    prop = load(Path(f))
    errs = check(prop, cur.get("doc_types"))
    if a.cmd == "check":
        print("통과" if not errs else "\n".join("✗ " + e for e in errs))
        return 0 if not errs else 1
    if a.cmd == "diff":
        print("\n".join(diff(cur, prop, Path(a.work).resolve() if a.work else None)))
        return 0
    if errs:
        print("\n".join("✗ " + e for e in errs))
        sys.exit("검사를 통과하지 못해 적지 않았다")
    prop.setdefault("doc_types", cur.get("doc_types", {}))
    prop.setdefault("_설명", cur.get("_설명", ""))
    shutil.copy(h / "team.json", h / "team.prev.json")   # 이전 판 (git에 올리지 않는다)
    (h / "team.json").write_text(json.dumps(prop, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"적었다: {h / 'team.json'}")
    print("다음: python3 build.py · 새 저장소는 python3 sync.py new <이름> --into <work> · 기존 저장소는 python3 sync.py update <폴더들>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
