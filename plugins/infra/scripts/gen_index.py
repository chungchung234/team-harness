#!/usr/bin/env python3
"""gen_index — 프론트매터에서 에이전트용 목차(docs/INDEX.md)를 생성한다. 사람이 목차를 손으로 고치지 않는다.

    python3 <플러그인>/scripts/gen_index.py docs --write     # docs/INDEX.md를 UTF-8·LF로 쓴다 (Windows에서도 안전)
    python3 <플러그인>/scripts/gen_index.py docs             # 표준 출력으로 미리보기
    python3 <플러그인>/scripts/gen_index.py --team [work/] --write   # 팀 현황 한 장: work/TEAM.md

목차 맨 위에 **최근 결정**(docs/decisions/결정-기록.md의 마지막 10줄)이 올라간다 — 회의록 원문은 notes/에 있어 목차에 없지만
결정 요지는 여기서 보인다. 사람용 현황·급한 일은 docs/STATUS.md에 쓴다 — 그 파일은 세션마다 로드되지 않는다.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from docs_check import GENERATED, load  # noqa: E402
from decision_log import REL as DECISION_LOG, rows as decision_rows  # noqa: E402

ORDER = [("policy", "정책서"), ("adr", "결정 (ADR)"), ("spec", "스펙"), ("design", "설계"), ("guide", "규약·가이드"),
         ("backlog", "백로그"), ("roadmap", "로드맵"), ("question", "질문"), ("research", "리서치"), ("meeting", "회의록")]
SKIP_DIRS = {"templates"}
RECENT_DECISIONS = 10


def esc(s) -> str:
    return str(s).replace("|", r"\|").replace("\n", " ").strip()


def scan(root: Path, warn=None) -> dict[str, list]:
    """type → [(id, title, status, rel)]"""
    rows: dict[str, list] = {}
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if rel.as_posix() in GENERATED or SKIP_DIRS & set(rel.parts):
            continue
        _, fm, err = load(p)
        if err or not fm:
            if warn:
                warn(f"gen_index: 건너뜀 {rel.as_posix()} — {err}")
            continue
        t = fm.get("type")
        if t not in dict(ORDER) and t != "index":
            if warn:
                warn(f"gen_index: 목차 분류에 없는 type `{t}` — {rel.as_posix()}")
            continue
        rows.setdefault(t, []).append((esc(fm.get("id")), esc(fm.get("title")), esc(fm.get("status")), rel.as_posix()))
    return rows


def recent_decisions(repo: Path, n: int = RECENT_DECISIONS) -> list[str]:
    rs = decision_rows(repo / DECISION_LOG)
    return [f"| {d} | {t} | {s} | {a} | {st} |" for d, t, s, a, st in rs[-n:]]


def build(root: Path, warn=None) -> str:
    rows = scan(root, warn)
    out = ["# INDEX — 문서 목차", "",
           "> 자동 생성(하네스 gen_index). 직접 고치지 않는다 — 세션 시작·문서 저장 때 훅이 다시 만든다",
           "> 필요한 문서만 경로로 연다. `ACCEPTED`만 확정이고, `DRAFT`·`REVIEW`는 반박 가능한 초안이다.", ""]
    dec = recent_decisions(root.parent)
    if dec:
        out += [f"## 최근 결정 (마지막 {len(dec)}줄 — 전체는 `{DECISION_LOG.as_posix()}`)", "",
                "| 날짜 | 결정 | 출처 | 영향 | 상태 |", "|---|---|---|---|---|", *dec, ""]
    for t, label in ORDER:
        if t not in rows:
            continue
        out += [f"## {label}", "", "| id | 제목 | 상태 | 경로 |", "|---|---|---|---|"]
        out += [f"| {i} | {ti} | `{s}` | `{r}` |" for i, ti, s, r in rows[t]]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------- 팀 현황 (저장소들을 가로질러)

def git(repo: Path, *args) -> str:
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=30)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def repos_under(work: Path) -> list[Path]:
    return sorted(p for p in work.iterdir() if p.is_dir() and (p / "docs").is_dir() and not p.name.startswith("."))


def build_team(work: Path, days: int = 7, today: dt.date | None = None) -> str:
    today = today or dt.date.today()
    out = [f"# TEAM — 팀 현황 한 장 ({today.isoformat()})", "",
           "> 자동 생성(하네스 gen_index --team). 저장소들을 가로질러 **열린 질문 · 결정 대기 · 초안 · 최근 결정 · 지난 7일 변경**을 모았다.",
           "> 사람 말로 된 요약은 `/status`. 여기는 에이전트가 세션 시작에 한 번 훑는 곳이다.", ""]
    totals = {"q": 0, "nd": 0, "draft": 0}
    for repo in repos_under(work):
        rows = scan(repo / "docs")
        qs = [(i, ti, s) for i, ti, s, _ in rows.get("question", [])]
        open_q = [x for x in qs if x[2] == "OPEN"]
        nd_q = [x for x in qs if x[2] == "NEEDS-DECISION"]
        drafts = [(t, i, ti, s) for t, lst in rows.items() if t not in ("question", "index") for i, ti, s, _ in lst if s in ("DRAFT", "REVIEW")]
        dec = recent_decisions(repo, 5)
        log = git(repo, "log", "--no-merges", f"--since={days}.days", "--date=short", "--format=%ad %s", "--", "docs", "notes").strip().splitlines()
        totals["q"] += len(open_q); totals["nd"] += len(nd_q); totals["draft"] += len(drafts)
        out += [f"## {repo.name} — 열린 질문 {len(open_q)} · 결정 대기 {len(nd_q)} · 초안 {len(drafts)} · 지난 {days}일 커밋 {len(log)}", ""]
        if nd_q:
            out += ["**결정 대기 (사람이 고른다)**", *[f"- {i} {ti}" for i, ti, _ in nd_q], ""]
        if open_q:
            out += ["**열린 질문**", *[f"- {i} {ti}" for i, ti, _ in open_q], ""]
        if drafts:
            out += ["**초안 (`DRAFT`·`REVIEW` — 확정 아님)**", *[f"- {i} {ti} `{s}`" for _, i, ti, s in drafts[:12]], *(["- …"] if len(drafts) > 12 else []), ""]
        if dec:
            out += ["**최근 결정**", *[f"- {l.strip('| ').split(' | ')[0]} — {l.strip('| ').split(' | ')[1]} ({l.strip('| ').split(' | ')[2]})" for l in dec], ""]
        if log:
            out += [f"**지난 {days}일 변경 (docs·notes)**", *[f"- {l}" for l in log[:8]], *(["- …"] if len(log) > 8 else []), ""]
    out.insert(4, "")
    out.insert(5, f"**전체** — 열린 질문 {totals['q']} · 결정 대기 {totals['nd']} · 초안 {totals['draft']} · 저장소 {len(repos_under(work))}")
    return "\n".join(out).rstrip() + "\n"


def find_work(start: Path) -> Path:
    """저장소 안에서 부르면 부모(work/)를, work/에서 부르면 그 자리를."""
    if (start / "docs").is_dir() and ((start / "AGENTS.md").exists() or (start / "CLAUDE.md").exists()):
        return start.parent
    return start


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--team" in sys.argv:
        work = Path(args[0]).resolve() if args else find_work(Path.cwd().resolve())
        text = build_team(work)
        if "--write" in sys.argv:
            (work / "TEAM.md").write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {work / 'TEAM.md'} ({len(repos_under(work))} repos)")
        else:
            sys.stdout.write(text)
        sys.exit(0)
    root = Path(args[0] if args else "docs").resolve()
    text = build(root, warn=lambda m: print(m, file=sys.stderr))
    if "--write" in sys.argv:
        (root / "INDEX.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {root.name}/INDEX.md ({len(text.encode())} bytes)")
    else:
        sys.stdout.write(text)
