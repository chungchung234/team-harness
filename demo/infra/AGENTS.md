# infra — 환경·배포

환경(IaC)·배포 파이프라인·런북. 코드와 분리해 권한을 좁힌다.

## 규칙 세 줄
사람은 지시하고 승인한다. 쓰는 것은 에이전트다. 자기 저장소에 쓰고, 남의 저장소는 읽고 질문한다.

## 이 저장소 — 소유: 백엔드 (착수 시) → 플랫폼 담당이 생기면 이관
- 제공하는 것: 배포 대상 저장소(backend·agent·frontend)의 환경. 런북(`docs/runbooks/`)
- 목차는 맨 아래에서 불러오는 `docs/INDEX.md`(생성물). 필요한 문서만 경로로 연다. 전부 읽지 않는다. 맨 위 "최근 결정"이 이 저장소에서 정해진 것.
- `iac/`
- `docs/runbooks/`  장애 대응 — 에이전트가 읽고 1차 대응한다
- `docs/decisions/`  인프라 ADR (환경 분리, 비밀 관리)
- `docs/questions/`
- 남이 이 저장소에 묻는 질문은 `docs/questions/Q-NN.md`에 온다. 세션 시작 알림에 "답할 질문"이 보이면 `/core:answer`부터.
- 프로덕션 비밀은 이 저장소에도 두지 않는다. 비밀 관리 방식은 첫 ADR이다.

## 읽는 저장소 — 옆 폴더, `.claude/settings.json`에 열려 있다
- `../backend/` — 배포 단위. 목차: `../backend/docs/INDEX.md`
- `../agent/` — 서빙 요구. 목차: `../agent/docs/INDEX.md`
- `../frontend/` — 정적 배포·CDN. 목차: `../frontend/docs/INDEX.md`
- `../memo/` — 팀원들의 메모·회고 — 생각이지 근거가 아니다. 사람 폴더 `people/<이름>/`, 회고 `retro/`. 목차 없음 — 세션 시작 `[메모]` 줄이 바뀐 것을 알린다
계약을 바꾸고 싶거나 문서가 모호하면 **그 저장소의** `docs/questions/`에 `/core:ask`로 묻는다. 추측으로 채우지 않는다.
다른 저장소의 문서를 `related`에 적을 때는 `저장소/ID`로 쓴다. 양식은 `../product/docs/templates/`.

## 이 저장소가 쓰는 하네스
플러그인 `core@team-harness`(계약 층 — 훅·스크립트·코어 스킬) + `infra@team-harness`(이 역할의 스킬). `.claude/settings.json`의 `enabledPlugins`에 선언돼 있다 — 설치 안 됐다는 안내가 뜨면 `claude plugin install infra@team-harness`(코어는 의존성으로 따라온다).

<!-- harness:common start — 이 블록은 harness/sync.py가 갱신한다 -->
## 공통 규칙
전 저장소 공통 규칙(맥락·소통·문서·git·검사)은 **core 플러그인이 세션 시작에 컨텍스트에 넣는다** — 원문 `harness/plugins/core/RULES.md`. 이 파일에는 이 저장소의 지도만 둔다.
이 저장소가 쓰는 플러그인은 `.claude/settings.json`의 `enabledPlugins`에 있다. 설치 안 됐다는 안내가 뜨면 `claude plugin install <이름>@team-harness`.
<!-- harness:common end -->

## 커밋·브랜치
- 커밋 메시지에 Jira 이슈 키 `KEY-123 설명`. 브랜치 `feature/KEY-123-짧은-설명`. 키 없는 커밋은 훅이, 키 없는 푸시는 저장소 설정이 거부한다.
<!-- KEY는 셋업 때 실제 Jira 프로젝트 키로 바꾼다. 남아 있으면 PR 파이프라인이 실패한다. -->

@docs/INDEX.md
