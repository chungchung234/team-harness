---
name: status
description: 사람용 현황판 docs/STATUS.md를 다시 쓴다 — 이번 주 바뀐 문서, 열린 질문, 오래된 DRAFT, 다음 회의 안건. 주 1회 또는 회의 전에 쓴다. 에이전트는 이 파일을 읽지 않는다(목차는 INDEX.md). "이번 주 현황", "회의 전에 정리해 줘"에 쓴다.
---

1. 재료: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docs_check.py" docs notes`(경고 = 오래된 DRAFT·REVIEW, 답 없는 질문) · `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/questions.py"` · `git log --since="7 days ago" --name-only -- docs notes` · `docs/INDEX.md`.
2. 먼저 `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/gen_index.py" --team --write`로 팀 현황(저장소 가로지른)을 새로 만들고 `.claude/TEAM.md`(세션 시작 훅이 둔 사본; 없으면 `../TEAM.md`)를 읽는다 — 내 저장소만 보고 쓰지 않는다.
3. `docs/STATUS.md`를 다시 쓴다 (프론트매터 유지, `updated` 오늘). 절: **이번 주 바뀐 것**(문서·상태 변화 — 내 저장소와 읽는 저장소, `.claude/TEAM.md`에서) · **최근 결정**(결정 기록)  · **결정 대기**(NEEDS-DECISION 질문, REVIEW 문서) · **늦은 것**(W02·W03·W04·W09 경고를 사람 말로) · **다음 회의 안건**(위에서 결정이 필요한 것 순서대로) · **문서 목록**은 쓰지 않는다 — INDEX.md가 있다.
4. 숫자는 재료에서만. 추정하지 않는다. 브랜치에 커밋 → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "<이슈키> STATUS <날짜>"`.

보고: 결정 대기 건수, 늦은 것 건수.
