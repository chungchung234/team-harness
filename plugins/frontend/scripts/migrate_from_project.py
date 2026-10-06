#!/usr/bin/env python3
"""migrate_from_project — Claude 프로젝트 스냅샷을 저장소 docs/ 레이아웃으로 옮긴다 (컷오버 1회용).

    python3 scripts/migrate_from_project.py ../snapshot/claude docs notes [--shared ../product/docs] [--prefix claude] [--force]

- 관리 문서(00·01·02·04)·decisions/·design/ → docs/   (정제 문서 — 결정 #8)
- INDEX.md(사람용 현황판) → docs/STATUS.md             (세션마다 로드하지 않는다)
- 00-…철학….md(기반 문서) · 03-문서관리-규약.md · templates/ → --shared 폴더     (전 저장소 공통 — product/docs/. 생략하면 docs/에 둔다)
  · 다른 저장소로 간 문서를 가리키는 related는 `저장소/ID`로, 본문 링크는 `../../product/docs/…`로 바꾼다
- meetings/·research/ → notes/meetings/·notes/research/   (원자료 — 목차에 없고 grep으로 도달. 결정 #8의 "제3의 공간")
- 프론트매터 related: 경로형 항목 → 문서 id, 중복 제거, 한 줄 목록으로
- 본문 링크: 옮긴 위치에 맞는 상대 경로로 다시 쓴다 / INDEX.md 링크 → STATUS.md
- 끝나면 docs/INDEX.md를 생성한다. Claude 프로젝트는 이후 보관용으로만 남긴다
- 내용이 다른 기존 파일이 있으면 멈춘다 (--force로 덮어쓴다). 같은 내용이면 다시 돌려도 안전하다
"""
from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from docs_check import D_DEF, FENCE, FM, load  # noqa: E402
from gen_index import build  # noqa: E402

KEEP_DIRS = {"decisions", "design", "templates"}  # → docs/  (templates는 검사·목차 제외)
NOTES_DIRS = {"meetings", "research"}                # → notes/
SHARED = {"00-*철학*.md", "03-문서관리-규약.md", "templates"}         # → --shared (전 저장소 공통. 첫 경로 요소로 판별)
SAFE = re.compile(r"^[\w가-힣./-]+$")
LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)\)")


def target_of(rel: Path, roots: dict[str, Path | None]) -> Path | None:
    """스냅샷 상대경로 → 절대 목적지 (roots: docs·notes·shared). 안 옮기면 None."""
    if roots.get("shared") and any(fnmatch.fnmatch(rel.parts[0], s) for s in SHARED):
        return roots["shared"] / rel
    if rel.as_posix() == "INDEX.md":
        return roots["docs"] / "STATUS.md"
    if len(rel.parts) == 1 or rel.parts[0] in KEEP_DIRS:
        return roots["docs"] / rel
    if rel.parts[0] in NOTES_DIRS:
        return roots["notes"] / rel
    return None


def repo_of(path: Path, roots: dict[str, Path | None]) -> str:
    """목적지가 속한 저장소 이름 — 공유 폴더면 그 저장소(../product/docs → product), 아니면 자기 저장소."""
    sh = roots.get("shared")
    if sh and path.is_relative_to(sh):
        return roots["shared_repo"]  # type: ignore[return-value]
    return roots["repo"]  # type: ignore[return-value]


def rewrite_related(head: str, path_to_id: dict[str, str], id_repo: dict[str, str] | None = None, my_repo: str = "") -> str:
    """경로형 항목 → id. 다른 저장소로 간 문서의 id에는 `저장소/` 접두사를 붙인다."""
    id_repo = id_repo or {}

    def norm(x) -> str:
        i = path_to_id.get(str(x).strip(), str(x).strip())
        r = id_repo.get(i)
        return f"{r}/{i}" if r and r != my_repo else i

    lines = head.split("\n")
    for k, line in enumerate(lines):
        if not line.startswith("related:"):
            continue
        end = k + 1
        if not line[len("related:"):].strip():  # 블록 목록 (- item)
            while end < len(lines) and re.match(r"^\s+-\s", lines[end]):
                end += 1
        import yaml
        items = yaml.safe_load("\n".join(lines[k:end])).get("related") or []
        seen = list(dict.fromkeys(norm(x) for x in items))
        fmt = ", ".join(x if SAFE.match(x) else "'" + x.replace("'", "''") + "'" for x in seen)
        return "\n".join(lines[:k] + [f"related: [{fmt}]"] + lines[end:])
    return head


