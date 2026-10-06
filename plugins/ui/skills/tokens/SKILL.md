---
name: tokens
description: Figma 변수(MCP)에서 ui/tokens/를 다시 생성한다. 디자이너가 Figma를 바꿨을 때. 생성물은 손으로 고치지 않는다. "디자인 바뀌었대", "토큰 다시 뽑아"에 쓴다.
---

ui 저장소에서 돈다.

1. `docs/FIGMA.md`의 파일 링크와 마지막 동기화 시각을 읽는다.
2. Figma MCP로 변수(색·간격·타이포)를 읽어 `tokens/`를 다시 쓴다. 이름 규칙은 `docs/decisions/`의 토큰 ADR을 따른다 — 없으면 만들지 않고 `/core:adr`로 먼저.
3. 바뀐 토큰 목록과 영향받는 `components/`를 보고한다. `docs/FIGMA.md`의 동기화 시각을 갱신.
4. 커밋 `KEY-N tokens 재생성 (Figma <날짜>)` → `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pr.py" "…"` — 퍼블리셔가 시각 충실도를 `/core:approve`로 승인.

보고: 바뀐 토큰 수, 영향 컴포넌트.
