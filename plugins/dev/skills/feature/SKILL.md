---
name: feature
description: 신규 기능의 첫걸음. 정책서가 있는지 확인하고, 없으면 기획에 묻고, 있으면 Jira 에픽·이 저장소의 작업 이슈를 만들고 /spec으로 넘긴다. "이 기능 시작하자", "X 만들어야 해"에 쓴다.
argument-hint: '"<기능 한 줄>" [product/POL-NN]'
---

기능은 **정책서에서 시작**한다. 정책서 없는 기능은 만들지 않는다 — 수용 기준이 없으면 "됐다"를 판정할 수 없다.

1. **정책서 찾기.** `policy-digest` 서브에이전트에게 기능 한 줄을 주고 `../product/docs/INDEX.md`에서 해당 `POL-`을 찾게 한다.
   - 없다 → 이 저장소에서는 시작할 수 없다. `/core:ask product "<기능>의 정책서가 필요하다 — 규칙·수용 기준·범위 밖"`으로 묻고 멈춘다. 기획자는 `/product:policy`로 답한다.
   - `DRAFT`·`REVIEW`다 → 스펙 초안은 쓸 수 있지만 구현은 못 한다. 사람에게 알리고 3으로.
   - `ACCEPTED`다 → 2로.
2. **작업 만들기.** `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/issue.py" "<기능> — <이 저장소>" --type Task` (에픽이 필요하면 `--type Epic` 먼저, 그 키를 사람에게 보고). 키가 브랜치·커밋·PR의 이름이 된다.
3. **스펙.** `/dev:spec product/POL-NN "<기능>"` — 수용 기준 A1..An에 구현·테스트를 한 줄씩 대응. 빈 곳은 `/core:ask`. 계약(OpenAPI·에이전트 API·토큰)이 바뀌면 소비 저장소에 먼저 `/core:ask`.
4. **구현은 스펙이 소유자 승인을 받은 뒤.** 같은 이슈 키의 `feature/KEY-N-…` 브랜치에서: 수용 기준마다 테스트 먼저(A1 → test_A1), 코드, `pr.py`. 코드 PR의 설명 첫 줄은 `SPEC-NN A1~An 구현 · 테스트 n건`.
5. **끝.** 소유자가 `/core:approve`. 머지되면 Jira 이슈는 Done(사람 또는 Bitbucket 연동의 스마트 커밋 `KEY-N #done`). 스펙 `status`는 그대로 `DRAFT`/`ACCEPTED` — "구현됨"은 Jira의 상태이지 문서 상태가 아니다.

보고: 정책서 id·상태, 만든 이슈 키, 스펙 경로, 만든 질문 수.
