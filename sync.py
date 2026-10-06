#!/usr/bin/env python3
"""sync — 저장소 골격을 만들고(new), 하네스가 바뀌었을 때 저장소에 **남아 있는 잔여 파일**만 갱신한다(update).

    python3 sync.py new  <name> --into ../work          # 새 저장소 골격 (product·backend·agent·frontend·ui·infra 중 하나)
    python3 sync.py all  --into ../kit                  # 여섯 전부 (킷 빌드)
    python3 sync.py update ../work/backend ../work/product   # 잔여 파일 갱신 — Pipelines · .gitignore · settings.json의 플러그인 선언 · harness.json

v0.12부터 스킬·훅·서브에이전트·스크립트는 저장소에 **복사하지 않는다** — 플러그인(core + 역할 플러그인)으로 온다.
저장소는 `.claude/settings.json`의 enabledPlugins로 "무엇을 쓰는지" 선언만 한다(프로젝트 범위 — 그 저장소를 여는 모든 사람에게 켜지고, 설치 안 된 사람에겐 설치하라고 알린다).
저장소에 남는 것: AGENTS.md(그 저장소의 지도만 — 공통 규칙은 core가 세션 시작에 넣는다) · settings.json · .gitignore · CODEOWNERS · bitbucket-pipelines.yml(하네스를 clone해서 검사) · .claude/harness.json · product의 양식.
하네스가 바뀌면 `harness` 저장소에 태그 하나 — 플러그인 갱신은 각자의 Claude Code가 받는다(자동 갱신 켬). update는 위 잔여 파일이 바뀌었을 때만.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VERSION = (HERE / "VERSION").read_text(encoding="utf-8").strip()
CORE = HERE / "plugins" / "core"
MARKET = "team-harness"
MARK_S, MARK_E = "<!-- harness:common start", "<!-- harness:common end -->"


def remotes() -> dict:
    return json.loads((HERE / "remotes.json").read_text(encoding="utf-8"))


def repos_json() -> str:
    """플러그인 scripts/repos.json — init.py·issue.py가 읽는다. 원격 주소·역할·읽는 저장소·Jira."""
    r = remotes()
    return json.dumps({"base": r["base"], "default_branch": r.get("default_branch", "main"), "jira": r.get("jira", {}),
                       "company_email_domain": r.get("company_email_domain", ""), "marketplace_add": r.get("marketplace_add", ""), "roles": ROLES, "plugins": ROLE_PLUGIN, "doc_types": TEAM.get("doc_types", {}), "docs": {n: r.get("docs", []) for n, r in TEAM["repos"].items()}, "reads": {n: [x for x, _ in rp["reads"]] for n, rp in REPOS.items()}}, ensure_ascii=False, indent=2) + "\n"


# 팀 구성은 team.json에 있다 — 저장소·주인(역할)·읽는 저장소·폴더·플러그인. 구조를 바꾸려면 코드가 아니라 그 파일을 고친다.
TEAM = json.loads((HERE / "team.json").read_text(encoding="utf-8"))
ROLES = TEAM["roles"]
ROLE_PLUGIN = {n: r.get("plugin", "core") for n, r in TEAM["repos"].items() if r.get("plugin", "core") != "core"}
REPOS = {n: {**{k: v for k, v in r.items() if k not in ("reads", "plugin")}, "reads": [(x["repo"], x["why"]) for x in r.get("reads", [])]} for n, r in TEAM["repos"].items()}


PIPELINES = """# 모든 PR과 main에서 문서를 검사한다. 실패 출력의 → 줄이 수정 지침이다.
# 검사 스크립트는 저장소에 없다 — 하네스(core 플러그인)를 태그로 clone해서 쓴다. HARNESS_TOKEN(저장소 액세스 토큰, 읽기)·HARNESS_REF(태그, 기본 main)는 저장소 변수.
# ⚠️ gitleaks 단계는 이 킷에서 실행 검증하지 못했다(이미지·플래그) — 첫 PR에서 확인. 의존성 캐시(M-a 결정 #3)는 코드 파이프라인이 생길 때 데브옵스와.
image: python:3.12-slim

