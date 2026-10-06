---
name: adr
description: 결정 기록(docs/decisions/ADR-NNN)을 양식대로 쓴다. 회의에서 결정된 것, 또는 백로그 논점(D-NN)의 결정안을 문서로 만들 때 쓴다. 팀 공통 결정은 product에, 한 팀 결정은 그 저장소에. "이거 결정으로 남겨 줘", "결정했어 — 기록해"에 쓴다.
argument-hint: '"<결정 제목>" [D-NN]'
---

1. 어디에 쓰는가: 한 팀에 갇힌 결정(백엔드 DB 선택)은 이 저장소. 여러 저장소에 걸치는 결정(API 스타일, 인증, 저장소 구성)은 `--to ../product`.
2. 근거를 모은다: 백로그의 `D-NN` 절(선택지·판단 기준), 관련 회의록(`notes/meetings/` grep), 관련 리서치. 회의록이 `DRAFT`면 ADR도 `DRAFT`를 벗어날 수 없다 (규약 §3-5) — 머리에 적는다.
3. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/new_doc.py" adr "<제목>" --related D-NN,M-YYYYMMDD [--to ../product]`
4. 양식대로: 배경(제약을 사실로) · 검토한 선택지(각 장단점 — 백로그 표를 옮기되 회의에서 바뀐 것을 반영) · 결정 · 결과와 대가 · **재검토 신호**(전제 질문이 `OPEN`이면 반드시). 결정 문장은 하나, 명사구로 제목과 같게.
5. 기존 ADR을 바꾸는 결정이면 옛 ADR 본문은 건드리지 않고 새 ADR에 `supersedes: ADR-OLD`, 옛 것에 `superseded_by`만 추가.
6. **결정 기록** — `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/decision_log.py" add "<결정 문장>" --source "ADR-NNN" --affects D-NN --status 잠정` (ADR이 있는 저장소에서). ADR 본문만으로는 다른 저장소의 에이전트가 이 결정을 모른다 — 이 한 줄이 목차 맨 위와 다음 세션 피드 `[결정]`에 오른다. `ACCEPTED`로 바뀔 때 같은 줄을 `--status 확정`으로 한 번 더.
7. 백로그 `D-NN`에 "ADR-NNN 초안" 한 줄. 검사는 훅이 돈다. 브랜치에 커밋 → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "<이슈키> ADR-NNN <제목>" --body "근거 M-… (상태) · D-NN"` — ADR + 결정 기록 + 백로그 한 PR. `DRAFT`.

보고: ADR 경로, 근거 회의록과 그 상태.
