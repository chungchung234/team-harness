---
name: spec
description: 정책서(product/POL-NN)를 받아 이 저장소의 스펙(docs/specs/SPEC-NN)을 양식대로 쓴다. 정책서가 답하지 않는 것은 추측하지 않고 /ask로 묻는다. "스펙 써줘", "POL-01 구현 스펙"에 쓴다.
argument-hint: '<product/POL-NN> "<스펙 제목>"'
---

1. `policy-digest` 서브에이전트에게 정책서 id와 주제를 주고 조항·수용 기준·"없는 것"을 받는다. 정책서 `status`가 `DRAFT`·`REVIEW`면 **여기서 멈추고** 사람에게 알린다 — 초안 위에 스펙을 쓰지 않는다 (규약 §3). 사람이 "그래도 진행"이라고 하면 스펙 머리에 "⚠️ 원천 POL-NN이 DRAFT — 확정 전 재검토"를 쓴다.
2. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/new_doc.py" spec "<제목>" --related product/POL-NN,<관련 ADR·D->` — 프론트매터 `issues`에 이 작업의 Jira 키(`/dev:feature`가 만든 것)를 적는다. "다 됐어?"는 이 키로 Jira 상태를 읽어 답한다(`issue.py status`).
3. 양식의 절을 채운다:
   - **원천 정책과 대응**: 정책서 수용 기준 A1, A2… 한 줄마다 스펙의 구현과 테스트 한 개. **빠지는 A가 없어야** 한다.
   - **동작**: 입력→처리→출력. API면 `docs/api/openapi.yaml`의 경로만 가리킨다 — 스키마를 여기 다시 쓰지 않는다. OpenAPI를 바꿔야 하면 그것도 이 PR에 넣고 "계약 변경" 절에 적는다.
   - **계약 변경**: 소비하는 저장소(`frontend`·외부)가 있으면 그 저장소에 `/core:ask`로 알린다 — 바꾸기 전에.
   - **정책서에 물은 것**: "없는 것" 목록은 전부 `/core:ask product`로 만들고 여기 표에 `product/Q-NN OPEN`으로 적는다. 답을 지어서 채우지 않는다. 구현 중에 새로 발견한 빈틈도 같은 길로 올린다(RULES "돌아오는 길").
   - **하지 않는 것**: 정책서의 "하지 않는 것"을 그대로 잇고, 이 스펙이 다루지 않는 것을 더한다.
4. 검사는 훅이 돈다. 스펙은 `DRAFT`로 둔다. 브랜치 `feature/<이슈키>-spec-NN`에 커밋 → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "<이슈키> SPEC-NN <제목>" --body "원천 product/POL-NN · 대응 수용 기준 n건 · 열린 질문 m건"`. `ACCEPTED`는 사람이 회의에서.

보고: 스펙 경로, 대응한 수용 기준 수, 만든 질문 수.
