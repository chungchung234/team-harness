---
name: minutes
description: 회의 녹취·메모를 받아 회의록(notes/meetings/YYYY-MM-DD-주제.md)을 양식대로 만들고, 결정된 것은 백로그의 해당 D-NN에 반영해 PR 하나로 올린다. 회의 당일~익일에 참석자가 쓴다 (규약 R9). "회의록 써 줘", "오늘 회의 정리해 줘", 녹취를 붙여 넣으면 쓴다.
argument-hint: '"<주제>" [--date YYYY-MM-DD]'
---

주최 팀의 저장소에서 돈다 (기획 회의는 `product`, 개발 회의는 `backend`).

1. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/new_doc.py" meeting "<주제>" --date <회의 날짜> --related <논의된 D-NN들>`
2. 양식대로 채운다. 원칙: **말한 것을 적되 결정과 의견을 가른다.**
   - **결정**: "결정 #n: <한 문장>" — 누가 반대했는지, 반박 가능한지("잠정") 표시. 합의가 아니면 결정 칸에 넣지 않는다.
   - **액션**: 담당·기한. 담당이 안 정해졌으면 "(배정 대기)".
   - **논의**: 요지만. 수치·인용은 누가 말했는지와 함께. 출처가 불분명한 수치는 "(출처 미확인)".
   - **다음 회의로**: 결론 안 난 것.
3. **결정 기록** — 결정마다 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/decision_log.py" add "<요지 한 문장>" --source "M-YYYYMMDD #n" --affects D-NN,ADR-NNN --status 잠정 --date <회의 날짜>`. 회의록은 `notes/`라 목차에 없다 — 이 한 줄이 **다른 저장소의 에이전트가 이 결정을 알게 되는 유일한 경로**다(목차 맨 위 "최근 결정" + 다음 세션 피드 `[결정]`). 회의록이 `ACCEPTED`되면 같은 결정을 `--status 확정`으로 다시 붙인다(append-only). 잠정·방향에 그친 것은 "(잠정)"을 요지에 넣는다.
4. 백로그(`docs/02-의사결정-백로그.md`, product 회의면 `../backend/`의 것)의 각 `D-NN` 절에 `M-YYYYMMDD 확정 #n: 요지` 한 줄. 새 논점이 나왔으면 `D-NN`을 새로 등록하면서 번호를 부여한다 (백로그에서 마지막 번호+1).
5. 결정이 ADR급이면 이 자리에서 만들지 않고 "→ `/core:adr`로" 라고 액션에 적는다.
6. 회의록은 `DRAFT`, 참석자 확인 후 `ACCEPTED` (7일 안에 — 규약 §8). 검사는 훅이 돈다. 브랜치 `feature/<이슈키>-m-YYYYMMDD`에 커밋 → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "<이슈키> M-YYYYMMDD <주제> 회의록" --body "결정 n · 액션 m · 갱신 D-…"` — 회의록 + 결정 기록 + 백로그 한 PR.
7. 머지 뒤 확인 하나: 다른 저장소에서 새 세션을 열면 `[결정]`에 이 회의의 결정이 보여야 한다. 안 보이면 결정 기록에 안 붙은 것이다.

보고: 회의록 경로, 결정 수(결정 기록에 붙인 줄 수), 액션 수, 갱신한 D-NN 목록.
