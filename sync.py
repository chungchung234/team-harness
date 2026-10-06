#!/usr/bin/env python3
"""sync — 저장소 골격을 만들고(new), 하네스가 바뀌었을 때 저장소에 **남아 있는 잔여 파일**만 갱신한다(update).

    python3 sync.py new  <name> --into ../work          # 새 저장소 골격 (product·backend·agent·frontend·ui·infra 중 하나)
    python3 sync.py all  --into ../kit                  # 여섯 전부 (킷 빌드)
    python3 sync.py update ../work/backend ../work/product   # 잔여 파일 갱신 — Pipelines · .gitignore · settings.json의 플러그인 선언 · harness.json

v0.12부터 스킬·훅·서브에이전트·스크립트는 저장소에 **복사하지 않는다** — 플러그인(core + 역할 플러그인)으로 온다.
저장소는 `.claude/settings.json`의 enabledPlugins로 "무엇을 쓰는지" 선언만 한다(프로젝트 범위 — 그 저장소를 여는 모든 사람에게 켜지고, 설치 안 된 사람에겐 설치하라고 알린다).
저장소에 남는 것: AGENTS.md(그 저장소의 지도만 — 공통 규칙은 core가 세션 시작에 넣는다) · settings.json · .gitignore · CODEOWNERS · bitbucket-pipelines.yml(하네스를 clone해서 검사) · .claude/harness.json · product의 양식.
하네스가 바뀌면 `harness` 저장소에 태그 하나 — 플러그인 갱신은 각자의 Claude Code가 받는다(자동 갱신 켬). update는 위 잔여 파일이 바뀌었을 때만.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text(encoding="utf-8").strip()
CORE = HERE / "plugins" / "core"
MARKET = "team-harness"
ROLE_PLUGIN = {"product": "product", "backend": "dev", "agent": "dev", "frontend": "frontend", "ui": "ui", "infra": "infra"}
ROLES = {"기획자": "product", "기획": "product", "백엔드": "backend", "프론트": "frontend", "퍼블리셔": "ui", "에이전트": "agent", "AI": "agent", "운영": "infra", "문서총괄": "harness"}
MARK_S, MARK_E = "<!-- harness:common start", "<!-- harness:common end -->"


def remotes() -> dict:
    return json.loads((HERE / "remotes.json").read_text(encoding="utf-8"))


def repos_json() -> str:
    """플러그인 scripts/repos.json — init.py·issue.py가 읽는다. 원격 주소·역할·읽는 저장소·Jira."""
    r = remotes()
    return json.dumps({"base": r["base"], "default_branch": r.get("default_branch", "main"), "jira": r.get("jira", {}),
                       "company_email_domain": r.get("company_email_domain", ""), "marketplace_add": r.get("marketplace_add", ""), "roles": ROLES, "reads": {n: [x for x, _ in rp["reads"]] for n, rp in REPOS.items()}}, ensure_ascii=False, indent=2) + "\n"


REPOS = {
    "memo": dict(
        owner="전원 (각자 자기 폴더) · 하네스 담당이 구조만", handle="@문서총괄", label="메모 — 사람의 생각·회고 (원자료, 근거 아님)",
        purpose="아직 결정도 문서도 아닌 것을 두는 곳 — 개인 메모, 회의 전 생각, 조사 중 발견, 스프린트 회고. **잠금이 없다**(PR 없이 바로 올린다). 여기 있는 것은 그 사람의 생각이지 팀의 결정이 아니다 — 읽고 인용할 수 있으나 근거로 쓰지 않는다. 근거가 되려면 `/core:catchup`으로 `docs/`에 올린다.",
        provides="없음 — 제공하는 계약이 없다. 모든 저장소가 읽는다",
        reads=[],
        dirs=["people/<이름>/  각자의 폴더 — **안의 구조는 각자 자유**(README의 \"내 폴더 지도\"에 적으면 `/core:note`가 따른다). 기본은 날짜 파일", "retro/  스프린트 회고·하네스 회의 — 팀이 함께 쓴다"],
        extra="- 양식·번호·상태 없음. 목차 없음. 검사는 시크릿 스캔만. 커밋 메시지에 이슈 키가 없어도 된다(`memo: …`).\n- 남의 폴더에 쓰지 않는다. 남의 메모에 할 말이 있으면 자기 메모에 쓰거나 그 사람에게 말한다.",
        mkdirs=["people", "retro"],
        codeowners={"retro/**": "@문서총괄"},
        raw=True,
    ),
    "product": dict(
        owner="기획", handle="@기획자", label="제품 기획 · 팀 공통",
        purpose="정책서·수용 기준·용어집·문서 규약을 담는다. **모든 팀이 읽는 저장소**다.",
        provides="정책서(`docs/policy/`) · 수용 기준 · 용어집(`docs/glossary.md`) · 문서 규약(`docs/03-문서관리-규약.md`) · 팀 공통 ADR",
        reads=[("memo", "팀원들의 메모·회고 — 생각이지 근거가 아니다")],
        dirs=["docs/policy/  정책서와 수용 기준 — `POL-NN`. 수용 기준은 검증 가능한 문장으로: \"~인 경우 시스템은 ~한다\"",
              "docs/glossary.md  용어집. 용어마다 별칭(한글·영문·약어). 개발·프론트는 PR로 제안한다",
              "docs/decisions/  팀 공통 ADR (한 팀에 갇히지 않는 결정 — API 스타일, 인증, 저장소 구성)",
              "docs/03-문서관리-규약.md  모든 저장소가 따르는 문서 규칙",
              "docs/templates/  전 저장소 공용 양식 — 여기만 고친다"],
        extra="- **질문에 답하는 것이 이 저장소의 절반이다.** 개발·프론트·에이전트 팀이 `docs/questions/`에 묻는다.",
        mkdirs=["docs/policy", "docs/questions", "docs/decisions", "docs/templates", "notes/meetings", "notes/research"],
        codeowners={"docs/policy/**": "@기획자", "docs/questions/**": "@기획자", "docs/glossary.md": "@기획자", "docs/decisions/**": "@기획자 @백엔드리드 @프론트리드", "docs/03-문서관리-규약.md": "@문서총괄"},
    ),
    "backend": dict(
        owner="백엔드", handle="@백엔드리드", label="Spring 백엔드",
        purpose="도메인·API·DB. Java 최신 LTS · Spring Boot · PostgreSQL.",
        provides="**OpenAPI** (`docs/api/openapi.yaml`) — 프론트와 외부가 소비한다. 바꾸면 `product`의 정책과 `frontend`의 클라이언트가 영향을 받는다",
        reads=[("product", "정책·수용 기준·용어"), ("agent", "에이전트 API — 면접관·평가 호출 계약"), ("memo", "팀원들의 메모·회고 — 생각이지 근거가 아니다")],
        dirs=["src/", "docs/api/openapi.yaml  제공 계약 — 이 파일이 원천이고 코드가 따른다", "docs/specs/  정책서를 받아 쓴 스펙 — `SPEC-NN`", "docs/decisions/  백엔드 ADR", "docs/02-의사결정-백로그.md · 04-추적성-매트릭스.md  백엔드 논점·추적", "notes/  회의록·리서치 원자료 (목차 밖)"],
        extra="- 프론트·외부가 이 저장소에 묻는 질문은 `docs/questions/`에 온다 — 주로 API에 관한 것이다.",
        mkdirs=["src", "docs/api", "docs/specs", "docs/decisions", "docs/design", "docs/questions", "notes/meetings", "notes/research"],
        codeowners={"docs/api/**": "@백엔드리드", "docs/specs/**": "@백엔드리드", "docs/decisions/**": "@백엔드리드", "docs/questions/**": "@백엔드리드", "notes/**": "@백엔드리드"},
    ),
    "agent": dict(
        owner="에이전트", handle="@에이전트리드", label="Python 에이전트 서버",
        purpose="면접관 에이전트·평가·시뮬레이션(디지털 트윈). AI팀의 분석 엔진을 호출한다(Q-3). **최종 합/불은 내리지 않는다** — 근거와 점수만 낸다.",
        provides="**에이전트 API** (`docs/api/`) — backend가 소비한다 · **프롬프트** (`docs/prompts/`) — 제품 행동을 정의하므로 기획이 리뷰한다 · 평가 세트(`docs/evals/`)",
        reads=[("product", "정책·수용 기준 — 면접관이 지켜야 할 규칙의 원천"), ("backend", "도메인 모델·용어"), ("memo", "팀원들의 메모·회고 — 생각이지 근거가 아니다")],
        dirs=["src/", "docs/api/  제공 계약", "docs/prompts/  프롬프트 원문 — 버전이 곧 제품 행동. 기획자가 CODEOWNERS로 리뷰", "docs/evals/  평가 세트와 결과 — 프롬프트를 바꾸면 돌린다", "docs/decisions/  에이전트 ADR", "notes/"],
        extra="- 면접 대화 기록은 소명 자료가 될 수 있다. 로그 형식을 바꾸는 변경은 ADR로 남긴다.",
        mkdirs=["src", "docs/api", "docs/prompts", "docs/evals", "docs/decisions", "docs/questions", "notes/meetings", "notes/research"],
        codeowners={"docs/api/**": "@에이전트리드", "docs/prompts/**": "@에이전트리드 @기획자", "docs/evals/**": "@에이전트리드", "docs/decisions/**": "@에이전트리드", "docs/questions/**": "@에이전트리드"},
    ),
    "frontend": dict(
        owner="프론트", handle="@프론트리드", label="화면",
        purpose="`apps/candidate`(응시자 — 검사·면접·영상) · `apps/admin`(관리자 — 검사 구성·전형 운영). 계약을 제공하지 않고 소비만 한다.",
        provides="화면. 제공 계약 없음 — `packages/api-client`는 `../backend/docs/api/openapi.yaml`에서 **생성**한다(손으로 쓰지 않는다)",
        reads=[("product", "정책·수용 기준·용어 — 화면 문구와 흐름의 원천"), ("backend", "OpenAPI → `packages/api-client` 생성"), ("ui", "디자인 토큰·컴포넌트 패키지"), ("memo", "팀원들의 메모·회고 — 생각이지 근거가 아니다")],
        dirs=["apps/candidate/ · apps/admin/", "packages/api-client/  생성물 — 편집 금지. 재생성 명령은 README", "docs/specs/  화면 스펙 — `SPEC-NN`. 어느 정책서(product/POL-NN)에서 왔는지 적는다", "docs/decisions/  프론트 ADR", "notes/"],
        extra="- API가 부족하면 `../backend/docs/questions/`에, 정책이 모호하면 `../product/docs/questions/`에, 컴포넌트가 없으면 `../ui/docs/questions/`에 묻는다. 세 곳을 헷갈리지 않는다.",
        mkdirs=["apps/candidate", "apps/admin", "packages/api-client", "docs/specs", "docs/decisions", "docs/questions", "notes/meetings", "notes/research"],
        codeowners={"apps/**": "@프론트리드", "docs/specs/**": "@프론트리드", "docs/decisions/**": "@프론트리드", "docs/questions/**": "@프론트리드", "packages/api-client/**": "@프론트리드"},
    ),
    "ui": dict(
        owner="퍼블리셔", handle="@퍼블리셔", label="디자인 시스템",
        purpose="토큰·컴포넌트 패키지. **원천은 Figma**이고 이 저장소는 그 코드 형태다. Figma는 MCP로 읽는다(`get_variable_defs` → 토큰, `get_design_context` → 컴포넌트).",
        provides="npm 패키지 — frontend가 소비한다. 토큰(`tokens/`)·컴포넌트(`components/`)·접근성 규칙",
        reads=[("product", "용어 — 컴포넌트 이름은 용어집을 따른다"), ("memo", "팀원들의 메모·회고 — 생각이지 근거가 아니다")],
        dirs=["tokens/  Figma 변수에서 생성 — 손으로 고치지 않는다", "components/", "docs/decisions/  디자인 시스템 ADR (브라우저 지원, 접근성 기준)", "docs/questions/  프론트가 묻는 곳"],
        extra="- Figma 파일 링크와 마지막 동기화 시각을 `docs/FIGMA.md`에 적는다. 디자이너가 Figma를 바꾸면 이 저장소의 에이전트가 토큰을 재생성해 PR을 올린다 — 퍼블리셔가 시각 충실도를 승인한다.",
        mkdirs=["tokens", "components", "docs/decisions", "docs/questions", "notes/research"],
        codeowners={"tokens/**": "@퍼블리셔", "components/**": "@퍼블리셔", "docs/**": "@퍼블리셔"},
    ),
    "infra": dict(
        owner="백엔드 (착수 시) → 플랫폼 담당이 생기면 이관", handle="@백엔드리드", label="환경·배포",
        purpose="환경(IaC)·배포 파이프라인·런북. 500여 고객사와 공채 시즌 트래픽을 받는 쪽이므로 코드와 분리해 권한을 좁힌다.",
        provides="배포 대상 저장소(backend·agent·frontend)의 환경. 런북(`docs/runbooks/`)",
        reads=[("backend", "배포 단위"), ("agent", "서빙 요구 — GPU·SLM 폴백"), ("frontend", "정적 배포·CDN"), ("memo", "팀원들의 메모·회고 — 생각이지 근거가 아니다")],
        dirs=["iac/", "docs/runbooks/  장애 대응 — 에이전트가 읽고 1차 대응한다", "docs/decisions/  인프라 ADR (환경 분리, 비밀 관리)", "docs/questions/"],
        extra="- 프로덕션 비밀은 이 저장소에도 두지 않는다. 비밀 관리 방식은 첫 ADR이다.",
        mkdirs=["iac", "docs/runbooks", "docs/decisions", "docs/questions", "notes/research"],
        codeowners={"iac/**": "@백엔드리드", "docs/runbooks/**": "@백엔드리드", "docs/decisions/**": "@백엔드리드"},
    ),
}


PIPELINES = """# 모든 PR과 main에서 문서를 검사한다. 실패 출력의 → 줄이 수정 지침이다.
# 검사 스크립트는 저장소에 없다 — 하네스(core 플러그인)를 태그로 clone해서 쓴다. HARNESS_TOKEN(저장소 액세스 토큰, 읽기)·HARNESS_REF(태그, 기본 main)는 저장소 변수.
# ⚠️ gitleaks 단계는 이 킷에서 실행 검증하지 못했다(이미지·플래그) — 첫 PR에서 확인. 의존성 캐시(M-a 결정 #3)는 코드 파이프라인이 생길 때 데브옵스와.
image: python:3.12-slim