definitions:
  steps:
    - step: &docs
        name: docs check + 이슈 키
        script:
          - python3 -m pip install --quiet pyyaml
          - git clone --quiet --depth 1 --branch "${HARNESS_REF:-main}" "https://x-token-auth:${HARNESS_TOKEN}@HARNESS_HOST/harness.git" .harness
          - python3 .harness/plugins/core/scripts/gen_index.py docs --write
          - python3 .harness/plugins/core/scripts/docs_check.py docs notes
          - echo "$BITBUCKET_BRANCH" | grep -Eq '^(main|master)$|^(feature|bugfix|hotfix)/[A-Z][A-Z0-9]+-[0-9]+-' || { echo "E90 브랜치 이름에 이슈 키가 없다 ($BITBUCKET_BRANCH) → feature/KEY-123-설명 형식으로 브랜치를 다시 만든다"; exit 1; }
          - if grep -qE '(^|[^A-Z])KEY-[0-9]' AGENTS.md; then echo "E91 AGENTS.md에 자리표시자 KEY가 남아 있다 → 실제 Jira 프로젝트 키로 바꾼다"; exit 1; fi

pipelines:
  pull-requests:
    "**":
      - step: *docs
      - step:
          name: secret scan
          image: zricethezav/gitleaks:latest
          script:
            - gitleaks detect --source . --no-git --redact --exit-code 1 || { echo "E92 시크릿이 들어 있다 → 키를 지우고 환경변수·시크릿 저장소로. 이미 푸시됐으면 키를 폐기한다"; exit 1; }
  branches:
    main:
      - step: *docs
      - step:
          name: 영향 알림 → Jira (push가 감지, Jira가 사람을 부른다 — 세션을 열 때까지 기다리지 않는다)
          script:
            - git clone --quiet --depth 1 --branch "${HARNESS_REF:-main}" "https://x-token-auth:${HARNESS_TOKEN}@HARNESS_HOST/harness.git" .harness
            - if [ -n "$JIRA_TOKEN" ] && [ -n "$JIRA_EMAIL" ]; then python3 .harness/plugins/core/scripts/notify_impact.py --ci --range "${BITBUCKET_COMMIT}~1..${BITBUCKET_COMMIT}" || echo "영향 알림 실패 — 다음 세션의 [영향]이 받는다"; else echo "JIRA_EMAIL·JIRA_TOKEN 저장소 변수 없음 — 영향 알림 건너뜀(세션 피드 [영향]만)"; fi
"""

GITIGNORE = "snapshot/\n__pycache__/\n*.pyc\n.env\n.claude/settings.local.json\n# 목차는 생성물 — 커밋하면 PR마다 충돌한다. 훅·init·CI가 만든다\ndocs/INDEX.md\n# 세션 피드 상태(지난 세션의 HEAD)·팀 현황 사본 — 각자 PC의 것\n.claude/harness-state.json\n.claude/TEAM.md\n# CI가 받는 하네스\n.harness/\n"
GITIGNORE_REQUIRED = ("docs/INDEX.md", ".claude/harness-state.json", ".claude/TEAM.md", ".claude/settings.local.json", ".harness/")


def ensure_gitignore(d: Path):
    gi = d / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.exists() else ""
    missing = [x for x in GITIGNORE_REQUIRED if x not in text.splitlines()]
    if missing:
        gi.write_text(text.rstrip("\n") + ("\n" if text else "") + "\n".join(missing) + "\n", encoding="utf-8")


PIPELINES_RAW = """# 메모 저장소 — 원자료. 검사는 시크릿 스캔뿐이다(형식·목차·이슈 키 없음). ⚠️ gitleaks 단계는 킷에서 실행 검증하지 못했다.
pipelines:
  default:
    - step:
        name: secret scan
        image: zricethezav/gitleaks:latest
        script:
          - gitleaks detect --source . --no-git --redact --exit-code 1 || { echo "E92 시크릿이 들어 있다 → 지우고 키를 폐기한다"; exit 1; }
