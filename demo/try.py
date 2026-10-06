#!/usr/bin/env python3
"""try — 이 PoC를 내 컴퓨터에서 바로 써 보는 시연 환경을 만든다. Bitbucket·Jira 없이, 원격도 로컬 폴더로 흉내 낸다.

    python3 demo/try.py                   # ~/team-harness-work 에 만든다
    python3 demo/try.py --work ~/시연      # 다른 곳에
    python3 demo/try.py --no-plugins      # Claude Code 플러그인 설치는 건너뛴다 (이미 설치했거나 시험만)

만드는 것:
  <work>/_원격/<저장소>.git    demo/의 저장소 일곱을 올려 둔 가짜 원격 (Bitbucket 대신)
  <work>/기획자/                김기획(예시)이 '처음이야, 기획자야'로 받은 모습 — product + memo
  <work>/백엔드/                이백엔드(예시)가 '처음이야, 백엔드야'로 받은 모습 — backend + product·agent·memo(읽기)
  <work>/프론트/                박프론트(예시)가 '처음이야, 프론트야'로 받은 모습 — frontend + product·backend·ui·memo(읽기)

받는 일은 하네스의 init.py가 한다(사람이 "처음이야"라고 말하면 에이전트가 부르는 바로 그 스크립트).
플러그인은 이 PoC 폴더를 마켓플레이스로 등록해 설치한다(`claude plugin marketplace add <이 폴더>`).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DEMO = Path(__file__).resolve().parent
ROOT = DEMO.parent                     # PoC 저장소 = 마켓플레이스
INIT = ROOT / "plugins" / "core" / "scripts" / "init.py"
REPOS = ["memo", "product", "backend", "agent", "frontend", "ui", "infra"]
PEOPLE = [("기획자", "김기획", "product"), ("백엔드", "이백엔드", "backend"), ("프론트", "박프론트", "frontend")]
DEMO_NOTE = """
## 시연 환경에서만

- 이 저장소는 시연용이다. 원격은 로컬 폴더(`_원격/`)이고 Bitbucket·Jira는 없다.
- **브랜치를 만들지 않고 PR도 없다.** main에서 바로 커밋하고 `pr.py "<이슈키> <제목>" --direct`로 올린다. "승인"을 기다리지 않는다(이 규칙이 스킬의 브랜치·PR 절차보다 앞선다).
- 티켓(Jira)이 없으므로 질문은 대화로 사람에게 묻는다. 티켓 번호 ORD-12·ORD-13은 예시다.
- 정책 변경을 올릴 때 이슈 키는 ORD-12를 쓴다(기획 티켓). 사람에게 묻지 않는다.
"""


def run(cmd, cwd=None, env=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"실패: {' '.join(map(str, cmd))}\n{r.stdout}\n{r.stderr}")
    return r


def git_env(name: str) -> dict:
    e = dict(os.environ)
    e.update(GIT_AUTHOR_NAME=name, GIT_COMMITTER_NAME=name,
             GIT_AUTHOR_EMAIL=f"{name}@example.com", GIT_COMMITTER_EMAIL=f"{name}@example.com")
    return e


def seed_remote(remotes: Path, name: str):
    bare = remotes / f"{name}.git"
    if bare.exists():
        return "있음"
    run(["git", "init", "--quiet", "--bare", "-b", "main", str(bare)])
    with tempfile.TemporaryDirectory() as td:
        w = Path(td) / name
        shutil.copytree(DEMO / name, w)
        # 플러그인 마켓플레이스를 이 PoC 폴더로
        sp = w / ".claude" / "settings.json"
        if sp.exists():
            s = json.loads(sp.read_text(encoding="utf-8"))
            s.setdefault("extraKnownMarketplaces", {})["team-harness"] = {"source": {"source": "directory", "path": str(ROOT)}}
            sp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ag = w / "AGENTS.md"
        if ag.exists():
            ag.write_text(ag.read_text(encoding="utf-8").rstrip() + "\n" + DEMO_NOTE, encoding="utf-8")
        env = git_env("시연준비")
        run(["git", "init", "--quiet", "-b", "main"], cwd=w)
        run(["git", "add", "-A"], cwd=w)
        run(["git", "commit", "--quiet", "-m", f"{name}: 시연 시작 상태"], cwd=w, env=env)
        run(["git", "remote", "add", "origin", str(bare)], cwd=w)
        run(["git", "push", "--quiet", "-u", "origin", "main"], cwd=w)
    return "만듦"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=str(Path.home() / "team-harness-work"))
    ap.add_argument("--no-plugins", action="store_true")
    a = ap.parse_args()
    if not shutil.which("git"):
        sys.exit("git이 없습니다. git을 설치한 뒤 다시 해 주세요.")

    work = Path(a.work).expanduser().resolve()
    remotes = work / "_원격"
    remotes.mkdir(parents=True, exist_ok=True)
    print(f"시연 환경: {work}")
    for n in REPOS:
        print(f"  원격 {n}: {seed_remote(remotes, n)}")

    for folder, name, _ in PEOPLE:
        d = work / folder
        d.mkdir(exist_ok=True)
        env = git_env(name)
        env.update(HARNESS_BASE=str(remotes) + "/", HARNESS_MARKETPLACE=str(ROOT),
                   HARNESS_NO_OPEN="1", HARNESS_OFFLINE="1", HARNESS_ME=name)
        cmd = [sys.executable, str(INIT), folder, "--name", name, "--work", str(d)]
        if a.no_plugins:
            cmd.append("--no-plugins")
        r = run(cmd, cwd=d, env=env, check=False)
        print(f"  {folder}({name}): " + " · ".join(
            l.strip().replace("  ", " ") for l in (r.stdout or "").splitlines()
            if l.strip().startswith(("clone", "있음", "메모", "실패", "비어있음", "플러그인", "마켓플레이스"))))
        if r.returncode != 0:
            print((r.stderr or r.stdout or "").strip()[-400:])
        (d / "tokens.txt").unlink(missing_ok=True)   # 시연에는 토큰이 필요 없다
        for repo in [p for p in d.iterdir() if (p / ".git").exists()]:
            run(["git", "config", "user.name", name], cwd=repo)
            run(["git", "config", "user.email", f"{name}@example.com"], cwd=repo)

    print(f"""
이제 이렇게 써 보세요 (Claude Code 창 세 개)

  1. 창 세 개를 엽니다 — 처음 열 때 '신뢰'를 한 번 누릅니다.
       기획자  {work / '기획자' / 'product'}
       백엔드  {work / '백엔드' / 'backend'}
       프론트  {work / '프론트' / 'frontend'}
  2. 기획자 창에서:  "주문 취소 정책에서 취소 가능 시간을 30분에서 1시간으로 바꿔 줘"
  3. 백엔드 창과 프론트 창에서 각각:  "지금 내 스펙 상태 어때?"
     → 기획자가 방금 바꾼 정책과, 그 정책에 기대고 있는 내 스펙이 영향을 받는다는 것을
       두 창의 Claude가 각각 먼저 말합니다. 아무도 전하지 않았습니다.

다시 처음부터 하려면 {work} 폴더를 지우고 이 스크립트를 다시 돌리면 됩니다.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
