---
name: api-client
description: backend의 docs/api/openapi.yaml에서 packages/api-client를 다시 생성한다. 손으로 고치지 않는다. OpenAPI가 바뀌었다는 [변경]이 뜨거나, 프론트가 없는 엔드포인트를 쓰려 할 때. "API 바뀌었대", "클라이언트 다시 만들어"에 쓴다.
---

frontend 저장소에서 돈다.

1. `../backend/docs/api/openapi.yaml`이 있는지 본다. 없으면 만들지 않고 `/core:ask`로 backend에 묻는다 — "OpenAPI 계약이 아직 없다. 어떤 엔드포인트가 예정인가".
2. 있으면 생성기(팀이 정한 것 — 기본 `openapi-typescript`)로 `packages/api-client/`를 다시 만든다. 생성물은 손으로 고치지 않는다 — 다르게 필요하면 backend의 계약을 바꾸는 질문을 먼저.
3. 바뀐 시그니처로 깨지는 호출이 있으면 그 파일 목록을 보고한다. 고치는 것은 별도 `/dev:feature`·`/dev:bug`.
4. 커밋 `KEY-N api-client 재생성 (backend openapi <커밋 짧은 해시>)` → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "…"`.

보고: 원천 openapi 커밋, 바뀐 타입 수, 깨진 호출 파일.