definitions:
  steps:
    - step: &docs
        name: docs check + 이슈 키
        script:
          - python3 -m pip install --quiet pyyaml
          - git clone --quiet --depth 1 --branch "${HARNESS_REF:-main}" "https://x-token-auth:${HARNESS_TOKEN}@HARNESS_HOST/harness.git" .harness
          - python3 .harness/plugins/core/scripts/gen_index.py docs --write
          - python3 .harness/plugins/core/scripts/docs_check.py docs notes
          - echo "$BITBUCKET_BRANCH" | grep -Eq '^(main|master)$|^(feature|bugfix|hotfix)/[A-Z][A-Z0-9]+-[0-9]+-' || { echo "E90 브랜치 이름에 이슈 키가 없다 ($BITBUCKET_BRANCH) → feature/KEY-123-설명 형식으로 브랜치를 다시 만든다"; exit 1; }
          - if grep -qE '(^|[^A-Z])KEY-[0-9]' AGENTS.md; then echo "E91 AGENTS.md에 자리표시자 KEY가 남아 있다 → 실제 Jira 프로젝트 키로 바꾼다"; exit 1; fi

pipelines:
  pull-requests:
    "**":
      - step: *docs
      - step:
          name: secret scan
          image: zricethezav/gitleaks:latest
          script:
            - gitleaks detect --source . --no-git --redact --exit-code 1 || { echo "E92 시크릿이 들어 있다 → 키를 지우고 환경변수·시크릿 저장소로. 이미 푸시됐으면 키를 폐기한다"; exit 1; }
  branches:
    main:
      - step: *docs
      - step:
          name: 영향 알림 → Jira (push가 감지, Jira가 사람을 부른다 — 세션을 열 때까지 기다리지 않는다)
          script:
            - git clone --quiet --depth 1 --branch "${HARNESS_REF:-main}" "https://x-token-auth:${HARNESS_TOKEN}@HARNESS_HOST/harness.git" .harness
            - if [ -n "$JIRA_TOKEN" ] && [ -n "$JIRA_EMAIL" ]; then python3 .harness/plugins/core/scripts/notify_impact.py --ci --range "${BITBUCKET_COMMIT}~1..${BITBUCKET_COMMIT}" || echo "영향 알림 실패 — 다음 세션의 [영향]이 받는다"; else echo "JIRA_EMAIL·JIRA_TOKEN 저장소 변수 없음 — 영향 알림 건너뜀(세션 피드 [영향]만)"; fi
