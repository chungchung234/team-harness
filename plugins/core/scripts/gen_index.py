#!/usr/bin/env python3
"""gen_index — 프론트매터에서 에이전트용 목차(docs/INDEX.md)를 생성한다. 사람이 목차를 손으로 고치지 않는다.

    python3 <플러그인>/scripts/gen_index.py docs --write     # docs/INDEX.md를 UTF-8·LF로 쓴다 (Windows에서도 안전)
    python3 <플러그인>/scripts/gen_index.py docs             # 표준 출력으로 미리보기
    python3 <플러그인>/scripts/gen_index.py --team [work/] --write   # 팀 현황 한 장: work/TEAM.md

목차 맨 위에 **최근 결정**(docs/decisions/결정-기록.md의 마지막 10줄)이 올라간다 — 회의록 원문은 notes/에 있어 목차에 없지만
결정 요지는 여기서 보인다. 사람용 현황·급한 일은 docs/STATUS.md에 쓴다 — 그 파일은 세션마다 로드되지 않는다.

    python3 <플러그인>/scripts/gen_index.py docs --stale     # 세션 시작 훅용 — 낡은 내 문서 한 줄 (없으면 아무것도 안 찍는다)

**살펴볼 것(낡음 신호)** 은 사람이 상태를 붙이지 않고 계산한다 — 목차 맨 위와 세션 시작에 보인다.
- 기대던 문서(related)가 이 문서보다 나중에 바뀜 — 시각은 마지막 커밋(커밋 안 된 변경은 지금), git이 없으면 프론트매터 updated
- 답 없는 질문(OPEN)·결정 대기(NEEDS-DECISION)가 7일을 넘김
- 다시 볼 날(review_by)이 지남
"""
from __future__ import annotations

import datetime as dt
import re
import subprocess
import time
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
STALE_Q_DAYS = 7
REF = re.compile(r"^(?:([a-z][a-z0-9-]*)/)?([A-Z]+-\d+)$")
SKIP_UP = ("D-", "M-")          # 논점·회의록은 기대는 문서로 보지 않는다
QUIET_TYPES = {"index", "backlog"}


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


def meta(repo: Path) -> list[tuple[str, dict]]:
    """저장소 docs/의 (저장소 기준 경로, 프론트매터)."""
    out = []
    d = repo / "docs"
    if not d.is_dir():
        return out
    for p in sorted(d.rglob("*.md")):
        rel = p.relative_to(d)
        if rel.as_posix() in GENERATED or SKIP_DIRS & set(rel.parts):
            continue
        _, fm, err = load(p)
        if fm and not err:
            out.append((p.relative_to(repo).as_posix(), fm))
    return out


def changed_at(repo: Path) -> dict[str, float]:
    """docs/ 파일 → 마지막 커밋 시각. 커밋 안 된 변경은 지금. git이 아니면 빈 dict."""
    out: dict[str, float] = {}
    t = None
    for l in git(repo, "log", "--format=@%ct", "--name-only", "--", "docs").splitlines():
        if l.startswith("@"):
            t = float(l[1:])
        elif l.strip() and t is not None and l not in out:
            out[l] = t
    now = time.time()
    for l in git(repo, "status", "--porcelain", "--", "docs").splitlines():
        path = l[3:].split(" -> ")[-1].strip().strip('"')
        if path:
            out[path] = now
    return out


def as_date(v) -> dt.date | None:
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except Exception:
        return None


def refs(fm: dict) -> list[str]:
    r = fm.get("related") or []
    if isinstance(r, str):
        r = r.strip("[]").split(",")
    return [str(x).strip().strip("'\"") for x in r if str(x).strip()]


def stale(root: Path, today: dt.date | None = None) -> list[tuple[str, str, str]]:
    """낡음 신호 — (id, 제목, 이유들). root는 저장소의 docs/."""
    repo = root.parent
    today = today or dt.date.today()
    cache: dict[str, dict | None] = {}
    times: dict[str, dict] = {}

    def index_of(name: str):
        if name not in cache:
            r = repo if name == repo.name else repo.parent / name
            if not (r / "docs").is_dir():
                cache[name] = None
            else:
                cache[name] = {str(fm.get("id")): (rel, fm) for rel, fm in meta(r)}
                times[name] = changed_at(r)
        return cache[name]

    def when(name: str, rel: str, fm: dict) -> float | None:
        t = times.get(name, {}).get(rel)
        if t is not None:
            return t
        d = as_date(fm.get("updated"))
        return time.mktime(d.timetuple()) if d else None

    mine = index_of(repo.name) or {}
    out = []
    for did, (rel, fm) in mine.items():
        s, t = fm.get("status"), fm.get("type")
        if t in QUIET_TYPES or s in ("SUPERSEDED", "DROPPED", "CLOSED"):
            continue
        why = []
        my_t = when(repo.name, rel, fm)
        for ref in refs(fm):
            m = REF.match(ref)
            if not m or m.group(2).startswith(SKIP_UP) or (not m.group(1) and m.group(2) == did):
                continue
            idx = index_of(m.group(1) or repo.name)
            hit = idx.get(m.group(2)) if idx else None
            if not hit or hit[1].get("status") == "DROPPED":
                continue
            up_t = when(m.group(1) or repo.name, hit[0], hit[1])
            if my_t and up_t and up_t > my_t + 60:
                days = max(0, (today - dt.date.fromtimestamp(up_t)).days)
                why.append(f"기대던 {ref}이 이 문서보다 나중에 바뀜({'오늘' if days == 0 else f'{days}일 전'})")
        if t == "question" and s in ("OPEN", "NEEDS-DECISION"):
            c = as_date(fm.get("created"))
            if c and (today - c).days > STALE_Q_DAYS:
                why.append(f"{'답 없는 질문' if s == 'OPEN' else '결정 대기'} {(today - c).days}일째")
        rb = as_date(fm.get("review_by"))
        if rb and rb < today:
            why.append(f"다시 볼 날({rb.isoformat()}) 지남")
        if why:
            out.append((did, esc(fm.get("title")), "; ".join(why)))
    return sorted(out)


