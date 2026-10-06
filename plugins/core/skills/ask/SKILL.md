---
name: ask
description: 다른 저장소의 문서가 모호하거나 없을 때 그 저장소의 docs/questions/에 질문 파일(Q-NN)을 양식대로 만들고 PR을 올린다. 정책·API·컴포넌트가 답하지 않는 것을 추측으로 채우기 직전에 쓴다.
argument-hint: '<저장소> "<질문 한 문장>"'
---

질문은 **답할 저장소에** 만든다. 정책이면 `product`, API면 `backend`, 에이전트 호출이면 `agent`, 컴포넌트·토큰이면 `ui`.

1. 먼저 그 저장소의 `../<저장소>/docs/INDEX.md`를 열어 **이미 답이 있거나 같은 질문이 `docs/questions/`에 있는지** 본다. 있으면 그 파일을 가리키고 끝낸다. 정책이면 `policy-digest` 서브에이전트에게 주제를 주고 "정책서에 없는 것" 목록을 받는다.
2. 그 저장소가 아직 없으면(`../<저장소>/`가 없다) **내 저장소** `docs/questions/`에 만들고 `owner`를 그 역할 이름으로, 제목 앞에 `[<저장소> 앞]`을 붙인다. 저장소가 생기면 `/core:init add`한 뒤 옮긴다. 있으면 만든다:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/new_doc.py" question "<질문 한 문장?>" --to ../<저장소> --asked-by <이 저장소 이름> --owner "<그 저장소 소유자, 모르면 비움>" --related <근거 문서들>
   ```
   `--related`: 그 저장소 안의 문서는 `POL-01`처럼, 다른 저장소 문서는 `backend/SPEC-03`처럼 `저장소/ID`.
3. 만들어진 파일의 절을 채운다 — **질문**(어느 문서 어느 문장이 모호한지), **왜 지금 필요한가**(이 답이 없으면 무엇을 못 만드는가), **묻는 쪽의 추정**(예/아니오로 끝낼 수 있게. 근거가 없으면 "없음"이라고 쓴다 — 수치를 지어내지 않는다). **회신** 절은 비워 둔다.
4. 검사는 저장 시 훅이 돈다. 오류가 돌아오면 고친다.
5. 그 저장소에서 PR을 올린다 (이 저장소가 아니다). 이슈 키가 없으면 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/issue.py" "<질문 제목>"`으로 만든다(exit 3이면 사람에게 묻는다):
   ```
   cd ../<저장소> && git checkout -b feature/<이슈키>-q-<번호> && git add docs/questions docs/INDEX.md && git commit -m "<이슈키> Q-NN <질문 요지>"
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "<이슈키> Q-NN <질문 한 문장>" --body "답: 이 파일의 회신 절에. 상태를 ANSWERED 또는 NEEDS-DECISION으로" --repo ../<저장소>
   ```
   `pr.py`가 푸시하고 PR을 만든다. 토큰이 없으면 링크를 출력한다 — 그 링크를 사람에게 보여준다(누르면 PR 화면이 채워져 있다).
6. 내 문서(스펙 등)에는 `related`에 `<저장소>/Q-NN`을 적고, 그 자리에 "Q-NN 답 대기"라고 쓴다. 답이 오기 전에는 구현 근거로 쓰지 않는다.

보고는 한 줄: 무엇을 어디에 만들었고 PR 링크.