"""

GITIGNORE = "snapshot/\n__pycache__/\n*.pyc\n.env\n.claude/settings.local.json\n# 목차는 생성물 — 커밋하면 PR마다 충돌한다. 훅·init·CI가 만든다\ndocs/INDEX.md\n# 세션 피드 상태(지난 세션의 HEAD)·팀 현황 사본 — 각자 PC의 것\n.claude/harness-state.json\n.claude/TEAM.md\n# CI가 받는 하네스\n.harness/\n"
GITIGNORE_REQUIRED = ("docs/INDEX.md", ".claude/harness-state.json", ".claude/TEAM.md", ".claude/settings.local.json", ".harness/")


def ensure_gitignore(d: Path):
    gi = d / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    missing = [x for x in GITIGNORE_REQUIRED if x not in text.splitlines()]
    if missing:
        gi.write_text(text.rstrip("\n") + ("\n" if text else "") + "\n".join(missing) + "\n", encoding="utf-8")


PIPELINES_RAW = """# 메모 저장소 — 원자료. 검사는 시크릿 스캔뿐이다(형식·목차·이슈 키 없음). ⚠️ gitleaks 단계는 킷에서 실행 검증하지 못했다.
pipelines:
  default:
    - step:
        name: secret scan
        image: zricethezav/gitleaks:latest
        script:
          - gitleaks detect --source . --no-git --redact --exit-code 1 || { echo "E92 시크릿이 들어 있다 → 지우고 키를 폐기한다"; exit 1; }
