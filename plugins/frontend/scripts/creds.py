"""creds — 사람마다 하나인 자격증명 파일을 읽어 환경변수로 채운다. pr.py·issue.py·notify_impact.py가 import한다.

자리: `work/tokens.txt` — 저장소들의 **부모 폴더**(어느 git 저장소에도 속하지 않는다 → 커밋될 길이 없다).
이름을 점으로 시작하지 않는 `.txt`로 둔 것은 Finder·탐색기에서 보이고 메모장으로 바로 열리게 하려는 것.
형식: 한 줄에 `이름=값`. `#`은 주석. 따옴표 없이. 사람이 메모장으로 열어 붙여 넣는다 — 토큰이 대화를 지나지 않게.

    BITBUCKET_API_TOKEN=...      # 개인 Atlassian API 토큰, Bitbucket 범위
    JIRA_EMAIL=hong@example.com
    JIRA_TOKEN=...               # 개인 Atlassian API 토큰, Jira 범위

순서: 이미 있는 환경변수(CI의 저장소 변수, settings.local.json의 env) > 이 파일. 파일 위치는 HARNESS_CREDENTIALS로 바꿀 수 있다.
값은 어디에도 출력하지 않는다 — 있는지만 말한다.
"""
from __future__ import annotations

import os
from pathlib import Path

NAME = "tokens.txt"
OLD_NAMES: tuple = ()
KEYS = ("BITBUCKET_API_TOKEN", "JIRA_EMAIL", "JIRA_TOKEN", "BITBUCKET_TOKEN")
TEMPLATE = """# 하네스 — 내 자격증명. 이 파일은 저장소 밖(work/)에 있어 커밋되지 않는다.
# 대화창에는 붙여 넣지 않는다(대화 기록에 남는다). 이 파일에 붙여 넣고 저장한 뒤 Claude에게 "다 넣었어"라고만 말한다.
#
# 만드는 법 (둘 다 같은 페이지, 5분)
#   1. 브라우저로 https://id.atlassian.com/manage-profile/security/api-tokens 를 연다 (회사 계정으로 로그인)
#   2. "Create API token with scopes"(범위가 있는 API 토큰 만들기) → 이름(예: harness-bitbucket) · 만료일 → 앱에서 Bitbucket 선택
#      → 권한: 저장소 읽기·쓰기, 풀 리퀘스트 읽기·쓰기 → 만들기 → 나온 값을 복사해 아래 BITBUCKET_API_TOKEN= 뒤에
#   3. 한 번 더 "범위가 있는 API 토큰 만들기" → 앱에서 Jira 선택 → 권한: Jira 읽기·쓰기 → 아래 JIRA_TOKEN= 뒤에
#   4. JIRA_EMAIL= 뒤에는 회사 메일
#
# Bitbucket 범위(저장소 읽기·쓰기, PR 읽기·쓰기) — PR·승인·머지가 내 이름으로 남는다
BITBUCKET_API_TOKEN=
# Jira 범위(이슈 읽기·쓰기, 댓글) — 티켓·댓글·상태
JIRA_EMAIL=
JIRA_TOKEN=
"""


def find(start: Path | None = None) -> Path | None:
    env = os.environ.get("HARNESS_CREDENTIALS")
    if env:
        return Path(env)
    here = (start or Path.cwd()).resolve()
    for cand in [here, *here.parents]:
        for n in (NAME, *OLD_NAMES):
            f = cand / n
            if f.exists():
                return f
    return None


def read(path: Path) -> dict:
    out = {}
    try:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.split(" #", 1)[0].strip().strip('"').strip("'")
            if v:
                out[k.strip()] = v
    except Exception:
        pass
    return out


def load(start: Path | None = None) -> Path | None:
    """파일의 값을, 아직 없는 환경변수에만 채운다. 찾은 파일 경로를 돌려준다(없으면 None)."""
    p = find(start)
    if p:
        for k, v in read(p).items():
            os.environ.setdefault(k, v)
    return p


def ensure(work: Path) -> tuple[Path, bool]:
    """work/에 빈 양식을 만든다(이미 있으면 그대로). (경로, 새로 만들었나)."""
    p = work / NAME
    if p.exists():
        return p, False
    p.write_text(TEMPLATE, encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
    return p, True


def put(work: Path, values: dict) -> Path:
    """init에 넘겨받은 값(옛 방식)을 파일에 반영한다 — 대화로 받은 토큰은 폐기·재발급을 권한다."""
    p, _ = ensure(work)
    lines = p.read_text(encoding="utf-8").splitlines()
    for k, v in values.items():
        if not v:
            continue
        for i, l in enumerate(lines):
            if l.split("=", 1)[0].strip() == k:
                lines[i] = f"{k}={v}"; break
        else:
            lines.append(f"{k}={v}")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
