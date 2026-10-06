#!/usr/bin/env python3
"""docs_check — 문서관리 규약 §1·§2·§5·§8을 기계로 검사한다.

    python3 <플러그인>/scripts/docs_check.py docs notes          # 저장소 루트에서. 첫 루트(docs)에 INDEX.md가 있다
    python3 <플러그인>/scripts/docs_check.py docs notes --today 2026-10-01

실패 메시지에는 수정 지침(→)을 함께 쓴다. 에이전트가 이 출력을 읽고 스스로 고치게 하기 위함이다.
종료 코드: 오류(E)가 있으면 1, 경고(W)만 있으면 0.
docs/ = 정제 문서(목차에 오른다) · notes/ = 회의록·리서치 원자료(목차에 없다, grep으로 도달). 둘 다 검사한다.
다른 저장소의 문서는 related에 `저장소/ID`로 적는다. 그 참조는 W07(경고)로 표시하고
존재 확인은 그 저장소의 검사에 맡긴다. 저장소 이름 없는 미해결 id는 E11(오류)다.
본문 링크가 저장소 밖(../../product/docs/…)을 가리키고 그 파일이 이 체크아웃에 없으면 W08(경고)다.
R10: 스펙은 related에 POL-이 있어야 한다(E17). 옆에 product가 있으면 원천 상태도 본다 — DRAFT 원천에 ACCEPTED 스펙은 E18, 원천이 초안이면 W12. Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # 한국어 Windows(cp949)에서 '—' 출력이 죽지 않게
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("pyyaml 필요: python3 -m pip install --user pyyaml")

REQUIRED = ["id", "type", "title", "status", "owner", "created", "updated", "related"]
TYPES = {"index", "guide", "roadmap", "backlog", "adr", "meeting", "research", "design", "question", "policy", "spec"}
STATUSES = {"DRAFT", "REVIEW", "ACCEPTED", "DEFERRED", "SUPERSEDED", "DROPPED"}
Q_STATUSES = {"OPEN", "ANSWERED", "NEEDS-DECISION", "CLOSED"}  # 질문 파일(type: question)만 — 묻고 답하는 상태 기계
PREFIX_BY_TYPE = {
    "adr": r"ADR-\d{3}", "meeting": r"M-\d{8}(-[a-z])?", "research": r"RS-\d{2}",
    "design": r"DSN-\d{2}", "index": r"DOC-\d{3}", "guide": r"DOC-\d{3}",
    "roadmap": r"DOC-\d{3}", "backlog": r"DOC-\d{3}", "question": r"Q-\d+",
    "policy": r"POL-\d{2}", "spec": r"SPEC-\d{2}",
}
GROUP_OWNERS = {"전원", "백엔드팀", "백엔드 팀", "팀", "백엔드", "all", "team"}
MULTI_OWNER = re.compile(r"[,/·&+、]| 및 | 외 |[가-힣]{2,4}( [가-힣]{2,4})+$")
DOC_ID = re.compile(r"^(ADR-\d{3}|RS-\d{2}|DSN-\d{2}|DOC-\d{3}|POL-\d{2}|SPEC-\d{2}|M-\d{8}(-[a-z])?)$")
D_ID, Q_ID = re.compile(r"^D-\d{2}$"), re.compile(r"^Q-\d+$")
D_DEF = re.compile(r"^(?:#{1,4} |- \*\*)(D-\d{2})\.", re.M)
Q_DEF = re.compile(r"^\|\s*\*{0,2}(Q-\d+)\*{0,2}\s*\|", re.M)
FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)
LINK = re.compile(r"\]\(([^)\s]+)\)")
FENCE = re.compile(r"^```.*?^```", re.S | re.M)
LIVING_TYPES = {"index", "guide", "roadmap", "backlog"}  # 규약 §3 살아있는 문서 — 신선도 경고 제외
GENERATED = {"INDEX.md"}  # gen_index 생성물 — 규약 §1 예외, 신선도는 E15가 본다
LOG_FILES = {"대신-답한-기록.md"}  # 하네스 기록 파일(notes/, 표 한 줄씩) — 프론트매터 없음, 목차 밖


def load(path: Path):
    """(본문, 프론트매터 dict | None, 문제 설명 | None)"""
    text = path.read_text(encoding="utf-8-sig")  # BOM 허용
    m = FM.match(text)
    if not m:
        return text, None, "프론트매터가 없다 — 파일 첫 줄이 `---`로 시작해야 한다"
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        return text, None, f"프론트매터 YAML 파싱 실패: {str(e).splitlines()[0]} — 따옴표로 시작한 값은 따옴표로 끝나야 한다. 값 전체를 '…'로 감싼다"
    if not isinstance(fm, dict):
        return text, None, "프론트매터가 key: value 형태가 아니다"
    return text, fm, None


def as_date(v):
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+", help="문서 루트들 (예: docs notes). 첫 루트에 INDEX.md")
    ap.add_argument("--repo-root", help="related 경로형 항목을 풀 기준 (기본: 첫 루트의 상위)")
    ap.add_argument("--exclude", action="append", default=None, help="제외할 하위 경로 (반복 가능, 기본: templates)")
    ap.add_argument("--owners", help="owner 허용 명단, 쉼표 구분 (예: 홍길동,김철수,이영희)")

    ap.add_argument("--today", default=dt.date.today().isoformat())
    a = ap.parse_args()
    a.exclude = a.exclude if a.exclude is not None else ["templates"]

    roots = [Path(r).resolve() for r in a.roots]
    root = roots[0]
    repo = Path(a.repo_root).resolve() if a.repo_root else root.parent
    # 저장소별 ID 접두: .claude/harness.json 의 "prefixes": {"policy": "PO-\\d{3}", ...}
    try:
        cfg = json.loads((repo / ".claude" / "harness.json").read_text(encoding="utf-8"))
        for t, rx in (cfg.get("prefixes") or {}).items():
            PREFIX_BY_TYPE[t] = rx
    except Exception:
        pass
    today = dt.date.fromisoformat(a.today)
    allow = {o.strip() for o in a.owners.split(",")} if a.owners else None
    cross = re.compile(r"^([a-z][a-z0-9-]*)/([A-Za-z]+-[\w.-]+)$")  # 다른 저장소 문서: 저장소/ID
    files = sorted(p for r in roots if r.exists() for p in r.rglob("*.md")
                   if not any(part in a.exclude for part in p.relative_to(r).parts)
                   and not (r == root and p.relative_to(r).as_posix() in GENERATED) and p.name not in LOG_FILES)

    docs, texts, errs, warns = {}, {}, [], []
    d_defs, q_defs = set(), set()

    def E(p, code, msg, fix):
        errs.append(f"{code}  {p.relative_to(repo).as_posix()}\n      {msg}\n      → {fix}")

    def W(p, code, msg, fix):
        warns.append(f"{code}  {p.relative_to(repo).as_posix()}\n      {msg}\n      → {fix}")

    for p in files:
        text, fm, problem = load(p)
        texts[p] = text
        d_defs |= set(D_DEF.findall(text))
        q_defs |= set(Q_DEF.findall(text))
        if problem:
            E(p, "E01", problem, "규약 §1의 YAML 헤더를 파일 맨 위에 둔다")
            continue
        docs[p] = fm

    ids = Counter(str(fm.get("id")) for fm in docs.values())
    known_ids = set(ids)

    for p, fm in docs.items():
        for k in REQUIRED:
            if fm.get(k) in (None, "", []):
                E(p, "E02", f"필수 필드 `{k}`가 비어 있다", f"규약 §1: `{k}`를 채운다")
        t, s, i = fm.get("type"), fm.get("status"), str(fm.get("id"))
        if t and t not in TYPES:
            E(p, "E03", f"type `{t}`는 규약에 없는 값", f"{sorted(TYPES)} 중 하나. 새 유형이면 규약 §1을 먼저 개정한다")
        if t == "question":
            if s and s not in Q_STATUSES:
                E(p, "E04", f"질문의 status `{s}`는 규약에 없는 값", f"{sorted(Q_STATUSES)} 중 하나 (OPEN → ANSWERED | NEEDS-DECISION → CLOSED)")
        elif s and s not in STATUSES:
            E(p, "E04", f"status `{s}`는 규약에 없는 값", f"{sorted(STATUSES)} 중 하나. 라이프사이클 밖 문서라면 규약 §3에 값을 먼저 정의한다")
        if t in PREFIX_BY_TYPE and not re.fullmatch(PREFIX_BY_TYPE[t], i):
            E(p, "E05", f"type `{t}`인데 id `{i}`의 형식이 맞지 않다", f"규약 §2: `{PREFIX_BY_TYPE[t]}`")
        if ids[i] > 1:
            E(p, "E06", f"id `{i}`가 {ids[i]}개 문서에 중복", "규약 §2: 번호는 재사용하지 않는다 — 나중 문서에 새 번호")
        owner = str(fm.get("owner") or "").strip()
        base = re.sub(r"\s*\(.*?\)\s*", "", owner).strip()
        if owner and (base in GROUP_OWNERS or MULTI_OWNER.search(base)):
            E(p, "E07", f"owner `{owner}`는 1인이 아니다", "규약 §1: owner는 반드시 1명. 공동 작업자는 본문에 적는다")
        elif owner and allow is not None and base not in allow:
            E(p, "E07", f"owner `{base}`가 허용 명단에 없다", f"명단: {sorted(allow)}. 새 팀원이면 --owners에 추가한다")
        c, u = as_date(fm.get("created")), as_date(fm.get("updated"))
        for key, val in (("created", c), ("updated", u)):
            if fm.get(key) and not val:
                E(p, "E08", f"{key} `{fm.get(key)}`가 날짜가 아니다", "YYYY-MM-DD")
        if c and u and u < c:
            E(p, "E09", f"updated({u}) < created({c})", "updated를 실제 마지막 수정일로")

        rel = fm.get("related") or []
        if not isinstance(rel, list):
            E
            rel = []
        rel = [str(x).strip() for x in rel]
        selfp = [r for r in rel if cross.match(r) and cross.match(r).group(1) == repo.name]
        if selfp:
            W(p, "W11", f"related {', '.join('`' + r + '`' for r in selfp)} — 자기 저장소 이름을 접두로 썼다",
              f"이 저장소 안의 문서는 접두 없이 id만: {', '.join(cross.match(r).group(2) for r in selfp)}")
            rel = [cross.match(r).group(2) if r in selfp else r for r in rel]  # 접두를 벗겨 실제로 확인한다
        foreign = [r for r in rel if cross.match(r)]
        if foreign:
            W(p, "W07", f"related {', '.join('`' + r + '`' for r in foreign)} — 다른 저장소의 문서. 여기서는 존재를 확인하지 못한다",
              "그 저장소의 검사가 확인한다. 저장소 이름과 id에 오타가 없는지만 본다")
        for r in rel:
            if cross.match(r):
                continue
            if DOC_ID.match(r):
                if r not in known_ids:
                    E(p, "E11", f"related `{r}` — 그런 id를 가진 문서가 없다 (깨진 링크)",
                      "오타면 고친다. 회의록·리서치는 notes/ 아래에 있어야 한다")
            elif D_ID.match(r):
                if r not in d_defs:
                    E(p, "E12", f"related `{r}` — 백로그에 정의되지 않은 논점", "백로그에 `## D-NN.` 또는 `- **D-NN.`으로 먼저 등록한다 (규약 §2)")
            elif Q_ID.match(r):
                if r not in q_defs and r not in known_ids:
                    E(p, "E13", f"related `{r}` — 그런 질문이 없다", "`docs/questions/Q-NN.md` 파일을 먼저 만든다 (또는 추적성 매트릭스 §3 표의 `| Q-N |` 행)")
            elif r.endswith(".md") or "/" in r:
                if not ((repo / r).exists() or any((rt / r).exists() for rt in roots)):
                    E(p, "E14", f"related 경로 `{r}`가 존재하지 않는다", "경로 대신 문서 id를 쓴다 — id는 이관해도 깨지지 않는다")
            else:
                W(p, "W01", f"related `{r}` — 알 수 없는 형식", "문서 id(ADR-/RS-/DSN-/DOC-/POL-/SPEC-/M-) · 논점(D-) · 질문(Q-) 중 하나로")

        if t == "spec":  # R10 — 스펙은 정책서 없이 존재하지 않는다
            pols = [r for r in rel if re.fullmatch(r"(?:[a-z][a-z0-9-]*/)?POL-\d{2}", r)]
            if not pols:
                E(p, "E17", "스펙인데 related에 원천 정책서(POL-)가 없다", "규약 §5: `related: [product/POL-NN, …]` — 정책서 없이 스펙을 쓰지 않는다. 없으면 먼저 /ask product")
            else:
                for r in pols:  # 옆에 product가 있으면 원천의 상태까지 본다
                    pid = r.split("/")[-1]
                    pdir = repo.parent / "product" / "docs" / "policy"
                    src = next((q for q in pdir.glob("*.md") if re.search(rf"^id:\s*{pid}\s*$", q.read_text(encoding="utf-8-sig")[:400], re.M)), None) if pdir.is_dir() else None
                    if src is not None:
                        _, pfm, _ = load(src)
                        if pfm and pfm.get("status") in ("DRAFT", "REVIEW") and s == "ACCEPTED":
                            E(p, "E18", f"원천 {r}이 {pfm.get('status')}인데 스펙이 ACCEPTED", "규약 §3: 정책서가 확정되기 전에 스펙을 확정할 수 없다")
                        elif pfm and pfm.get("status") in ("DRAFT", "REVIEW"):
                            W(p, "W12", f"원천 {r}이 아직 {pfm.get('status')} — 이 스펙은 구현 근거가 아니다", "정책서 확정 뒤 다시 본다")

        age = (today - u).days if u else None
        if age is not None and t == "question":
            if s == "OPEN" and age > 7:
                W(p, "W09", f"질문이 OPEN인 채 {age}일 — 답이 없다", "그 저장소 소유자가 답하거나 NEEDS-DECISION으로 올린다. 회의 안건으로")
            if s == "NEEDS-DECISION" and age > 7:
                W(p, "W09", f"결정 대기 {age}일", "다음 회의 안건 첫머리에 올린다 (규약 §3)")
        elif age is not None and t not in LIVING_TYPES:
            if s == "DRAFT" and t != "meeting" and age > 14:
                W(p, "W02", f"DRAFT인 채 {age}일 (규약 §8: 14일)", "REVIEW로 올리거나 DROPPED로 닫는다")
            if s == "DRAFT" and t == "meeting" and age > 7:
                W(p, "W03", f"회의록이 DRAFT인 채 {age}일 (규약 §8: 7일)", "참석자 확인을 받아 ACCEPTED로. 이 회의의 ADR도 그때까지 DRAFT다 (규약 §3-5)")
            if s == "REVIEW" and age > 7:
                W(p, "W04", f"REVIEW인 채 최소 {age}일 (규약 §3: 이번 주 안에 결론)", "다음 회의 안건 첫머리에 올린다")

    # E16 — 본문의 상대 링크가 가리키는 파일이 없다 (코드 블록 안은 제외)
    for p, text in texts.items():
        body = FENCE.sub("", text)
        for target in LINK.findall(body):
            if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            path = target.split("#", 1)[0]
            if not path:
                continue
            dest = (p.parent / path).resolve()
            if dest.exists():
                continue
            if not dest.is_relative_to(repo):  # 옆 저장소(../product/…) — 이 체크아웃에는 없을 수 있다
                W(p, "W08", f"본문 링크 `{target}` — 다른 저장소의 파일. 여기서는 존재를 확인하지 못한다",
                  "저장소들이 옆에 클론돼 있으면 열린다. 확실히 하려면 `저장소/ID`로도 적는다")
                continue
            E(p, "E16", f"본문 링크 `{target}`가 가리키는 파일이 없다",
              "옆 저장소 문서는 `../../<저장소>/docs/…`로, 그 밖은 링크 대신 id로 적는다")

    # E15 — 저장소 모드에서 INDEX.md가 없거나 낡았다
    idx = root / "INDEX.md"
    if (repo / "scripts" / "gen_index.py").exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from gen_index import build
        fix = f"python3 <플러그인>/scripts/gen_index.py {a.roots[0]} --write"
        if not idx.exists():
            errs.append(f"E15  {a.roots[0]}/INDEX.md\n      목차가 없다 — CLAUDE.md가 이 파일을 불러온다\n      → {fix}")
        elif idx.read_text(encoding="utf-8-sig") != build(root):
            errs.append(f"E15  {idx.relative_to(repo).as_posix()}\n      목차가 문서 프론트매터와 어긋난다 (새 문서·상태 변경 후 미갱신)\n      → {fix}")

    owners = Counter(re.sub(r"\s*\(.*?\)\s*", "", str(fm.get("owner") or "")).strip() for fm in docs.values())
    if len(docs) >= 5:  # 문서가 몇 개뿐인 새 저장소는 쏠림이 자연스럽다
        top, n = owners.most_common(1)[0]
        if n / len(docs) > 0.8:
            warns.append(f"W05  (전체)\n      owner 쏠림 — {len(docs)}건 중 {n}건이 `{top}` ({n*100//len(docs)}%)\n"
                         f"      → 규약 §8: 설계 문서 owner를 워크숍에서 분산한다")

    print(f"docs_check · {len(files)}개 파일 ({' + '.join(r.name for r in roots)}) · 기준일 {today} · 제외 {a.exclude}")
    print(f"  정의된 논점 D- {len(d_defs)}개 · 질문 Q- {len(q_defs)}개 · 문서 id {len(known_ids)}개\n")
    for line in errs + warns:
        print(line)
    print(f"\n오류 {len(errs)} · 경고 {len(warns)}")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
