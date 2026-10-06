# ui — 디자인 시스템

토큰·컴포넌트 패키지. **원천은 Figma**이고 이 저장소는 그 코드 형태다. Figma는 MCP로 읽는다(`get_variable_defs` → 토큰, `get_design_context` → 컴포넌트).

## 규칙 세 줄
사람은 지시하고 승인한다. 쓰는 것은 에이전트다. 자기 저장소에 쓰고, 남의 저장소는 읽고 질문한다.

## 이 저장소 — 소유: 퍼블리셔
- 제공하는 것: npm 패키지 — frontend가 소비한다. 토큰(`tokens/`)·컴포넌트(`components/`)·접근성 규칙
- 목차는 맨 아래에서 불러오는 `docs/INDEX.md`(생성물). 필요한 문서만 경로로 연다. 전부 읽지 않는다. 맨 위 "최근 결정"이 이 저장소에서 정해진 것.
- `tokens/`  Figma 변수에서 생성 — 손으로 고치지 않는다
- `components/`
- `docs/decisions/`  디자인 시스템 ADR (브라우저 지원, 접근성 기준)
- `docs/questions/`  프론트가 묻는 곳
- 남이 이 저장소에 묻는 질문은 `docs/questions/Q-NN.md`에 온다. 세션 시작 알림에 "답할 질문"이 보이면 `/core:answer`부터.
- Figma 파일 링크와 마지막 동기화 시각을 `docs/FIGMA.md`에 적는다. 디자이너가 Figma를 바꾸면 이 저장소의 에이전트가 토큰을 재생성해 PR을 올린다 — 퍼블리셔가 시각 충실도를 승인한다.

## 읽는 저장소 — 옆 폴더, `.claude/settings.json`에 열려 있다
- `../product/` — 용어 — 컴포넌트 이름은 용어집을 따른다. 목차: `../product/docs/INDEX.md`
- `../memo/` — 팀원들의 메모·회고 — 생각이지 근거가 아니다. 사람 폴더 `people/<이름>/`, 회고 `retro/`. 목차 없음 — 세션 시작 `[메모]` 줄이 바뀐 것을 알린다
계약을 바꾸고 싶거나 문서가 모호하면 **그 저장소의** `docs/questions/`에 `/core:ask`로 묻는다. 추측으로 채우지 않는다.
다른 저장소의 문서를 `related`에 적을 때는 `저장소/ID`로 쓴다. 양식은 `../product/docs/templates/`.

## 이 저장소가 쓰는 하네스
플러그인 `core@team-harness`(계약 층 — 훅·스크립트·코어 스킬) + `ui@team-harness`(이 역할의 스킬). `.claude/settings.json`의 `enabledPlugins`에 선언돼 있다 — 설치 안 됐다는 안내가 뜨면 `claude plugin install ui@team-harness`(코어는 의존성으로 따라온다).

<!-- harness:common start — 이 블록은 harness/sync.py가 갱신한다 -->
## 공통 규칙
전 저장소 공통 규칙(맥락·소통·문서·git·검사)은 **core 플러그인이 세션 시작에 컨텍스트에 넣는다** — 원문 `harness/plugins/core/RULES.md`. 이 파일에는 이 저장소의 지도만 둔다.
이 저장소가 쓰는 플러그인은 `.claude/settings.json`의 `enabledPlugins`에 있다. 설치 안 됐다는 안내가 뜨면 `claude plugin install <이름>@team-harness`.
<!-- harness:common end -->

## 커밋·브랜치
- 커밋 메시지에 Jira 이슈 키 `KEY-123 설명`. 브랜치 `feature/KEY-123-짧은-설명`. 키 없는 커밋은 훅이, 키 없는 푸시는 저장소 설정이 거부한다.
<!-- KEY는 셋업 때 실제 Jira 프로젝트 키로 바꾼다. 남아 있으면 PR 파이프라인이 실패한다. -->

@docs/INDEX.md
