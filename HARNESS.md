# harness — 하네스의 원본: 모두가 같은 것을 알고, 같은 모양으로 일하게 하는 것

> **PoC 저장소(0.13.8)**: 이 저장소의 루트가 곧 마켓플레이스다(`/plugin marketplace add <owner>/<repo>`). `demo/`는 시연 저장소 일곱, `demo/try.py`가 로컬 원격으로 시연 환경을 만든다. 새 설정: `remotes.json`의 `marketplace`(저장소 settings의 extraKnownMarketplaces 소스 — 예 `{"source": "github", "repo": "owner/repo"}`)·`marketplace_add`(init이 `claude plugin marketplace add`에 넘기는 값), 환경변수 `HARNESS_BASE`·`HARNESS_MARKETPLACE`(init 덮어쓰기). 사람용 설명은 `README.md`, 철학은 `PHILOSOPHY.md`.

소유: 백엔드 — 정 담당자(하네스 담당) 책임제.
문서(정책서·규약·양식)는 여기 두지 않는다 — 그건 `product`다. 여기는 **동작**이다.
**v0.12부터 이 저장소는 Claude Code 플러그인 마켓플레이스다** (`team-harness`). 저장소에 복사본을 두지 않는다.

## 세 층

> 0.13: 저장소에 **`memo`**가 하나 더 있다 — 사람의 생각·회고를 두는 원자료 저장소(`people/<이름>/`·`retro/`, 잠금 없음, `harness.json` `raw: true`로 목차·형식 검사·이슈 키 훅이 꺼진다). 모든 저장소가 읽고 세션 시작에 `[메모]` 한 줄로 안다. 적는 길은 `/core:note` → `scripts/memo.py`. 철학 방침 ① "저장소 바깥은 없다"가 요구한 자리다. 0.13.1: `/core:init`이 `memo/people/<이름>/`을 만들고 `HARNESS_ME`를 적는다 — 사람이 폴더를 만들 일이 없다. 커밋 없는 원격은 '비어있음'으로 알리고 건너뛴다. **0.13.2**: UserPromptSubmit 훅 `prompt_check.py` — 대화 중에도 저장소가 바뀌면 다음 말에 `[지금]`으로 안다(T34 실측). `issue.py status/transition` — 구현 상태는 Jira에서 읽고 옮긴다.


| 층 | 무엇 | 어디 | 같아야 하나 |
|---|---|---|---|
| **계약** | 훅 3 · 스크립트 · 코어 스킬 10(`ask` `answer` `note` `approve` `adr` `minutes` `status` `init` `onboard` `catchup`) · 에이전트 2 · 공통 규칙 `RULES.md` | `plugins/core` | **반드시 같다** — 저장소끼리 대화하는 규칙 |
| **역할** | 기획 `policy` `research` / 개발 `feature` `spec` `bug` `research` `review-docs` / 프론트 `api-client` / 퍼블리셔 `tokens` `research` `review-docs` / 운영 `research` | `plugins/product` `dev` `frontend` `ui` `infra` (모두 `dependencies: ["core"]`, frontend는 `dev`) | **달라야 한다** — 그 역할이 하는 일 |
| **저장소 고유** | 지도 `AGENTS.md` · `.claude/settings.json`(`additionalDirectories` + `enabledPlugins`) · `.claude/harness.json`(버전·플러그인·ID 접두) · `bitbucket-pipelines.yml` · `.gitignore` · `CODEOWNERS` | 각 저장소 (`sync.py`가 만든다) | 저장소마다 다르다 |

```
.claude-plugin/marketplace.json   team-harness — 플러그인 여섯, source ./plugins/<name>
plugins/
  core/                       계약 층
    .claude-plugin/plugin.json
    hooks/hooks.json              PostToolUse(Write|Edit)→after_doc_edit · PreToolUse(Bash)→check_commit_msg · SessionStart→session_start   ← 반사. 항상 돈다
    hooks/*.py                    ${CLAUDE_PLUGIN_ROOT}/scripts 를 부른다
    scripts/                      docs_check · gen_index(목차 + 최근 결정 · --team 팀 현황) · decision_log · new_doc · questions · pr · issue · init · migrate · memo(메모 적기·올리기)   ← 손. 스킬·훅·CI가 같은 것을 부른다
    skills/<10>/SKILL.md           절차. 요청이 이 중 하나면 그대로. 본문은 python3 "${CLAUDE_PLUGIN_ROOT}/scripts/X.py"
    agents/                       policy-digest(haiku, 읽기만) · docs-reviewer(sonnet, 읽기+검사)   ← 격리
    templates/                    양식 3 사본 (product/docs/templates 가 없을 때 new_doc 의 예비)
    RULES.md                      공통 규칙 — session_start 가 세션 첫 컨텍스트에 넣는다 (AGENTS.md 에는 저장소 지도만)
  product/ dev/ frontend/ ui/ infra/
    .claude-plugin/plugin.json    dependencies
    skills/<역할 스킬>/
    scripts/ templates/           build.py 가 넣는 코어 사본 (역할 스킬이 ${CLAUDE_PLUGIN_ROOT} 로 부를 수 있게) — 손으로 고치지 않는다
repo-template/                    AGENTS.md.tmpl(지도 + "이 저장소가 쓰는 하네스" + 공통 블록은 포인터 세 줄) · product 초기 파일(용어집·양식 3)
build.py                          코어 scripts/·templates/ → 역할 플러그인 사본, VERSION → plugin.json·marketplace.json.  --check
sync.py                           new <저장소> / all / update <저장소들> — 저장소 고유 층만 만든다·고친다, v0.11 복사본은 지운다
remote.py · remotes.json          Bitbucket 저장소 생성·설정(브랜치 잠금·Pipelines) · 워크스페이스 주소·Jira
VERSION
```

