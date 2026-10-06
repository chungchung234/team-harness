#!/usr/bin/env python3
"""build — 역할 플러그인에 코어의 scripts/·templates/ 사본을 넣는다 (같은 마켓플레이스 안의 빌드 산출물).

    python3 build.py            # 복사 + 각 플러그인 version = VERSION + marketplace.json 갱신
    python3 build.py --check    # 사본이 코어와 같은지만 확인 (CI용, 다르면 exit 1)

왜: 스킬 본문의 `${CLAUDE_PLUGIN_ROOT}`는 **그 스킬이 든 플러그인**의 루트다. `/product:policy`가 코어의 new_doc.py를 부르려면
자기 플러그인 안에 scripts/가 있어야 한다. 원본은 plugins/core/scripts 하나 — 여기서만 고치고 build로 퍼뜨린다(저장소 사이 sync PR이 아니라 한 저장소 안의 빌드).
"""
import filecmp
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text(encoding="utf-8").strip()
P = HERE / "plugins"
CORE = P / "core"
ROLE = [p for p in sorted(P.iterdir()) if p.is_dir() and p.name != "core"]
COPY = ["scripts", "templates"]


def same(a: Path, b: Path) -> bool:
    if not (a.exists() and b.exists()):
        return False
    c = filecmp.dircmp(a, b, ignore=["__pycache__", "README.md"])
    return not (c.left_only or c.right_only or c.diff_files or any(not same(a / d, b / d) for d in c.common_dirs))


def main() -> int:
    check = "--check" in sys.argv
    bad = 0
    for r in ROLE:
        for sub in COPY:
            src, dst = CORE / sub, r / sub
            if check:
                if not same(src, dst):
                    print(f"다름: {dst.relative_to(HERE)} ← {src.relative_to(HERE)} (python3 build.py)"); bad += 1
                continue
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        if not check:
            (r / "scripts" / "README.md").write_text("빌드 사본 — 원본은 plugins/core/scripts. 여기서 고치지 않는다 (python3 build.py).\n", encoding="utf-8")
    if check:
        print("build --check:", "OK" if not bad else f"{bad}건 다름")
        return 1 if bad else 0
    for p in [CORE, *ROLE]:
        mf = p / ".claude-plugin" / "plugin.json"
        m = json.loads(mf.read_text(encoding="utf-8")); m["version"] = VERSION
        mf.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    mk = HERE / ".claude-plugin" / "marketplace.json"
    m = json.loads(mk.read_text(encoding="utf-8"))
    for e in m["plugins"]:
        e["version"] = VERSION
    mk.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(CORE / "scripts" / "__pycache__", ignore_errors=True)
    print(f"build: {len(ROLE)} role plugins ← core scripts/templates · version {VERSION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