"""


def _ws() -> str:
    import re as _re
    m = _re.search(r"bitbucket\.org/([^/]+)/", remotes().get("base", ""))
    return m.group(1) if m else "CHANGE-ME-workspace"


def pipelines_text() -> str:
    host = remotes()["base"].replace("https://", "").rstrip("/")   # 예: bitbucket.org/your-workspace
    return PIPELINES.replace("HARNESS_HOST", host)


def marketplace_source() -> dict:
    """remotes.json의 marketplace가 있으면 그것(예: GitHub {"source": "github", "repo": "owner/repo"}), 없으면 base + harness.git."""
    m = remotes().get("marketplace")
    if m:
        return m
    return {"source": "git", "url": remotes()["base"].rstrip("/") + "/harness.git"}


HARNESS_SCRIPTS = ("new_doc", "docs_check", "gen_index", "decision_log", "questions", "pr", "issue", "init", "memo", "notify_impact", "migrate_from_project")


def put_settings(d: Path, name: str):
    """settings.json — 읽는 저장소(additionalDirectories) + 플러그인 선언(enabledPlugins, 프로젝트 범위) + 마켓플레이스 알림."""
    sp = d / ".claude" / "settings.json"
    settings = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    if name in REPOS:
        settings.setdefault("permissions", {})["additionalDirectories"] = [f"../{x}" for x, _ in REPOS[name]["reads"]]
    # 스킬의 allowed-tools는 쓰지 않는다 — 모델이 부른 스킬에 allowed-tools가 있으면 본문이 로드되지 않았다(T35, 비대화형). 권한은 여기서 준다.
    # 하네스 스크립트·git은 묻지 않고 돈다 — 비개발자에게 "python3 … 허용?" 창이 뜨지 않게. 위험한 것(main 직접 push·force)은 서버의 브랜치 권한이 막는다
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    for rule in [f"Bash(python3 *scripts/{n}.py*)" for n in HARNESS_SCRIPTS] + ["Write(docs/**)", "Edit(docs/**)", "Write(notes/**)", "Edit(notes/**)", "Write(../*/docs/questions/**)", "Write(../memo/people/**)", "Edit(../memo/people/**)"] + [f"Bash(git {g}*)" for g in ("status", "log", "diff", "show", "fetch", "pull", "add", "commit", "checkout", "switch", "branch", "rev-parse", "push -u origin", "push -q -u origin", "rebase", "merge --ff-only", "stash", "-C")] + ["Bash(cd *)", "Bash(ls*)", "Bash(cat *)", "Bash(head *)", "Bash(grep *)", "Bash(find *)"]:
        if rule not in allow:
            allow.append(rule)
    deny = settings.setdefault("permissions", {}).setdefault("deny", [])
    for rule in ("Read(../tokens.txt)", "Read(**/tokens.txt)", "Bash(git push --force*)", "Bash(git push -f*)", "Bash(*tokens.txt*)", "Bash(find * -delete*)", "Bash(find * -exec*)"):   # 사람의 토큰 파일 — 에이전트는 열지 않는다(스크립트만 읽는다). ⚠️ 규칙 문법 실측 전
        if rule not in deny:
            deny.append(rule)
    settings.pop("hooks", None)   # v0.11까지의 저장소 훅 — 이제 플러그인이 갖는다
    plugs = {f"core@{MARKET}": True}
    if name in ROLE_PLUGIN:
        plugs[f"{ROLE_PLUGIN[name]}@{MARKET}"] = True
    settings["enabledPlugins"] = {**{k: v for k, v in settings.get("enabledPlugins", {}).items() if not k.endswith("@" + MARKET)}, **plugs}
    settings["extraKnownMarketplaces"] = {**settings.get("extraKnownMarketplaces", {}), MARKET: {"source": marketplace_source()}}   # ⚠️ 스키마 미검증 — 틀리면 이 키만 지운다
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def put_residual(d: Path, name: str):
    """저장소에 남는 잔여 파일 (new와 update가 같이 쓴다)."""
    ensure_gitignore(d)
    put_settings(d, name)
    raw = bool(REPOS.get(name, {}).get("raw"))
    (d / "bitbucket-pipelines.yml").write_text(PIPELINES_RAW.replace("CHANGE-ME-workspace", _ws()) if raw else pipelines_text(), encoding="utf-8")
    hj = d / ".claude" / "harness.json"
    old = json.loads(hj.read_text(encoding="utf-8")) if hj.exists() else {}
    if raw:
        old["raw"] = True   # 원자료 저장소 — 이슈 키 훅·목차·형식 검사 없음. 세션 피드는 [메모] 한 줄
    old.update({"harness": VERSION, "plugins": sorted(k.split("@")[0] for k in json.loads((d / ".claude" / "settings.json").read_text(encoding="utf-8"))["enabledPlugins"] if k.endswith("@" + MARKET))})
    old.setdefault("prefixes", {})   # D-29 — product가 자기 ID 체계를 정하면 여기: {"policy": "PO-\\d{3}"}
    old.pop("version", None); old.pop("skills", None)
    hj.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # v0.11까지의 복사본 정리: 지도 파일의 공통 블록은 짧은 안내로, 복사된 스킬·훅·에이전트·스크립트는 지운다
    cm = d / "AGENTS.md"
    if not cm.exists() and (d / "CLAUDE.md").exists() and (d / "CLAUDE.md").read_text(encoding="utf-8").strip() != "@AGENTS.md":
        (d / "CLAUDE.md").rename(cm)
    if cm.exists():
        t = cm.read_text(encoding="utf-8")
        if MARK_S in t and MARK_E in t:
            t = t[: t.index(MARK_S)] + common_pointer() + t[t.index(MARK_E) + len(MARK_E):]
            cm.write_text(t, encoding="utf-8")
    (d / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    for sub in (".claude/skills", ".claude/agents", ".claude/hooks"):
        p = d / sub
        if p.is_dir() and _is_harness_copy(p):
            shutil.rmtree(p)
    sc = d / "scripts"
    if sc.is_dir() and (sc / "docs_check.py").exists() and (sc / "gen_index.py").exists():
        for f in list(sc.glob("*.py")) + [sc / "repos.json"]:
            if f.exists():
                f.unlink()
        shutil.rmtree(sc / "__pycache__", ignore_errors=True)
        if not any(sc.iterdir()):
            sc.rmdir()


def _is_harness_copy(p: Path) -> bool:
    names = {x.name for x in p.iterdir()}
    return bool(names & {"ask", "answer", "approve", "policy-digest.md", "docs-reviewer.md", "session_start.py", "after_doc_edit.py"})


def common_pointer() -> str:
    return (MARK_S + " — 이 블록은 harness/sync.py가 갱신한다 -->\n"
            "## 공통 규칙\n"
            "전 저장소 공통 규칙(맥락·소통·문서·git·검사)은 **core 플러그인이 세션 시작에 컨텍스트에 넣는다** — 원문 `harness/plugins/core/RULES.md`. 이 파일에는 이 저장소의 지도만 둔다.\n"
            "이 저장소가 쓰는 플러그인은 `.claude/settings.json`의 `enabledPlugins`에 있다. 설치 안 됐다는 안내가 뜨면 `claude plugin install <이름>@" + MARKET + "`.\n"
            + MARK_E)


def new_repo(name: str, parent: Path):
    r = REPOS[name]
    d = parent / name
    if d.exists():
        sys.exit(f"이미 있다: {d} — update를 쓴다")
    (d / ".claude").mkdir(parents=True)
    (d / ".bitbucket").mkdir()
    for sub in r["mkdirs"]:
        (d / sub).mkdir(parents=True, exist_ok=True)
        (d / sub / ".gitkeep").touch()
    (d / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (d / ".bitbucket" / "CODEOWNERS").write_text("# 리뷰어 자동 지정 (Bitbucket Cloud: 제안까지. 강제는 브랜치 권한 + Pipelines). 셋업 때 @핸들을 실제 계정으로.\n" + "".join(f"{k:<28}{v}\n" for k, v in r["codeowners"].items()), encoding="utf-8")
    reads = "\n".join((f"- `../{x}/` — {why}. 사람 폴더 `people/<이름>/`, 회고 `retro/`. 목차 없음 — 세션 시작 `[메모]` 줄이 바뀐 것을 알린다" if REPOS.get(x, {}).get("raw") else f"- `../{x}/` — {why}. 목차: `../{x}/docs/INDEX.md`") for x, why in r["reads"]) or "- (없음 — 이 저장소가 원천이다. 필요하면 `backend`·`frontend`를 읽기로 열 수 있다)"
    dirs = "\n".join(f"- `{line.split('  ',1)[0]}`  {line.split('  ',1)[1]}" if "  " in line else f"- `{line}`" for line in r["dirs"])
    tmpl = (HERE / "repo-template" / ("AGENTS-memo.md.tmpl" if r.get("raw") else "AGENTS.md.tmpl")).read_text(encoding="utf-8")
    (d / "AGENTS.md").write_text(tmpl.format(name=name, label=r["label"], purpose=r["purpose"], owner=r["owner"], provides=r["provides"], dirs=dirs, extra=r["extra"], reads=reads,
                                              templates="`docs/templates/`" if name == "product" else "`../product/docs/templates/`",
                                              plugin=ROLE_PLUGIN.get(name, "core"), market=MARKET), encoding="utf-8")
    if name == "product":
        for f in (HERE / "repo-template" / "product").rglob("*"):
            if f.is_file():
                dst = d / f.relative_to(HERE / "repo-template" / "product")
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, dst)
    put_residual(d, name)
    if not r.get("raw"):
        subprocess.run([sys.executable, str(CORE / "scripts" / "gen_index.py"), "docs", "--write"], cwd=d, check=True, capture_output=True)
    return d


MEMO_READ_LINE = "- `../memo/` — 팀원들의 메모·회고 — 생각이지 근거가 아니다. 사람 폴더 `people/<이름>/`, 회고 `retro/`. 목차 없음 — 세션 시작 `[메모]` 줄이 바뀐 것을 알린다"


def ensure_memo_read(d: Path, name: str):
    """기존 저장소의 AGENTS.md(지도는 저장소 것이라 sync가 덮지 않는다)에 memo 읽기 한 줄만 없으면 넣는다 — 0.13."""
    cm = d / "AGENTS.md"
    if not cm.exists() or not any(x == "memo" for x, _ in REPOS.get(name, {}).get("reads", [])):
        return False
    t = cm.read_text(encoding="utf-8")
    if "`../memo/`" in t:
        return False
    marker = "## 읽는 저장소"
    if marker not in t:
        return False
    i = t.index(marker); j = t.index("\n", i) + 1
    cm.write_text(t[:j] + MEMO_READ_LINE + "\n" + t[j:], encoding="utf-8")
    return True


def update_repo(d: Path):
    d = d.resolve()
    raw = bool(REPOS.get(d.name, {}).get("raw"))
    if not ((d / "AGENTS.md").exists() or (d / "CLAUDE.md").exists()) or not ((d / "docs").is_dir() or raw):
        print(f"건너뜀 (저장소 아님): {d}")
        return
    put_residual(d, d.name)
    added = ensure_memo_read(d, d.name)
    print(f"갱신 {d.name} → harness {VERSION} (잔여 파일: Pipelines · .gitignore · settings 플러그인 선언 · harness.json{' · AGENTS.md에 memo 읽기 한 줄' if added else ''})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("name", choices=sorted(REPOS)); n.add_argument("--into", required=True)
    a_ = sub.add_parser("all"); a_.add_argument("--into", required=True)
    u = sub.add_parser("update"); u.add_argument("repos", nargs="+")
    a = ap.parse_args()
    (CORE / "scripts" / "repos.json").write_text(repos_json(), encoding="utf-8")   # 플러그인의 repos.json은 remotes.json에서 나온다
    if a.cmd == "new":
        print(new_repo(a.name, Path(a.into).resolve()))
    elif a.cmd == "all":
        parent = Path(a.into).resolve(); parent.mkdir(parents=True, exist_ok=True)
        for name in REPOS:
            new_repo(name, parent)
        print("generated:", ", ".join(REPOS), f"(harness {VERSION}, plugins core + {len(set(ROLE_PLUGIN.values()))} role plugins)")
    else:
        for r in a.repos:
            update_repo(Path(r))


if __name__ == "__main__":
    main()