"""


def _ws() -> str:
    import re as _re
    m = _re.search(r"bitbucket\.org/([^/]+)/", remotes().get("base", ""))
    return m.group(1) if m else "CHANGE-ME-workspace"


def pipelines_text() -> str:
    host = remotes()["base"].replace("https://", "").rstrip("/")   # 예: bitbucket.org/your-workspace
    return PIPELINES.replace("HARNESS_HOST", host)


def marketplace_source() -> dict:
    """remotes.json의 marketplace가 있으면 그것(예: GitHub {"source": "github", "repo": "owner/repo"}), 없으면 base + harness.git."""
    m = remotes().get("marketplace")
    if m:
        return m
    return {"source": "git", "url": remotes()["base"].rstrip("/") + "/harness.git"}


HARNESS_SCRIPTS = ("new_doc", "team_plan", "docs_check", "gen_index", "decision_log", "questions", "pr", "issue", "init", "memo", "notify_impact", "migrate_from_project")


def put_settings(d: Path, name: str):
    """settings.json — 읽는 저장소(additionalDirectories) + 플러그인 선언(enabledPlugins, 프로젝트 범위) + 마켓플레이스 알림."""
    sp = d / ".claude" / "settings.json"
    settings = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    if name in REPOS:
        settings.setdefault("permissions", {})["additionalDirectories"] = [f"../{x}" for x, _ in REPOS[name]["reads"]]
    # 스킬의 allowed-tools는 쓰지 않는다 — 모델이 부른 스킬에 allowed-tools가 있으면 본문이 로드되지 않았다(T35, 비대화형). 권한은 여기서 준다.
    # 하네스 스크립트·git은 묻지 않고 돈다 — 비개발자에게 "python3 … 허용?" 창이 뜨지 않게. 위험한 것(main 직접 push·force)은 서버의 브랜치 권한이 막는다
    allow = settings.setdefault("permissions", {}).setdefault("allow", [])
    for rule in [f"Bash(python3 *scripts/{n}.py*)" for n in HARNESS_SCRIPTS] + ["Write(docs/**)", "Edit(docs/**)", "Write(notes/**)", "Edit(notes/**)", "Write(../*/docs/questions/**)", "Write(../memo/people/**)", "Edit(../memo/people/**)"] + [f"Bash(git {g}*)" for g in ("status", "log", "diff", "show", "fetch", "pull", "add", "commit", "checkout", "switch", "branch", "rev-parse", "push -u origin", "push -q -u origin", "rebase", "merge --ff-only", "stash", "-C")] + ["Bash(cd *)", "Bash(ls*)", "Bash(cat *)", "Bash(head *)", "Bash(grep *)", "Bash(find *)"]:
        if rule not in allow:
            allow.append(rule)
    deny = settings.setdefault("permissions", {}).setdefault("deny", [])
    for rule in ("Read(../tokens.txt)", "Read(**/tokens.txt)", "Bash(git push --force*)", "Bash(git push -f*)", "Bash(*tokens.txt*)", "Bash(find * -delete*)", "Bash(find * -exec*)"):   # 사람의 토큰 파일 — 에이전트는 열지 않는다(스크립트만 읽는다). ⚠️ 규칙 문법 실측 전
        if rule not in deny:
            deny.append(rule)
    settings.pop("hooks", None)   # v0.11까지의 저장소 훅 — 이제 플러그인이 갖는다
    plugs = {f"core@{MARKET}": True}
    if name in ROLE_PLUGIN:
        plugs[f"{ROLE_PLUGIN[name]}@{MARKET}"] = True
    settings["enabledPlugins"] = {**{k: v for k, v in settings.get("enabledPlugins", {}).items() if not k.endswith("@" + MARKET)}, **plugs}
    settings["extraKnownMarketplaces"] = {**settings.get("extraKnownMarketplaces", {}), MARKET: {"source": marketplace_source()}}   # ⚠️ 스키마 미검증 — 틀리면 이 키만 지운다
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def put_residual(d: Path, name: str):
    """저장소에 남는 잔여 파일 (new와 update가 같이 쓴다)."""
    ensure_gitignore(d)
    put_settings(d, name)
    raw = bool(REPOS.get(name, {}).get("raw"))
    (d / "bitbucket-pipelines.yml").write_text(PIPELINES_RAW.replace("CHANGE-ME-workspace", _ws()) if raw else pipelines_text(), encoding="utf-8")
    hj = d / ".claude" / "harness.json"
    old = json.loads(hj.read_text(encoding="utf-8")) if hj.exists() else {}
    if raw:
        old["raw"] = True   # 원자료 저장소 — 이슈 키 훅·목차·형식 검사 없음. 세션 피드는 [메모] 한 줄
    old.update({"harness": VERSION, "plugins": sorted(k.split("@")[0] for k in json.loads((d / ".claude" / "settings.json").read_text(encoding="utf-8"))["enabledPlugins"] if k.endswith("@" + MARKET))})
    old.setdefault("prefixes", {})   # D-29 — product가 자기 ID 체계를 정하면 여기: {"policy": "PO-\\d{3}"}
    old.pop("version", None); old.pop("skills", None)
    hj.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # v0.11까지의 복사본 정리: 지도 파일의 공통 블록은 짧은 안내로, 복사된 스킬·훅·에이전트·스크립트는 지운다
    cm = d / "AGENTS.md"
    if not cm.exists() and (d / "CLAUDE.md").exists() and (d / "CLAUDE.md").read_text(encoding="utf-8").strip() != "@AGENTS.md":
        (d / "CLAUDE.md").rename(cm)
    if cm.exists():
        t = cm.read_text(encoding="utf-8")
        if MARK_S in t and MARK_E in t:
            t = t[: t.index(MARK_S)] + common_pointer() + t[t.index(MARK_E) + len(MARK_E):]
            cm.write_text(t, encoding="utf-8")
    (d / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    for sub in (".claude/skills", ".claude/agents", ".claude/hooks"):
        p = d / sub
        if p.is_dir() and _is_harness_copy(p):
            shutil.rmtree(p)
    sc = d / "scripts"
    if sc.is_dir() and (sc / "docs_check.py").exists() and (sc / "gen_index.py").exists():
        for f in list(sc.glob("*.py")) + [sc / "repos.json"]:
            if f.exists():
                f.unlink()
        shutil.rmtree(sc / "__pycache__", ignore_errors=True)
        if not any(sc.iterdir()):
            sc.rmdir()


def _is_harness_copy(p: Path) -> bool:
    names = {x.name for x in p.iterdir()}
    return bool(names & {"ask", "answer", "approve", "policy-digest.md", "docs-reviewer.md", "session_start.py", "after_doc_edit.py"})


def common_pointer() -> str:
    return (MARK_S + " — 이 블록은 harness/sync.py가 갱신한다 -->\n"
            "## 공통 규칙\n"
            "전 저장소 공통 규칙(맥락·소통·문서·git·검사)은 **core 플러그인이 세션 시작에 컨텍스트에 넣는다** — 원문 `harness/plugins/core/RULES.md`. 이 파일에는 이 저장소의 지도만 둔다.\n"
            "이 저장소가 쓰는 플러그인은 `.claude/settings.json`의 `enabledPlugins`에 있다. 설치 안 됐다는 안내가 뜨면 `claude plugin install <이름>@" + MARKET + "`.\n"
            + MARK_E)


def new_repo(name: str, parent: Path):
    r = REPOS[name]
    d = parent / name
    if d.exists():
        sys.exit(f"이미 있다: {d} — update를 쓴다")
    (d / ".claude").mkdir(parents=True)
    (d / ".bitbucket").mkdir()
    for sub in r["mkdirs"]:
        (d / sub).mkdir(parents=True, exist_ok=True)
        (d / sub / ".gitkeep").touch()
    (d / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (d / ".bitbucket" / "CODEOWNERS").write_text("# 리뷰어 자동 지정 (Bitbucket Cloud: 제안까지. 강제는 브랜치 권한 + Pipelines). 셋업 때 @핸들을 실제 계정으로.\n" + "".join(f"{k:<28}{v}\n" for k, v in r["codeowners"].items()), encoding="utf-8")
    reads = "\n".join((f"- `../{x}/` — {why}. 사람 폴더 `people/<이름>/`, 회고 `retro/`. 목차 없음 — 세션 시작 `[메모]` 줄이 바뀐 것을 알린다" if REPOS.get(x, {}).get("raw") else f"- `../{x}/` — {why}. 목차: `../{x}/docs/INDEX.md`") for x, why in r["reads"]) or "- (없음 — 이 저장소가 원천이다. 필요하면 `backend`·`frontend`를 읽기로 열 수 있다)"
    dirs = "\n".join(f"- `{line.split('  ',1)[0]}`  {line.split('  ',1)[1]}" if "  " in line else f"- `{line}`" for line in r["dirs"])
    tmpl = (HERE / "repo-template" / ("AGENTS-memo.md.tmpl" if r.get("raw") else "AGENTS.md.tmpl")).read_text(encoding="utf-8")
    (d / "AGENTS.md").write_text(tmpl.format(name=name, label=r["label"], purpose=r["purpose"], product_line=("\n" + TEAM["product"]) if TEAM.get("product") else "", owner=r["owner"], provides=r["provides"], dirs=dirs, extra=r["extra"], reads=reads,
                                              templates="`docs/templates/`" if name == "product" else "`../product/docs/templates/`",
                                              plugin=ROLE_PLUGIN.get(name, "core"), market=MARKET), encoding="utf-8")
    if name == "product":
        for f in (HERE / "repo-template" / "product").rglob("*"):
            if f.is_file():
                dst = d / f.relative_to(HERE / "repo-template" / "product")
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(f, dst)
    put_residual(d, name)
    if not r.get("raw"):
        subprocess.run([sys.executable, str(CORE / "scripts" / "gen_index.py"), "docs", "--write"], cwd=d, check=True, capture_output=True)
    return d


MEMO_READ_LINE = "- `../memo/` — 팀원들의 메모·회고 — 생각이지 근거가 아니다. 사람 폴더 `people/<이름>/`, 회고 `retro/`. 목차 없음 — 세션 시작 `[메모]` 줄이 바뀐 것을 알린다"


def ensure_memo_read(d: Path, name: str):
    """기존 저장소의 AGENTS.md(지도는 저장소 것이라 sync가 덮지 않는다)에 memo 읽기 한 줄만 없으면 넣는다 — 0.13."""
    cm = d / "AGENTS.md"
    if not cm.exists() or not any(x == "memo" for x, _ in REPOS.get(name, {}).get("reads", [])):
        return False
    t = cm.read_text(encoding="utf-8")
    if "`../memo/`" in t:
        return False
    marker = "## 읽는 저장소"
    if marker not in t:
        return False
    i = t.index(marker); j = t.index("\n", i) + 1
    cm.write_text(t[:j] + MEMO_READ_LINE + "\n" + t[j:], encoding="utf-8")
    return True


def update_repo(d: Path):
    d = d.resolve()
    raw = bool(REPOS.get(d.name, {}).get("raw"))
    if not ((d / "AGENTS.md").exists() or (d / "CLAUDE.md").exists()) or not ((d / "docs").is_dir() or raw):
        print(f"건너뜀 (저장소 아님): {d}")
        return
    put_residual(d, d.name)
    added = ensure_memo_read(d, d.name)
    print(f"갱신 {d.name} → harness {VERSION} (잔여 파일: Pipelines · .gitignore · settings 플러그인 선언 · harness.json{' · AGENTS.md에 memo 읽기 한 줄' if added else ''})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("name", choices=sorted(REPOS)); n.add_argument("--into", required=True)
    a_ = sub.add_parser("all"); a_.add_argument("--into", required=True)
    u = sub.add_parser("update"); u.add_argument("repos", nargs="+")
    a = ap.parse_args()
    (CORE / "scripts" / "repos.json").write_text(repos_json(), encoding="utf-8")   # 플러그인의 repos.json은 remotes.json에서 나온다
    if a.cmd == "new":
        print(new_repo(a.name, Path(a.into).resolve()))
    elif a.cmd == "all":
        parent = Path(a.into).resolve(); parent.mkdir(parents=True, exist_ok=True)
        for name in REPOS:
            new_repo(name, parent)
        print("generated:", ", ".join(REPOS), f"(harness {VERSION}, plugins core + {len(set(ROLE_PLUGIN.values()))} role plugins)")
    else:
        for r in a.repos:
            update_repo(Path(r))


if __name__ == "__main__":
    main()