## 어떻게 퍼지는가

- **사람**: `claude plugin marketplace add <이 저장소 주소>` → `claude plugin install core@team-harness` → 세션에서 `/core:init <역할>`(저장소 clone + 역할 플러그인 설치 + `memo/people/<이름>/`과 `HARNESS_ME`). 저장소의 `settings.json`에 `enabledPlugins`가 커밋돼 있어 그 저장소를 여는 사람에게 설치 안내가 뜬다(공식 문서). 자동 갱신은 제3자 마켓플레이스 기본 꺼짐 — `/plugin`에서 켠다.
- **세션**: Claude Code 터미널·데스크톱 앱·`claude -p`·**Cowork**(플러그인 스킬·훅·에이전트 로드 — 공식 표)가 같은 플러그인을 본다. claude.ai/code 클라우드 세션은 플러그인을 로드하지 않는다(그 세션은 이 하네스 밖).
- **CI**: `bitbucket-pipelines.yml`이 이 저장소를 태그(`HARNESS_REF`, 토큰 `HARNESS_TOKEN`)로 clone해 `plugins/core/scripts/gen_index.py`·`docs_check.py`를 돈다. 저장소마다 태그를 골라 갱신 시점을 정한다.
- **하네스가 바뀌면**: `python3 build.py` → PR → 머지 → 태그. 저장소에는 아무 변경이 없다. 저장소 고유 층(AGENTS 틀·settings·Pipelines)이 바뀔 때만 `python3 sync.py update ../product ../backend …` → 저장소마다 PR, **그 소유자가 승인**.

## 한 줄씩

- **훅이 하는 일**: 세션이 시작되면 공통 규칙을 넣고, 자기·읽는 저장소를 당기고, **지난 세션 이후 바뀐 문서와 새 결정을 알린다**(`[변경]`·`[결정]`, 상태는 `.claude/harness-state.json`), 팀 현황 `../TEAM.md`를 다시 만들고(`[팀]`), 답할 질문·열린 PR을 알린다 — 하네스 책임 1의 장치. 문서를 저장하면 목차를 다시 만들고 검사해서 오류가 있으면 그 `→` 지침을 에이전트에게 돌려준다(exit 2) — 옆 저장소에 쓴 파일도 그 저장소에서. 이슈 키 없는 커밋은 막는다.
- **스킬이 하는 일**: 사람이 매번 다시 말하던 절차를 담는다. `/core:ask`는 답할 저장소에 질문 파일을 만들고 그 저장소에 PR, `:answer`는 답할 수 있으면 `ANSWERED`·사람이 정할 것이면 `NEEDS-DECISION`, `:minutes`는 회의록 + 결정마다 `결정-기록.md` 한 줄, `/dev:spec`은 정책서의 수용 기준을 한 줄씩 대응하고 빈 곳은 `:ask`.
- **서브에이전트가 하는 일**: 정책서 여러 장을 읽어 조항만 뽑아 오기(주 대화의 컨텍스트 보호), PR 문서 검토(스크립트가 못 보는 초안 의존·원천 불일치).
- **스크립트가 하는 일**: 형식 검사(규약 §1·2·5·8, `.claude/harness.json`의 `prefixes`로 저장소별 ID 접두), 목차 생성, 양식+다음 번호로 새 문서, 결정 기록 append, 질문 현황, 10/1 이관.

## 검증

`claude plugin validate .` 마켓플레이스 + 플러그인 여섯 통과. `_검증기록/test_kit.py` **139건**(훅은 `CLAUDE_PLUGIN_ROOT`를 넣고 stdin JSON으로 단위 시험, `sync.py`·`build.py --check`·`init --no-plugins` 포함). 스킬·훅은 Claude Code headless로 실측 — `--plugin-dir`(T28) 그리고 로컬 git 마켓플레이스에서 `marketplace add` → `plugin install dev@team-harness`(코어 의존성 자동) → 설치본으로 훅·피드·스킬 로드(T29, `agent-trials-v0.12.md`). 실측하지 못한 것: 비공개 Bitbucket에서의 `add`(저장된 자격증명·프롬프트 없음), Cowork에서 플러그인 훅 실행.