def build(root: Path, warn=None, today: dt.date | None = None) -> str:
    rows = scan(root, warn)
    out = ["# INDEX — 문서 목차", "",
           "> 자동 생성(하네스 gen_index). 직접 고치지 않는다 — 세션 시작·문서 저장 때 훅이 다시 만든다",
           "> 필요한 문서만 경로로 연다. `ACCEPTED`만 확정이고, `DRAFT`·`REVIEW`는 반박 가능한 초안이다.", ""]
    st = stale(root, today)
    if st:
        out += [f"## 살펴볼 것 ({len(st)} — 자동 계산, 사람이 붙이지 않는다)", "",
                "> 기대던 문서가 바뀌었으면 원문을 열어 반영한다. 반영할 것이 없으면 개정 이력에 \"확인 — 영향 없음\" 한 줄을 남긴다(그러면 사라진다).", "",
                *[f"- {i} {ti} — {w}" for i, ti, w in st], ""]
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
    totals = {"q": 0, "nd": 0, "draft": 0, "stale": 0}
    for repo in repos_under(work):
        rows = scan(repo / "docs")
        qs = [(i, ti, s) for i, ti, s, _ in rows.get("question", [])]
        open_q = [x for x in qs if x[2] == "OPEN"]
        nd_q = [x for x in qs if x[2] == "NEEDS-DECISION"]
        drafts = [(t, i, ti, s) for t, lst in rows.items() if t not in ("question", "index") for i, ti, s, _ in lst if s in ("DRAFT", "REVIEW")]
        dec = recent_decisions(repo, 5)
        old = stale(repo / "docs", today)
        log = git(repo, "log", "--no-merges", f"--since={days}.days", "--date=short", "--format=%ad %s", "--", "docs", "notes").strip().splitlines()
        totals["q"] += len(open_q); totals["nd"] += len(nd_q); totals["draft"] += len(drafts); totals["stale"] += len(old)
        out += [f"## {repo.name} — 열린 질문 {len(open_q)} · 결정 대기 {len(nd_q)} · 초안 {len(drafts)} · 낡음 {len(old)} · 지난 {days}일 커밋 {len(log)}", ""]
        if old:
            out += ["**낡음 (자동 계산)**", *[f"- {i} {ti} — {w}" for i, ti, w in old[:8]], ""]
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
    out.insert(5, f"**전체** — 열린 질문 {totals['q']} · 결정 대기 {totals['nd']} · 초안 {totals['draft']} · 낡음 {totals['stale']} · 저장소 {len(repos_under(work))}")
    return "\n".join(out).rstrip() + "\n"


def find_work(start: Path) -> Path:
    """저장소 안에서 부르면 부모(work/)를, work/에서 부르면 그 자리를."""
    if (start / "docs").is_dir() and ((start / "AGENTS.md").exists() or (start / "CLAUDE.md").exists()):
        return start.parent
    return start


if __name__ == "__main__":
    _today = None
    if "--today" in sys.argv:
        _i = sys.argv.index("--today"); _today = dt.date.fromisoformat(sys.argv[_i + 1]); del sys.argv[_i:_i + 2]
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--team" in sys.argv:
        work = Path(args[0]).resolve() if args else find_work(Path.cwd().resolve())
        text = build_team(work, today=_today)
        if "--write" in sys.argv:
            (work / "TEAM.md").write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {work / 'TEAM.md'} ({len(repos_under(work))} repos)")
        else:
            sys.stdout.write(text)
        sys.exit(0)
    root = Path(args[0] if args else "docs").resolve()
    if "--stale" in sys.argv:
        st = stale(root, _today)
        if st:
            print(f"[낡음] 내 문서 {len(st)}: " + " · ".join(f"{i} {ti}({w})" for i, ti, w in st[:5]) + (" · …" if len(st) > 5 else "")
                  + " — 사람에게 풀어서 말하고, 기대던 문서가 바뀐 것은 원문을 열어 반영할지 묻는다")
        sys.exit(0)
    text = build(root, warn=lambda m: print(m, file=sys.stderr), today=_today)
    if "--write" in sys.argv:
        (root / "INDEX.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {root.name}/INDEX.md ({len(text.encode())} bytes)")
    else:
        sys.stdout.write(text)
