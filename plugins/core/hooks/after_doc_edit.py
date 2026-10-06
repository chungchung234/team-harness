#!/usr/bin/env python3
"""PostToolUse(Write|Edit) 훅 — 문서를 고치면 목차를 다시 만들고 검사한다. 오류가 있으면 그 줄을 에이전트에게 돌려준다(exit 2).

- docs/ · notes/ 아래 .md만 대상. 다른 파일은 아무것도 안 한다.
- 옆 저장소(../product/docs/questions/…)에 썼으면 **그 저장소**에서 돈다 — 질문 파일을 만든 뒤 product의 목차가 낡는 문제(E15)를 여기서 막는다.
- 검사 출력은 이미 "→ 수정 지침"을 담고 있으므로 그대로 보낸다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)
SCRIPTS = PLUGIN_ROOT / "scripts"


def repo_of(p: Path):
    """하네스 저장소 = docs/가 있고 지도 파일(AGENTS.md/CLAUDE.md)이나 .claude/harness.json이 있는 폴더."""
    for d in [p] + list(p.parents):
        if (d / "docs").is_dir() and ((d / "AGENTS.md").exists() or (d / "CLAUDE.md").exists() or (d / ".claude" / "harness.json").exists()):
            return d
    return None


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    if not fp.endswith(".md"):
        return 0
    path = Path(fp)
    if not path.is_absolute():
        path = Path(data.get("cwd") or ".") / path
    path = path.resolve()
    repo = repo_of(path.parent)
    if repo is None:
        return 0
    rel = path.relative_to(repo).parts
    if not rel or rel[0] not in ("docs", "notes") or "templates" in rel:
        return 0
    py = sys.executable
    subprocess.run([py, str(SCRIPTS / "gen_index.py"), "docs", "--write"], cwd=repo, capture_output=True, text=True)
    roots = ["docs"] + (["notes"] if (repo / "notes").is_dir() else [])
    r = subprocess.run([py, str(SCRIPTS / "docs_check.py"), *roots], cwd=repo, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        lines = [l for l in r.stdout.splitlines() if l.strip()]
        # 오류 블록만 (E로 시작하는 줄과 그 뒤 두 줄)
        keep, take = [], 0
        for l in lines:
            if l[:1] == "E" and l[1:3].isdigit():
                take = 3
            if take:
                keep.append(l); take -= 1
        sys.stderr.write(f"[docs_check @ {repo.name}] 문서 검사 오류 — 고치고 다시 저장한다. 목차(docs/INDEX.md)는 이미 다시 만들었다.\n" + "\n".join(keep[-30:]) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
