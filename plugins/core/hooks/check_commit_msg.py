#!/usr/bin/env python3
"""PreToolUse(Bash) 훅 — `git commit`에 Jira 이슈 키가 없으면 막는다(exit 2). 서버(저장소 설정)가 거부하기 전에 여기서 알려준다.

키 형식: 대문자 프로젝트 키-숫자 (SSY-123). --amend --no-edit, 메시지 없는 커밋(에디터)은 건드리지 않는다.
"""
import json
import re
import sys

KEY = re.compile(r"\b[A-Z][A-Z0-9]+-[0-9]+\b")


def _is_raw_repo(cmd: str, cwd) -> bool:
    """커밋 대상 저장소의 .claude/harness.json 에 raw:true 가 있으면 참. `git -C <경로> commit` 이면 그 경로, 아니면 cwd."""
    import json as _j
    from pathlib import Path
    base = Path(cwd or ".")
    m = re.search(r"\bgit\s+-C\s+(\"[^\"]+\"|'[^']+'|\S+)", cmd)
    target = (base / m.group(1).strip("\"'")) if m else base
    for d in [target.resolve(), *target.resolve().parents]:
        hj = d / ".claude" / "harness.json"
        if hj.exists():
            try:
                return bool(_j.loads(hj.read_text(encoding="utf-8")).get("raw"))
            except Exception:
                return False
        if (d / ".git").exists():
            return False
    return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not re.search(r"\bgit\s+commit\b", cmd) or "--no-edit" in cmd:
        return 0
    if _is_raw_repo(cmd, data.get("cwd")):   # memo 같은 원자료 저장소 — 이슈 키를 요구하지 않는다
        return 0
    msgs = re.findall(r"(?:-m|--message)[ =](?:\"([^\"]*)\"|'([^']*)'|(\S+))", cmd)
    if not msgs:
        return 0
    text = " ".join("".join(m) for m in msgs)
    if KEY.search(text):
        return 0
    sys.stderr.write("커밋 메시지에 Jira 이슈 키가 없다 (예: `SSY-123 이탈 감지 스펙 초안`). 저장소 설정이 푸시를 거부한다. 작업의 이슈 키를 앞에 붙인다 — 없으면 하네스 스크립트 `issue.py '<작업 제목>'`(플러그인 scripts/)으로 만든다(exit 3이면 사람에게 묻는다).\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
