#!/usr/bin/env python3
"""new_doc — 양식에서 새 문서를 만든다. 다음 번호를 스캔해서 부여하므로 id 충돌(E06)이 나지 않는다.

    python3 <플러그인>/scripts/new_doc.py policy  "주문 취소"                 # → docs/policy/POL-02-주문-취소.md
    python3 <플러그인>/scripts/new_doc.py spec    "주문 취소 API" --related product/POL-01     # → docs/specs/SPEC-01-주문-취소-API.md
    python3 <플러그인>/scripts/new_doc.py question "'즉시'는 몇 초인가?" --to ../product --asked-by backend --related POL-01,backend/D-23
    python3 <플러그인>/scripts/new_doc.py adr     "에이전트 서버 Python 분리"
    python3 <플러그인>/scripts/new_doc.py meeting "AI 개발체계 리서치 공유" --date 2026-10-02  # → notes/meetings/2026-10-02-….md
    python3 <플러그인>/scripts/new_doc.py research "위키 도구 비교"                            # → notes/research/RS-07-….md

- 양식은 product의 docs/templates/ (이 저장소가 product가 아니면 ../product/docs/templates/). 없으면 최소 프론트매터만 쓴다.
- --to <저장소 경로>: 그 저장소에 만든다 (질문은 답할 저장소에 만드는 것이 규칙). 번호도 그 저장소 기준으로 매긴다.
- owner는 --owner, 없으면 git user.name. 질문의 owner는 답할 사람이므로 --owner를 명시한다(모르면 비워 두고 사람이 채운다).
- 만든 경로를 stdout에 한 줄로 출력한다. 그 뒤 gen_index·docs_check는 훅이 돌린다.
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

# type → (양식 파일, 목적지 폴더, id 접두, 자리수, 기본 status)
KIND = {
    "policy":   ("정책서-템플릿.md", "docs/policy",     "POL",  2, "DRAFT"),
    "spec":     ("스펙-템플릿.md",   "docs/specs",      "SPEC", 2, "DRAFT"),
    "question": ("질문-템플릿.md",   "docs/questions",  "Q",    2, "OPEN"),
    "adr":      ("ADR-템플릿.md",    "docs/decisions",  "ADR",  3, "DRAFT"),
    "design":   ("설계문서-템플릿.md", "docs/design",   "DSN",  2, "DRAFT"),
    "meeting":  ("회의록-템플릿.md", "notes/meetings",  "M",    0, "DRAFT"),
    "research": (None,               "notes/research",  "RS",   2, "DRAFT"),
}
# team.json의 문서 종류가 있으면 그것을 쓴다 (repos.json으로 온다)
import json as _json
try:
    _CFG = _json.loads((Path(__file__).resolve().parent / "repos.json").read_text(encoding="utf-8"))
except Exception:
    _CFG = {}
for _k, _v in (_CFG.get("doc_types") or {}).items():
    KIND[_k] = (_v.get("template"), _v["dir"], _v["prefix"], int(_v.get("digits", 2)), _v.get("status", "DRAFT"))
FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def slug(title: str) -> str:
    s = re.sub(r"[^\w가-힣]+", "-", title).strip("-")
    return s[:40].rstrip("-") or "untitled"


def next_number(repo: Path, prefix: str) -> int:
    pat = re.compile(rf"^id:\s*{prefix}-(\d+)\s*$", re.M)
    n = 0
    for root in ("docs", "notes"):
        for p in (repo / root).rglob("*.md"):
            if "templates" in p.parts:
                continue
            try:
                head = p.read_text(encoding="utf-8-sig")[:600]
            except OSError:
                continue
            for m in pat.finditer(head):
                n = max(n, int(m.group(1)))
    return n + 1


def git_user(repo: Path) -> str:
    try:
        return subprocess.run(["git", "config", "user.name"], cwd=repo, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def template_dir(repo: Path) -> Path | None:
    """양식: 이 저장소 → 옆의 product → 플러그인에 든 기본 양식(product가 아직 없을 때)."""
    for cand in (repo / "docs" / "templates", repo.parent / "product" / "docs" / "templates", Path(__file__).resolve().parent.parent / "templates"):
        if cand.is_dir():
            return cand
    return None


def set_field(head: str, key: str, value: str) -> str:
    line = f"{key}: {value}"
    if re.search(rf"^{key}:.*$", head, re.M):
        return re.sub(rf"^{key}:.*$", line, head, count=1, flags=re.M)
    return head + "\n" + line


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind", choices=sorted(KIND))
    ap.add_argument("title")
    ap.add_argument("--to", default=".", help="만들 저장소 경로 (기본: 현재 저장소)")
    ap.add_argument("--related", default="", help="쉼표 구분. 다른 저장소 문서는 저장소/ID")
    ap.add_argument("--owner", default=None)
    ap.add_argument("--asked-by", default=None, help="질문: 묻는 저장소/사람")
    ap.add_argument("--date", default=None, help="회의록 날짜 YYYY-MM-DD (기본 오늘)")
    ap.add_argument("--status", default=None)
    a = ap.parse_args()

    repo = Path(a.to).resolve()
    if not (repo / "docs").is_dir():
        sys.exit(f"저장소가 아니다 (docs/ 없음): {repo}")
    _name = repo.name
    try:
        _name = _json.loads((repo / ".claude" / "harness.json").read_text(encoding="utf-8")).get("repo") or _name
    except Exception:
        pass
    _allowed = (_CFG.get("docs") or {}).get(_name)
    if _allowed is not None and a.kind not in _allowed:
        _where = [n for n, ks in (_CFG.get("docs") or {}).items() if a.kind in ks]
        sys.exit(f"{_name} 저장소는 '{a.kind}' 문서를 쓰지 않는다(team.json). 쓰는 저장소: {', '.join(_where) or '없음'}")
    tpl_name, dest, prefix, width, default_status = KIND[a.kind]
    today = dt.date.today().isoformat()

    if a.kind == "meeting":
        date = a.date or today
        doc_id = "M-" + date.replace("-", "")
        fname = f"{date}-{slug(a.title)}.md"
    else:
        num = next_number(repo, prefix)
        doc_id = f"{prefix}-{num:0{width}d}"
        fname = f"{doc_id}-{slug(a.title)}.md"
    out = repo / dest / fname
    if out.exists():
        sys.exit(f"이미 있다: {out}")

    tdir = template_dir(repo)
    tpl = (tdir / tpl_name) if (tdir and tpl_name and (tdir / tpl_name).exists()) else None
    if tpl:
        text = tpl.read_text(encoding="utf-8-sig")
        m = FM.match(text)
        head, body = m.group(1), text[m.end():]
        # 양식 안의 자리표시자 id(POL-NN, ADR-NNN, M-YYYYMMDD, Q-NN …)를 본문에서도 바꾼다
        placeholder = re.search(r"^id:\s*(\S+)", head, re.M).group(1)
        body = body.replace(placeholder, doc_id)
    else:
        head, body = f"id: {doc_id}\ntype: {a.kind}\ntitle: \nstatus: {default_status}\nowner:\ncreated: {today}\nupdated: {today}\nrelated: []", f"\n# {doc_id}: {a.title}\n\n## 배경\n\n## 내용\n\n## 결론\n"

    owner = a.owner if a.owner is not None else git_user(Path.cwd())
    related = ", ".join(x.strip() for x in a.related.split(",") if x.strip())
    head = set_field(head, "id", doc_id)
    head = set_field(head, "type", a.kind)
    head = set_field(head, "title", "'" + a.title.replace("'", "''") + "'")
    head = set_field(head, "status", a.status or default_status)
    head = set_field(head, "owner", owner)
    head = set_field(head, "created", today)
    head = set_field(head, "updated", today)
    head = set_field(head, "related", f"[{related}]")
    if a.kind == "question":
        head = set_field(head, "asked_by", a.asked_by or Path.cwd().resolve().name)  # 묻는 쪽 저장소에서 실행한다
    body = re.sub(r"^# .*$", f"# {doc_id}: {a.title}", body, count=1, flags=re.M)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"---\n{head}\n---\n{body}", encoding="utf-8", newline="\n")
    print(out.relative_to(Path.cwd()).as_posix() if out.is_relative_to(Path.cwd()) else str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
