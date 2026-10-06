#!/usr/bin/env python3
"""memo — 아직 결정도 문서도 아닌 것을 memo 저장소의 내 폴더에 적고 바로 올린다. 저장소 밖(개인 노트·메신저)에 남기지 않기 위한 가장 가벼운 길.

    python3 memo.py add "이탈 임계 3회가 너무 빡빡한 것 같다 — 내일 기획에 물어볼 것"      # people/<나>/2026-10-01.md 에 시각과 함께 붙인다
    python3 memo.py add "..." --topic 이탈-임계                                           # people/<나>/이탈-임계.md 에 붙인다 (주제 파일)
    python3 memo.py add "..." --retro 2026-10-sprint-1                                     # retro/2026-10-sprint-1.md (팀 회고 — 누구나 쓴다)
    python3 memo.py recent [--who 홍길동] [-n 10]                                             # 최근 메모 (파일·첫 줄)
    python3 memo.py add "..." --to 조사/LLM-폴백.md                                        # 내 폴더 안의 내가 정한 자리 (폴더 구조는 각자 자유)
    python3 memo.py tree [--who 홍길동]                                                      # 그 사람 폴더의 구조와 README 첫 줄
    python3 memo.py add "..." --no-push                                                    # 커밋만 (시험용)

- **내 폴더 안의 구조는 각자 자유다.** 고정은 맨 위 둘뿐 — `people/<이름>/`(누구의 것인가, 피드가 이것으로 센다)·`retro/`. 그 아래는 사람마다 다르게 둔다. 구조를 남이(에이전트가) 알게 하려면 `people/<이름>/README.md`에 한두 줄로 적는다 — `/core:note`는 그것을 먼저 읽고 따른다.

- memo 저장소는 work/ 아래 옆 폴더 `../memo`(없으면 `/core:init add memo`). `--repo` 로 바꿀 수 있다.
- 나 = HARNESS_ME 환경변수(있으면) → `git config user.name`. 둘 다 없으면 멈추고 묻는다. `/core:init --user`가 settings.local.json 의 env 에 HARNESS_ME 를 넣을 수 있다.
- 커밋 메시지 `memo: <첫 50자>` — 이슈 키 없음(원자료 저장소는 훅이 요구하지 않는다). main 에 바로 올린다: pull --rebase 뒤 push. 원격이 없으면 커밋만.
- 양식 없음. 한 줄이면 한 줄. 사람이 나중에 읽을 수 있으면 된다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def git(repo: Path, *args, check=False):
    r = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"git {' '.join(args)} 실패: {r.stderr.strip()[-200:]}")
    return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()


def find_repo(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    here = Path.cwd().resolve()
    for cand in [here, *here.parents]:
        if (cand / ".claude" / "harness.json").exists():
            if (cand / "people").is_dir() and (cand / "retro").is_dir():   # memo 안에서 불렀다
                return cand
            sib = cand.parent / "memo"
            if sib.is_dir():
                return sib
            break
    for cand in [here, *here.parents]:   # 하네스 표식이 없는 폴더(빈 clone 등)에서 불러도 옆에 memo가 있으면 쓴다
        sib = cand.parent / "memo"
        if (sib / ".git").exists() and (sib / "people").is_dir():
            return sib
    sys.exit("memo 저장소를 찾지 못했다 — 옆 폴더 `../memo`가 없다. `/core:init add memo` 로 받는다 (저장소가 아직 없으면 하네스 담당이 `remote.py create memo` → `setup memo --mode direct`).")


def me(repo: Path) -> str:
    name = os.environ.get("HARNESS_ME", "")
    if not name:
        code, name, _ = git(repo, "config", "user.name")
        name = name if code == 0 else ""
    name = re.sub(r"[\\/:*?\"<>|\s]+", "-", name.strip())
    if not name:
        sys.exit("내 이름을 모른다 — `git config --global user.name '홍길동'` 또는 HARNESS_ME 환경변수. 사람에게 묻는다.")
    return name


def add(a) -> int:
    repo = find_repo(a.repo)
    text = a.text.strip()
    if not text:
        sys.exit("적을 내용이 비었다")
    today = dt.date.today().isoformat()
    now = dt.datetime.now().strftime("%H:%M")
    if a.retro:
        path = repo / "retro" / f"{re.sub(r'[^0-9A-Za-z가-힣._-]+', '-', a.retro)}.md"
        header = f"# 회고 — {a.retro}\n\n"
    elif a.to:
        who = me(repo)
        mine = (repo / "people" / who).resolve()
        rel_to = a.to if a.to.endswith(".md") else a.to + ".md"
        path = (mine / rel_to).resolve()
        if mine not in path.parents:
            sys.exit(f"내 폴더 밖이다 — `--to`는 people/{who}/ 안의 상대 경로만. 남의 폴더에는 쓰지 않는다")
        header = f"# {who} — {Path(rel_to).stem}\n\n"
    else:
        who = me(repo)
        fname = (re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", a.topic) if a.topic else today) + ".md"
        path = repo / "people" / who / fname
        header = f"# {who} — {a.topic or today}\n\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", encoding="utf-8") as f:
        if new:
            f.write(header)
        stamp = f"- **{today} {now}**" if (a.topic or a.retro or a.to) else f"- **{now}**"
        f.write(f"{stamp} {text}\n")
    rel = path.relative_to(repo)
    first = text.splitlines()[0][:50]
    git(repo, "add", str(rel), check=True)
    code, _, err = git(repo, "commit", "-q", "-m", f"memo: {first}")
    if code != 0:
        sys.exit(f"커밋 실패: {err[-200:]}")
    pushed = ""
    if not a.no_push:
        rc, _, _ = git(repo, "remote", "get-url", "origin")
        if rc == 0:
            _, br, _ = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
            git(repo, "pull", "--rebase", "-q", "origin", br or "main")
            pc, _, perr = git(repo, "push", "-q", "-u", "origin", "HEAD")
            pushed = " · 올렸다" if pc == 0 else f" · ⚠️ push 실패({perr[-120:]}) — 다음 세션 시작 훅이 다시 시도하지 않는다, `git -C ../memo push`"
        else:
            pushed = " · (원격 없음 — 커밋만)"
    print(f"적었다 {rel}{pushed}")
    return 0


def recent(a) -> int:
    repo = find_repo(a.repo)
    base = repo / "people" / a.who if a.who else repo
    files = sorted((p for p in base.rglob("*.md") if ".git" not in p.parts), key=lambda p: p.stat().st_mtime, reverse=True)[: a.n]
    if not files:
        print("메모 없음"); return 0
    for p in files:
        lines = [l for l in p.read_text(encoding="utf-8", errors="ignore").splitlines() if l.startswith("- ")]
        last = lines[-1][:100] if lines else ""
        print(f"{p.relative_to(repo)}  ({len(lines)}건)  {last}")
    return 0


def tree(a) -> int:
    repo = find_repo(a.repo)
    who = a.who or me(repo)
    base = repo / "people" / who
    if not base.is_dir():
        print(f"people/{who}/ 없음"); return 0
    rd = base / "README.md"
    if rd.exists():
        lines = [l for l in rd.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
        print("README: " + (lines[0][:160] if lines else "(비어 있음)"))
    for p in sorted(base.rglob("*")):
        if ".git" in p.parts or p.name == ".gitkeep":
            continue
        depth = len(p.relative_to(base).parts) - 1
        print("  " * depth + (p.name + "/" if p.is_dir() else p.name))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", help="memo 저장소 경로 (기본: 옆 폴더 ../memo)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add"); s.add_argument("text"); s.add_argument("--topic"); s.add_argument("--retro"); s.add_argument("--to", help="내 폴더 안의 상대 경로 (구조는 각자 자유)"); s.add_argument("--no-push", action="store_true"); s.set_defaults(fn=add)
    s = sub.add_parser("tree"); s.add_argument("--who"); s.set_defaults(fn=tree)
    s = sub.add_parser("recent"); s.add_argument("--who"); s.add_argument("-n", type=int, default=10); s.set_defaults(fn=recent)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
