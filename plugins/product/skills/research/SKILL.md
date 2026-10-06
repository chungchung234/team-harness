---
name: research
description: 이 세션에서 한 조사·비교·검증을 notes/research/RS-NN 문서로 남긴다. 웹 검색이나 문서 비교를 여러 번 한 뒤, 또는 사람이 "정리해 둬"라고 하면 쓴다. 대화에만 남기지 않는다.
argument-hint: "<조사 제목>"
---

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/new_doc.py" research "<제목>" --related <관련 D-NN, ADR, Q->`
2. 채운다: **질문**(무엇을 알려고 했나) · **찾은 것**(사실은 출처 URL과 함께, 날짜) · **판단**(사실과 분리해서, "우리 상황에서는") · **못 확인한 것** · **다음**(결정이 필요하면 D-NN, 물을 것은 Q-).
3. 출처 없는 수치는 쓰지 않는다. 출처가 커뮤니티 답변이면 그렇게 표시한다.
4. 브랜치에 커밋 → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "<이슈키> RS-NN <제목>"`. `notes/`는 목차에 오르지 않는다 — 결정에 쓰이려면 백로그의 D-NN이나 ADR에서 이 RS-를 `related`로 가리켜야 한다. 그 한 줄을 넣을 곳을 보고에 적는다.

보고: 경로, 근거로 가리켜야 할 D-NN/ADR.
