---
name: review-docs
description: 문서 PR을 리뷰한다 — 검사 스크립트 결과에 더해 DRAFT 의존·정책서와 스펙 불일치·결정의 출처를 docs-reviewer 서브에이전트가 보고, 승인자가 5분 안에 결정할 수 있는 요약을 만든다.
argument-hint: '[브랜치 또는 파일들]'
context: fork
agent: docs-reviewer
background: false
---

`git diff --name-only main...HEAD -- docs notes` (또는 받은 파일 목록)의 문서를 검토한다. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/docs_check.py" docs notes`를 먼저 돌리고, 스크립트가 못 보는 것(초안 의존 · 원천 불일치 · 결정 출처 · 질문 처리 · 개정 이력)을 본다. 결과는 "막는 것 / 고치면 좋은 것 / 확인함" 세 절로.
