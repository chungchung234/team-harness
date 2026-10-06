#!/usr/bin/env python3
"""SessionStart 훅 (core 플러그인) — (0) 공통 규칙(RULES.md)을 컨텍스트에 넣는다 (1) 자기 저장소와 읽는 저장소를 최신으로 당긴다 (2) **지난 세션 이후 바뀐 것**을 알린다 (3) 팀 현황 한 장을 만든다 (4) 답할 질문·회신 온 질문·열린 PR을 알린다.

사람이 git pull을 기억할 필요가 없게, 그리고 **회의에 없던 사람·읽지 않은 에이전트가 낡은 전제로 일하지 않게** 하기 위한 것이다.
규칙:
- 작업 트리가 깨끗하고 main/master에 있을 때만 `git pull --ff-only`. 아니면 건드리지 않고 한 줄 알린다.
- 읽는 저장소(settings.json의 additionalDirectories)는 어느 브랜치든 깨끗하면 ff-only pull. 실패해도 조용히 넘어간다(오프라인 등).
- 피드: 저장소마다 지난 세션의 HEAD를 `.claude/harness-state.json`(미추적)에 두고, 이번 HEAD까지의 docs·notes 커밋과 바뀐 문서를 알린다.
  결정 기록(docs/decisions/결정-기록.md)에 새 줄이 붙었으면 `[결정]`으로 따로. 첫 세션(상태 없음)은 지난 7일.
- 출력은 stdout → 에이전트 컨텍스트에 들어간다. 저장소마다 3줄 안, 전체 20줄 안. 없으면 아무것도 찍지 않는다.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)
SCRIPTS = PLUGIN_ROOT / "scripts"
RULES = PLUGIN_ROOT / "RULES.md"
STATE = root / ".claude" / "harness-state.json"
DECISION_LOG = "docs/decisions/결정-기록.md"
ROW = re.compile(r"^\+\|\s*(\d{4}-\d{2}-\d{2})\s*\|(.*?)\|(.*?)\|")


def git(repo, *args):
    try:
        r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=40)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:  # git 없음·타임아웃
        return 1, str(e)


def head(repo: Path):
    code, out = git(repo, "rev-parse", "HEAD")
    return out if code == 0 and re.fullmatch(r"[0-9a-f]{40}", out) else None


def pull(repo: Path, own: bool):
    if not (repo / ".git").exists():
        return None
    code, out = git(repo, "status", "--porcelain", "--untracked-files=no")  # 생성물(INDEX.md)은 막지 않는다
    if code != 0:
        return None
    if out.strip():
        return f"{repo.name}: 커밋되지 않은 변경이 있어 당기지 않았다" if own else None
    code, branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if own and branch not in ("main", "master"):
        return f"{repo.name}: 브랜치 {branch}에 있다 — 새 작업이면 main에서 새 브랜치를 만든다"
    code, remote = git(repo, "remote", "get-url", "origin")
    if code != 0:
        return None
    code, out = git(repo, "pull", "--ff-only", "--quiet")
    if code != 0:
        why = next((l for l in out.splitlines() if l.startswith("fatal") or l.startswith("error")), out.splitlines()[0] if out else "원인 미상")
        return f"{repo.name}: 당기지 못했다 ({why[:90]}) — 오프라인이면 그대로 진행. 아니면 하네스 담당에게" if own else None
    return None


def reindex(repo: Path):
    """목차는 커밋되지 않는 생성물 — 당긴 뒤 다시 만든다 (없으면 AGENTS.md의 @docs/INDEX.md가 빈다)."""
    g = SCRIPTS / "gen_index.py"
    if g.exists() and (repo / "docs").is_dir():
        subprocess.run([sys.executable, str(g), "docs", "--write"], cwd=repo, capture_output=True)


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except Exception:
        pass


def short(s: str, n: int) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def is_raw(repo: Path) -> bool:
    hj = repo / ".claude" / "harness.json"
    try:
        return bool(json.loads(hj.read_text(encoding="utf-8")).get("raw")) if hj.exists() else False
    except Exception:
        return False


def memo_feed(repo: Path, old: str | None, new: str | None):
    """원자료 저장소(memo) — 누가 몇 건 적었는지 한 줄. 내용은 열어야 안다(근거가 아니므로 피드에 싣지 않는다)."""
    if not new or old == new:
        return []
    rng = f"{old}..{new}" if old and git(repo, "cat-file", "-e", f"{old}^{{commit}}")[0] == 0 else "--since=7.days"
    code, out = git(repo, "log", "--no-merges", "--name-only", "--format=", rng)
    files = [l.strip() for l in out.splitlines() if l.strip() and (l.startswith("people/") or l.startswith("retro/")) and not l.strip().endswith(".gitkeep")] if code == 0 else []
    if not files:
        return []
    who: dict[str, int] = {}
    for f in files:
        parts = f.split("/")
        key = parts[1] if parts[0] == "people" and len(parts) > 2 else ("회고" if parts[0] == "retro" else parts[0])
        who[key] = who.get(key, 0) + 1
    summary = " · ".join(f"{k} {v}" for k, v in sorted(who.items(), key=lambda kv: -kv[1])[:6])
    sample = " ".join(f"../{repo.name}/{f}" for f in dict.fromkeys(files[:3]))
    return [f"[메모] {'첫 세션, 지난 7일' if rng.startswith('--since') else '지난 세션 이후'} {summary} — 생각이지 근거가 아니다. 열어 보려면 {sample}"]


def feed(repo: Path, old: str | None, new: str | None):
    """지난 세션(old) 이후 이번(new)까지 docs·notes에서 바뀐 것. 줄 목록을 돌려준다."""
    if not new or not (repo / ".git").exists():
        return []
    if is_raw(repo):
        return memo_feed(repo, old, new)
    if old == new:
        return []
    if old and git(repo, "cat-file", "-e", f"{old}^{{commit}}")[0] == 0:
        rng, first = f"{old}..{new}", False
    else:
        rng, first = "--since=7.days", True   # 첫 세션 또는 상태가 깨졌다
    code, log = git(repo, "log", "--no-merges", "--date=format:%m-%d", "--format=%ad %s", rng, "--", "docs", "notes")
    commits = [l for l in log.splitlines() if l.strip()] if code == 0 else []
    if not commits:
        return []
    lines = []
    subj = " · ".join(short(c, 60) for c in commits[:3]) + (" · …" if len(commits) > 3 else "")
    files = ""
    changed_paths = []
    if not first:
        code, ns = git(repo, "diff", "--name-status", old, new, "--", "docs")
        if code == 0 and ns.strip():
            fl = []
            for l in ns.splitlines():
                parts = l.split("\t")
                if len(parts) >= 2 and not parts[-1].endswith("INDEX.md"):
                    fl.append(f"{parts[-1].replace('docs/', '', 1)}({parts[0][0]})")
                    if parts[0][0] != "D" and parts[-1].endswith(".md"):
                        changed_paths.append(parts[-1])
            if fl:
                files = " | 파일: " + " ".join(fl[:6]) + (" …" if len(fl) > 6 else "")
    lines.append(f"[변경] {repo.name} — {'첫 세션, 지난 7일' if first else '지난 세션 이후'} 커밋 {len(commits)}: {subj}{files}")
    lines += impact(repo, new, changed_paths)
    # 결정 기록에 새 줄 — 첫 세션이면 지난 7일 날짜의 줄 (diff 대상이 없으므로 파일에서 직접)
    if not first:
        code, diff = git(repo, "diff", old, new, "--", DECISION_LOG)
        rows = diff.splitlines() if code == 0 else []
    else:
        import datetime as _dt
        since = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()
        p = repo / DECISION_LOG
        rows = ["+" + l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("|") and l[1:12].strip() >= since] if p.exists() else []
    for l in rows:
        m = ROW.match(l)
        if m and m.group(2).strip() and not m.group(2).strip().startswith("---") and m.group(1) != "날짜":
            lines.append(f"[결정] {repo.name}: {m.group(1)} {short(m.group(2), 90)} ({m.group(3).strip()})")
        if len(lines) >= 6:
            break
    return lines


ID_RE = re.compile(r"^id:\s*([A-Za-z]+-[0-9A-Za-z-]+)", re.M)
REL_RE = re.compile(r"^related:\s*\[(.*?)\]", re.M)


def impact(repo: Path, new: str, changed_paths: list[str]):
    """읽는 저장소에서 바뀐 문서를 `related`로 가리키는 내 문서 — 전제가 바뀐 문서를 훅이 짚어 준다(모델이 알아채길 기다리지 않는다)."""
    if repo == root or not changed_paths or not (root / "docs").is_dir():
        return []
    changed_ids = []
    for pth in changed_paths[:20]:
        code, head = git(repo, "show", f"{new}:{pth}")
        m = ID_RE.search(head[:1500]) if code == 0 else None
        if m and m.group(1) != "DOC-000":
            changed_ids.append(m.group(1))
    if not changed_ids:
        return []
    hits = []
    for f in sorted((root / "docs").rglob("*.md")):
        if f.name == "INDEX.md":
            continue
        try:
            head = f.read_text(encoding="utf-8", errors="ignore")[:2500]
        except OSError:
            continue
        rel = REL_RE.search(head)
        if not rel:
            continue
        refs = {x.strip().strip("'\"") for x in rel.group(1).split(",")}
        dep = [i for i in changed_ids if f"{repo.name}/{i}" in refs]
        if dep:
            mid = ID_RE.search(head)
            hits.append(f"{mid.group(1) if mid else f.stem}({f.relative_to(root)}) ← {repo.name}/{' '.join(dep)}")
    if not hits:
        return []
    return [f"[영향] 전제가 바뀐 내 문서 {len(hits)}: " + " · ".join(hits[:5]) + (" …" if len(hits) > 5 else "") + " — 반영 전에 바뀐 문서를 연다"]


def team(work: Path):
    """팀 현황 한 장(work/TEAM.md)을 다시 만들고 자기 저장소 .claude/TEAM.md 에도 사본을 둔다(에이전트는 work/ 를 읽을 권한이 없다 — T30). 전체 숫자 한 줄을 돌려준다. 저장소가 둘 이상일 때만."""
    g = SCRIPTS / "gen_index.py"
    if not g.exists():
        return None
    repos = [p for p in work.iterdir() if p.is_dir() and (p / "docs").is_dir() and not p.name.startswith(".")]
    if len(repos) < 2:
        return None
    r = subprocess.run([sys.executable, str(g), "--team", str(work), "--write"], cwd=root, capture_output=True, text=True, encoding="utf-8", timeout=60)
    if r.returncode != 0:
        return None
    try:
        text = (work / "TEAM.md").read_text(encoding="utf-8")
        (root / ".claude").mkdir(exist_ok=True)
        (root / ".claude" / "TEAM.md").write_text(text, encoding="utf-8", newline="\n")
        for l in text.splitlines():
            if l.startswith("**전체**"):
                return f"[팀] {l.replace('**전체** — ', '')} — 자세히는 `.claude/TEAM.md`"
    except Exception:
        pass
    return None


lines = []
# 공통 규칙 — 플러그인 루트의 CLAUDE.md는 로드되지 않으므로(공식 문서) 여기서 넣는다. 저장소 AGENTS.md에는 그 저장소의 지도만 있다.
if RULES.exists() and (root / "docs").is_dir():
    lines.append(RULES.read_text(encoding="utf-8").strip())
    lines.append(f"[스크립트] {SCRIPTS} — 하네스 스크립트는 여기 있다(python3 {SCRIPTS}/<이름>.py)")
state = load_state()
heads = state.get("heads", {})
old_own = heads.get(str(root))
msg = pull(root, own=True)
if msg:
    lines.append("[git] " + msg)
reindex(root)
new_own = head(root)
lines += feed(root, old_own, new_own)
if new_own:
    heads[str(root)] = new_own
try:
    settings = json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    for rel in settings.get("permissions", {}).get("additionalDirectories", []):
        sib = (root / rel).resolve()
        if not sib.is_dir():
            continue
        m = pull(sib, own=False)
        if m:
            lines.append("[git] " + m)
        reindex(sib)
        new_sib = head(sib)
        lines += feed(sib, heads.get(str(sib)), new_sib)
        if new_sib:
            heads[str(sib)] = new_sib
except Exception:
    pass
state["heads"] = heads
save_state(state)

t = team(root.parent)
if t:
    lines.append(t)

prs = SCRIPTS / "pr.py"
if prs.exists():
    try:
        r = subprocess.run([sys.executable, str(prs), "inbox", "--brief", "--repo", str(root)], capture_output=True, text=True, encoding="utf-8", timeout=40)
        if r.returncode == 0 and r.stdout.strip():
            lines.append(r.stdout.rstrip())
    except Exception:
        pass

q = SCRIPTS / "questions.py"
if q.exists():
    r = subprocess.run([sys.executable, str(q), "--brief", "--repo", str(root)], capture_output=True, text=True, encoding="utf-8")
    if r.stdout.strip():
        lines.append(r.stdout.rstrip())
if lines:
    sys.stdout.write("\n".join(lines[:40]) + "\n")
