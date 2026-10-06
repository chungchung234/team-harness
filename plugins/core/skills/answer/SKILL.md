---
name: answer
description: 이 저장소에 들어온 질문(docs/questions의 OPEN)을 훑어, 이 저장소의 문서로 답할 수 있는 것은 회신을 써서 ANSWERED로, 사람의 결정이 필요한 것은 NEEDS-DECISION으로 올린다. 세션 시작 알림에 "답할 질문"이 보이면 쓴다.
---

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/questions.py"`로 답할 질문 목록을 본다. 하나씩:
2. 질문이 가리키는 문서를 **이 저장소에서** 찾는다 (`docs/INDEX.md` → 해당 문서). 세 갈래로 나눈다:
   - **문서에 답이 있다** → 회신 절에 답과 근거(문서 id와 대목, 원문 인용), "반영한 문서: 없음(이미 §n에 있음)"을 쓰고 `status: ANSWERED`. 사람이 정한 것이 아니라 **대신 답한 것**이므로 남긴다: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/answered.py" add Q-NN "<답 한 줄>" --basis "<POL-NN 규칙 n>"`. 근거를 댈 수 없으면 이 갈래가 아니다 — 아래 NEEDS-DECISION으로.
   - **문서가 침묵하지만 이 저장소 소유자가 정하면 되는 것**(용어 정의, 수치, 범위) → 회신 절에 "결정이 필요하면 무엇을:"을 한 줄로 쓰고 `status: NEEDS-DECISION`. 선택지가 둘이면 둘 다 적는다. **스스로 정하지 않는다.**
   - **다른 저장소가 답해야 한다** → 그 저장소에 `/core:ask`로 넘기고, 이 질문 회신 절에 "→ <저장소>/Q-NN으로 넘김"을 쓴다.
3. 답이 문서를 바꿔야 하면(정책서에 문장 추가 등) **사람이 정한 경우에만** 고친다 — 크기를 가르고(RULES "결정의 크기", `downstream.py`) 그에 따라 상태·결정 기록을 다룬다. 개정 이력에 한 줄, `updated` 갱신. 회신 절 "반영한 문서"에 경로와 절.
4. `updated`를 오늘로. 검사는 훅이 돈다.
5. 브랜치 `feature/<이슈키>-answers`에 커밋하고 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "<이슈키> Q-NN·Q-MM 회신" --body "…"`로 PR 하나. `NEEDS-DECISION`이 있으면 `--body` 첫 줄에 "**결정 필요**: Q-NN — <한 줄>" — 소유자가 이것만 보고 정할 수 있게. 이슈 키가 없으면 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/issue.py" "<작업 제목>"`으로 만든다(출력이 키다). exit 3이면(Jira 토큰 없음) 그때만 사람에게 묻는다.

**바로잡기** — 사람이 대신 답한 것(`[대신 답함]`)을 보고 "아니야"라고 하면:
1. 맞는 답을 묻는다(이미 말했으면 그대로). 사람이 아직 정하지 못하면 질문을 `NEEDS-DECISION`으로 되돌린다.
2. 질문 파일의 회신 절 끝에 "바로잡음(날짜): <맞는 답> — <누가 확인>"을 붙이고 `status: ANSWERED`(이미 `CLOSED`였어도 — 묻는 쪽이 다시 반영하도록), `updated` 갱신.
3. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/answered.py" correct Q-NN "<맞는 답>" --basis "<누가 확인>"` — 기록에 바로잡은 줄이 붙고, 이 질문에 기대는 다른 저장소 문서가 나온다.
4. 올린다(위 5와 같이). 그 문서들의 Claude는 다음 말에 바뀐 답을 알고(변경 알림), 티켓이 있으면 Jira가 그 주인을 부른다. 사람에게는 "바로잡았습니다 — <저장소>의 <문서>를 쓰는 쪽에 바뀐 답이 갑니다" 한 줄.

보고: 질문별 한 줄 (`Q-01 대신 답함 — POL-01 §2 인용` / `Q-02 NEEDS-DECISION — 탭 전환 포함 여부`).