def rewrite_links(body: str, src_rel: Path, src: Path, roots: dict[str, Path | None]) -> str:
    fences = {m.span() for m in FENCE.finditer(body)}

    def in_fence(pos):
        return any(a <= pos < b for a, b in fences)

    def sub(m):
        if in_fence(m.start()):
            return m.group(0)
        text, target = m.group(1), m.group(2)
        if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
            return m.group(0)
        path, _, anchor = target.partition("#")
        try:
            dest = (src / src_rel.parent / path).resolve().relative_to(src)
        except ValueError:
            return m.group(0)
        me, to = target_of(src_rel, roots), target_of(dest, roots)
        if me is None or to is None:
            return m.group(0)
        import os
        new = os.path.relpath(str(to), str(me.parent)).replace(os.sep, "/")
        return f"[{text}]({new}{'#' + anchor if anchor else ''})"

    return LINK.sub(sub, body)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("docs"); ap.add_argument("notes")
    ap.add_argument("--prefix", default="claude", help="프로젝트 문서 경로 접두사 (related의 claude/xxx.md)")
    ap.add_argument("--shared", help="전 저장소 공통 문서(03-규약·templates)를 둘 폴더, 예: ../product/docs")
    ap.add_argument("--repo", help="이 저장소 이름 (기본: docs 폴더의 부모 폴더명)")
    ap.add_argument("--shared-files", default="", help="공통 폴더로 함께 보낼 파일/폴더 이름(쉼표). 예: 00-프로젝트-운영가이드.md,01-논의-로드맵.md,02-의사결정-백로그.md,04-추적성-매트릭스.md")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    SHARED.update(x.strip() for x in a.shared_files.split(",") if x.strip())
    src = Path(a.src).resolve()
    docs_root = Path(a.docs).resolve()
    shared = Path(a.shared).resolve() if a.shared else None
    roots: dict = {"docs": docs_root, "notes": Path(a.notes).resolve(), "shared": shared,
                   "repo": a.repo or docs_root.parent.name,
                   "shared_repo": next((x for x in Path(a.shared).parts if x not in ("..", ".")), "shared") if a.shared else None}
    cwd = Path.cwd().resolve()

    meta, id_repo = {}, {}
    for p in src.rglob("*.md"):
        text, fm, _ = load(p)
        rel = p.relative_to(src)
        if fm and fm.get("id"):
            meta[rel.as_posix()] = (str(fm["id"]), str(fm.get("title", "")))
            out = target_of(rel, roots)
            if out is not None and rel.parts[0] != "templates":
                id_repo[str(fm["id"])] = repo_of(out, roots)
                if text and fm.get("type") == "backlog":  # 논점 D-NN은 백로그가 있는 저장소의 것
                    for d in D_DEF.findall(text):
                        id_repo[d] = repo_of(out, roots)
    path_to_id = {f"{a.prefix}/{r}": i for r, (i, _) in meta.items()}

    plan: dict[Path, str] = {}
    for p in sorted(src.rglob("*.md")):
        rel = p.relative_to(src)
        out = target_of(rel, roots)
        if out is None:
            continue
        text = p.read_text(encoding="utf-8-sig")
        m = FM.match(text)
        head, body = (m.group(1), text[m.end():]) if m else (None, text)
        body = rewrite_links(body, rel, src, roots)
        my_repo = repo_of(out, roots)
        plan[out] = (f"---\n{rewrite_related(head, path_to_id, id_repo, my_repo)}\n---\n" if head is not None else "") + body

    def show(o: Path) -> str:
        import os
        return os.path.relpath(str(o), str(cwd)).replace(os.sep, "/")

    # 내용이 다른 기존 파일만 막는다 — 같은 내용의 재실행은 통과(멱등), 로컬 수정은 보호
    clash = [o for o, t in plan.items() if o.exists() and o.read_text(encoding="utf-8") != t]
    if clash and not a.force:
        print("멈춤: 내용이 다른 기존 파일을 덮어쓰게 된다. 로컬 수정을 확인한 뒤 --force로 다시 실행한다.")
        for o in clash:
            print("  내용 다름:", show(o))
        sys.exit(2)

    for o, t in plan.items():
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text(t, encoding="utf-8", newline="\n")
    (docs_root / "INDEX.md").write_text(build(docs_root), encoding="utf-8", newline="\n")
    if shared and shared.is_dir() and (shared.parent / "scripts" / "gen_index.py").exists():
        (shared / "INDEX.md").write_text(build(shared), encoding="utf-8", newline="\n")
    moved = sorted(show(o) for o in plan)
    n_docs = sum(1 for o in plan if o.is_relative_to(docs_root))
    n_notes = sum(1 for o in plan if o.is_relative_to(roots["notes"]))
    n_shared = len(plan) - n_docs - n_notes
    print(f"옮김 {len(moved)}건 (docs {n_docs} · notes {n_notes}" + (f" · shared {n_shared}" if shared else "") + ") + INDEX.md 생성")
    for o in moved:
        print("  ", o)


if __name__ == "__main__":
    main()
