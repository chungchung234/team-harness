#!/usr/bin/env python3
"""init — 역할에 맞는 저장소를 옆에 나란히 clone한다. 사람이 git clone을 치지 않게 하기 위한 것.

    python3 init.py 백엔드                 # backend(자기 것) + product, agent(읽기) 를 현재 폴더(work/) 아래에
    python3 init.py product                # 저장소 이름으로도 된다
    python3 init.py add agent              # 이미 있는 work/에 읽기용 저장소 하나 추가 (나중에 생긴 저장소)
    python3 init.py 백엔드 --user <bitbucket 사용자> --app-password <앱 비밀번호> --jira-email <이메일> --jira-token <토큰>
                                           # pr.py(PR·승인·머지가 이 사람 이름으로)·issue.py가 쓸 자격증명을 자기 저장소의 .claude/settings.local.json(커밋 안 됨)에

- 원격 주소는 옆의 repos.json(base)에서 읽는다. 없는 원격(아직 안 만든 저장소)은 건너뛰고 알린다. 받았는데 커밋이 하나도 없는 원격(만들고 setup을 안 올린 것)은 '비어있음'으로 알리고 빈 폴더를 남기지 않는다.
- 끝나면 남는 사람 손 하나를 그대로 적어 준다: 각 폴더에서 Claude Code를 한 번 열어 신뢰 다이얼로그 수락. 이건 보안 확인이라 스크립트가 대신 누르지 않는다.
- 역할 플러그인도 설치한다: `claude plugin install <역할>@team-harness` (마켓플레이스 `team-harness`가 없으면 repos.json의 base + harness.git 으로 add). `--no-plugins`로 끈다.
- memo 저장소가 있으면 **내 폴더** `memo/people/<이름>/`을 만들어 올리고, 이름을 모든 저장소의 `.claude/settings.local.json` env `HARNESS_ME`에 적는다 — `/core:note`가 어느 저장소에서든 내 폴더를 찾는다. 이름은 `--name`, 없으면 `git config user.name`.
- 이 파일은 core 플러그인 안에 있다(각 역할 플러그인에도 빌드가 같은 것을 넣는다). 처음 한 번은 `claude plugin marketplace add <harness URL>` → `claude plugin install core@team-harness` → `/core:init 백엔드`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import creds  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "repos.json").read_text(encoding="utf-8"))
ROLES = CFG["roles"]      # 역할 → 저장소
READS = CFG["reads"]      # 저장소 → 읽는 저장소들
BASE = (os.environ.get("HARNESS_BASE") or CFG["base"]).rstrip("/") + "/"   # HARNESS_BASE: 시연(로컬 원격)·다른 호스트
# 마켓플레이스를 어디서 받나 — HARNESS_MARKETPLACE(시연: PoC 폴더) > repos.json marketplace_add(예: GitHub owner/repo) > base + harness.git
MARKET_SRC = os.environ.get("HARNESS_MARKETPLACE") or CFG.get("marketplace_add") or (BASE + "harness.git")


ROLE_PLUGIN = {**CFG.get("plugins", {}), "harness": "core"}   # 저장소 → 역할 플러그인 (team.json에서 온다)
MARKET = "team-harness"
GEN_INDEX = HERE / "gen_index.py"


def find_work(start: Path) -> Path:
    """work/ 를 정한다: 현재 폴더가 하네스 저장소(docs/ + AGENTS.md 또는 .claude/harness.json)면 그 부모, 아니면 현재 폴더."""
    if ((start / "docs").is_dir() and ((start / "AGENTS.md").exists() or (start / ".claude" / "harness.json").exists())) or (start / "sync.py").exists():
        return start.parent
    return start


def claude_cli(*args):
    try:
        r = subprocess.run(["claude", "plugin", *args], capture_output=True, text=True, encoding="utf-8", timeout=180)
        return r.returncode, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return 127, "claude CLI 없음"
    except Exception as e:
        return 1, str(e)


def install_plugins(mine: str) -> list[str]:
    """마켓플레이스 등록 + 역할 플러그인 설치 (코어는 의존성으로 따라온다). 이미 있으면 그대로."""
    out = []
    code, lst = claude_cli("marketplace", "list")
    if code == 127:
        return ["  플러그인  claude CLI를 찾지 못했다 — 터미널에서 `claude plugin marketplace add " + MARKET_SRC + "` 뒤 `claude plugin install " + ROLE_PLUGIN.get(mine, "core") + "@" + MARKET + "`"]
    if MARKET not in lst:
        code, msg = claude_cli("marketplace", "add", MARKET_SRC)
        out.append(f"  마켓플레이스 {'등록 ' + MARKET if code == 0 else '등록 실패 — ' + msg.splitlines()[-1][:120] if msg else '등록 실패'}")
        if code != 0:
            out.append("         → Bitbucket HTTPS 자격증명이 저장돼 있어야 한다(프롬프트 없이 clone). `git credential` 확인 뒤 다시")
            return out
    plug = ROLE_PLUGIN.get(mine, "core")
    code, msg = claude_cli("install", f"{plug}@{MARKET}", "--scope", "user")
    out.append(f"  플러그인  {plug}@{MARKET} {'설치' if code == 0 else '설치 실패 — ' + (msg.splitlines()[-1][:120] if msg else '?')}" + ("  (core는 의존성으로 함께)" if code == 0 and plug != "core" else ""))
    out.append(f"         자동 갱신: 세션에서 `/plugin` → Marketplaces → {MARKET} → Enable auto-update (제3자 마켓플레이스는 기본 꺼짐)")
    return out


def clone(work: Path, name: str, why: str) -> str:
    dst = work / name
    if dst.exists():
        return f"  있음   {name}/  ({why})"
    url = BASE + name + ".git"
    r = subprocess.run(["git", "clone", "--quiet", url, str(dst)], capture_output=True, text=True)
    if r.returncode != 0:
        why_fail = (r.stderr.strip().splitlines() or ["?"])[-1]
        return f"  실패   {name}/  ({why}) — {why_fail[:90]}\n         → 저장소가 아직 없으면 하네스 담당이 `remote.py create {name}`으로 만든다. 권한 문제면 Bitbucket 로그인(자격증명 저장)을 확인"
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=dst, capture_output=True).returncode != 0:
        # 받았는데 커밋이 없다 — 하네스 담당이 setup을 아직 안 올렸거나, 원격의 기본 브랜치(HEAD)가 내용 있는 브랜치를 가리키지 않는다. 빈 폴더를 남기면 다음 init이 "있음"으로 넘어가므로 지운다.
        import shutil; shutil.rmtree(dst, ignore_errors=True)
        return f"  비어있음 {name}/  ({why}) — 원격에 커밋이 없다\n         → 하네스 담당이 `setup {name}`을 아직 안 올렸거나, Bitbucket 저장소 설정의 Main branch가 비어 있는 브랜치를 가리킨다. 채워지면 `/core:init add {name}`"
    if GEN_INDEX.exists() and (dst / "docs").is_dir():  # 목차는 커밋되지 않는다 — 여기서 처음 만든다
        subprocess.run([sys.executable, str(GEN_INDEX), "docs", "--write"], cwd=dst, capture_output=True)
    return f"  clone  {name}/  ({why})"


def my_name(explicit: str | None) -> str:
    name = explicit or os.environ.get("HARNESS_ME") or ""
    if not name:
        r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, encoding="utf-8")
        name = r.stdout.strip() if r.returncode == 0 else ""
    import re
    return re.sub(r"[\\/:*?\"<>|\s]+", "-", name.strip())


def setup_memo(work: Path, name: str) -> list[str]:
    """memo/people/<이름>/ 을 만들고 올린다 (이미 있으면 그대로). 커밋 메시지는 `memo:` — 원자료 저장소는 이슈 키가 없어도 된다."""
    memo = work / "memo"
    if not memo.is_dir() or not (memo / ".git").exists():
        return ["  메모     memo 저장소가 없다 — 하네스 담당이 만들면 `/core:init add memo` 뒤 다시"]
    if subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=memo, capture_output=True).returncode != 0:
        return ["  메모     memo 저장소가 비어 있다(커밋 없음) — 하네스 담당이 `setup memo --mode direct`로 채운 뒤 다시. 빈 저장소에 내 폴더부터 올리지 않는다(엉뚱한 브랜치가 생긴다)"]
    if not name:
        return ["  메모     내 이름을 모른다 — `/core:init <역할> --name 홍길동` 또는 `git config --global user.name`"]
    folder = memo / "people" / name
    if (folder / "README.md").exists():
        return [f"  메모     있음   memo/people/{name}/"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "README.md").write_text(
        f"# {name}의 메모\n\n"
        f"여기 있는 것은 {name}의 업무 생각이지 팀의 결정이 아니다. 팀 전원과 모든 에이전트가 읽고 git 이력에 남는다 — 개인 사정·남에 대한 평가는 적지 않는다.\n"
        f"적는 길: 어느 저장소에서든 `/core:note \"한 줄\"`. 근거가 되려면 `/core:catchup`으로 `docs/`에 올린다.\n\n"
        f"## 내 폴더 지도 (자유롭게 고친다 — `/core:note`가 이것을 읽고 따른다)\n"
        f"- 기본: 날짜 파일(`YYYY-MM-DD.md`)에 한 줄씩\n", encoding="utf-8")
    g = lambda *a: subprocess.run(["git", "-c", "core.quotepath=off", *a], cwd=memo, capture_output=True, text=True, encoding="utf-8")
    g("add", f"people/{name}/README.md")
    c = g("commit", "-q", "-m", f"memo: {name} 폴더")
    if c.returncode != 0:
        return [f"  메모     폴더는 만들었으나 커밋 실패 — {c.stderr.strip()[-100:]}"]
    br = g("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"
    if g("remote", "get-url", "origin").returncode == 0:
        g("pull", "--rebase", "-q", "origin", br)
        pu = g("push", "-q", "-u", "origin", "HEAD")
        return [f"  메모     memo/people/{name}/ 만들어 {'올렸다' if pu.returncode == 0 else '커밋했다 (push 실패 — `git -C memo push`)'}"]
    return [f"  메모     memo/people/{name}/ 만들어 커밋했다 (원격 없음)"]


def write_env(repo: Path, env: dict):
    """자격증명은 커밋되지 않는 .claude/settings.local.json 의 env 에 — Claude Code가 세션 환경변수로 넣어 준다."""
    p = repo / ".claude" / "settings.local.json"
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    d.setdefault("env", {}).update({k: v for k, v in env.items() if v})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def open_for_person(path: Path):
    """사람이 볼 수 있게 파일을 연다(메모장·텍스트 편집기). 시험·CI에선 HARNESS_NO_OPEN=1."""
    if os.environ.get("HARNESS_NO_OPEN") or os.environ.get("CI"):
        return
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-t", str(path)])
        elif os.name == "nt":
            subprocess.Popen(["notepad", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def verify_tokens(vals: dict) -> list[tuple[bool, str, str]]:
    """넣은 토큰이 맞는지 한 번 호출해 본다 — 누구로 확인됐는지만 말하고 값은 말하지 않는다. HARNESS_OFFLINE=1이면 건너뛴다."""
    import base64, urllib.request, urllib.error
    out = []
    if os.environ.get("HARNESS_OFFLINE"):
        return out
    bt = vals.get("BITBUCKET_API_TOKEN")
    if bt:
        try:
            req = urllib.request.Request("https://api.bitbucket.org/2.0/user", headers={"Authorization": f"Bearer {bt}", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
            out.append((True, f"Bitbucket 토큰 — {d.get('display_name', '?')}(으)로 확인", ""))
        except urllib.error.HTTPError as e:
            out.append((False, f"Bitbucket 토큰이 받아들여지지 않는다 (HTTP {e.code})", "만료됐거나 범위가 모자라다 — 파일 안의 2단계대로 다시 만든다"))
        except Exception:
            out.append((False, "Bitbucket 토큰 — 확인하지 못했다(인터넷 연결?)", "연결된 뒤 `init check` 다시"))
    je, jt, site = vals.get("JIRA_EMAIL"), vals.get("JIRA_TOKEN"), CFG.get("jira", {}).get("site", "").rstrip("/")
    if je and jt and site and "CHANGE-ME" not in site:
        try:
            auth = base64.b64encode(f"{je}:{jt}".encode()).decode()
            req = urllib.request.Request(f"{site}/rest/api/3/myself", headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode("utf-8"))
            out.append((True, f"Jira 토큰 — {d.get('displayName', '?')}(으)로 확인", ""))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 403 and "IP" in body:
                out.append((False, "Jira가 이 네트워크를 막는다 (회사 IP 허용 목록)", "회사 망이나 VPN에 연결한 뒤 \"다 넣었어\"라고 다시 말한다"))
            else:
                out.append((False, f"Jira 토큰이 받아들여지지 않는다 (HTTP {e.code})", "메일·토큰을 다시 확인하거나 파일 안의 3단계대로 다시 만든다"))
        except Exception:
            out.append((False, "Jira 토큰 — 확인하지 못했다(인터넷 연결?)", "연결된 뒤 `init check` 다시"))
    return out


COMPANY_DOMAIN = CFG.get("company_email_domain", "")   # repos.json — 예: example.com. 비면 도메인 검사를 하지 않는다


def check(work: Path, mine: str | None) -> int:
    """설치가 다 됐는지 — 무엇이 있고 무엇이 없는지, 다음에 사람이 할 일 한 줄씩. 비밀 값은 절대 출력하지 않는다(있다/없다만)."""
    rows = []
    def row(ok, what, nxt=""):
        rows.append(f"  {'✓' if ok else '✗'} {what}" + ("" if ok or not nxt else f"\n      → {nxt}"))
    run = lambda *c, cwd=None: subprocess.run(list(c), cwd=cwd, capture_output=True, text=True, encoding="utf-8")
    try:
        gv = run("git", "--version").returncode == 0
    except Exception:
        gv = False
    row(gv, "git 설치", "Windows면 https://git-scm.com 에서 설치(기본값 그대로 다음·다음) — Claude Code가 git으로 저장소를 받는다")
    gn, ge = (run("git", "config", "user.name").stdout.strip(), run("git", "config", "user.email").stdout.strip()) if gv else ("", "")
    row(bool(gn), f"git 이름 {gn or '(없음)'}", "`git config --global user.name '홍길동'` — 팀에서 부르는 이름")
    dom_ok = bool(ge) and (not COMPANY_DOMAIN or ge.lower().endswith("@" + COMPANY_DOMAIN.lower()))
    row(dom_ok, f"git 메일 {ge or '(없음)'}" + (f" (회사 메일 @{COMPANY_DOMAIN})" if COMPANY_DOMAIN else ""), "커밋에 영구히 남는다 — 회사 메일로: `git config --global user.email 이름@회사`")
    repos = [d for d in sorted(work.iterdir()) if (d / ".git").exists()] if work.is_dir() else []
    row(bool(repos), "받은 저장소: " + (", ".join(d.name for d in repos) or "없음"), "`/core:init <역할>`")
    own = work / mine if mine else (repos[0] if repos else None)
    envd = {}
    if own and (own / ".claude" / "settings.local.json").exists():
        try:
            envd = json.loads((own / ".claude" / "settings.local.json").read_text(encoding="utf-8")).get("env", {})
        except Exception:
            envd = {}
    cf = creds.find(work) or (work / creds.NAME)
    cvals = creds.read(cf) if cf.exists() else {}
    row(cf.exists(), f"자격증명 파일 {cf}", "Claude에게 \"처음이야, <역할>\"이라고 말하면 만든다")
    has = lambda k: bool(envd.get(k) or os.environ.get(k) or cvals.get(k))
    row(has("HARNESS_ME"), f"내 이름(HARNESS_ME) {envd.get('HARNESS_ME', '')}", "`/core:init <역할> --name 홍길동`")
    row((work / "memo" / "people" / (envd.get("HARNESS_ME") or "_") / "README.md").exists(), "내 메모 폴더", "memo 저장소를 받은 뒤 init 다시")
    row(has("BITBUCKET_API_TOKEN"), "Bitbucket 개인 API 토큰 (PR·승인·머지가 내 이름으로)", f"{cf.name}를 열어 안의 2단계대로 — 대화창에는 붙여 넣지 않는다")
    if has("BITBUCKET_APP_PASSWORD") and not has("BITBUCKET_API_TOKEN"):
        row(False, "앱 비밀번호가 남아 있다 — 2026-06-09 폐지돼 동작하지 않는다", "위의 개인 API 토큰으로 바꾼다")
    row(has("JIRA_EMAIL") and has("JIRA_TOKEN"), "Jira 이메일·토큰 (티켓·댓글·상태)", f"{cf.name}를 열어 안의 3·4단계대로")
    for ok, what, nxt in verify_tokens({**cvals, **{k: os.environ[k] for k in creds.KEYS if os.environ.get(k)}}):
        row(ok, what, nxt)
    if own:
        tr = run("git", "ls-files", "--error-unmatch", ".claude/settings.local.json", cwd=own)
        row(tr.returncode != 0, "자격증명 파일이 커밋되지 않는다", "`git rm --cached .claude/settings.local.json` 뒤 토큰을 폐기·재발급")
    pl = run("claude", "plugin", "list")
    row(pl.returncode == 0 and "core" in pl.stdout, "플러그인 core", "`claude plugin install core@team-harness`")
    rows.append("  · 사람만 할 수 있는 것: 내 폴더에서 Claude를 한 번 열고 '이 폴더를 신뢰하시겠습니까'에 '신뢰' · 토큰 발급(위 파일 안 4단계)")
    print("설치 점검 — " + str(work)); print("\n".join(rows))
    return 0 if all(r.startswith("  ✓") or r.startswith("  ·") for r in rows) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", nargs="+", help="`check` = 설치 점검(비밀 값은 보이지 않는다) · 역할(백엔드·기획자·프론트·퍼블리셔·에이전트·운영·문서총괄) 또는 저장소 이름, 또는 `add <저장소>`")
    ap.add_argument("--token", help="(CI·문서 총괄용) Bitbucket 저장소 액세스 토큰 — settings.local.json에 저장(커밋 안 됨)")
    ap.add_argument("--user", help="Bitbucket 사용자명 — PR 생성·승인·머지가 이 사람 이름으로 남는다 (권장)")
    ap.add_argument("--bitbucket-token", help="개인 Atlassian API 토큰(Bitbucket 범위: 저장소 읽기·쓰기, PR 읽기·쓰기) — PR·승인·머지가 이 사람 이름으로. settings.local.json에 저장(커밋 안 됨)")
    ap.add_argument("--app-password", help="Bitbucket 앱 비밀번호 (--user와 함께). settings.local.json에 저장(커밋 안 됨)")
    ap.add_argument("--jira-email", help="Jira 이메일 (issue.py)")
    ap.add_argument("--jira-token", help="Atlassian API 토큰 (issue.py). settings.local.json에 저장(커밋 안 됨)")
    ap.add_argument("--work", help="저장소들을 둘 부모 폴더 (기본: 자동)")
    ap.add_argument("--no-plugins", action="store_true", help="플러그인 설치를 건너뛴다 (시험용)")
    ap.add_argument("--name", help="내 이름 — memo/people/<이름>/ 폴더와 HARNESS_ME. 기본: git config user.name")
    a = ap.parse_args()
    work = Path(a.work).resolve() if a.work else find_work(Path.cwd().resolve())
    lines = [f"work = {work}"]
    if a.what[0] in ("--check", "check"):
        return check(work, a.what[1] if len(a.what) > 1 else None)

    if a.what[0] == "add":
        for name in a.what[1:]:
            lines.append(clone(work, name, "읽기용 추가"))
        print("\n".join(lines)); return 0

    key = a.what[0]
    mine = ROLES.get(key, key)
    if mine not in READS and mine != "harness":
        sys.exit(f"모르는 역할/저장소: {key}. 역할: {', '.join(ROLES)} / 저장소: {', '.join(READS)}")
    # 토큰이 먼저다 — 비공개 Bitbucket은 git 자격증명 없이는 받을 수 없다. 토큰 파일에서 git 자격증명을 저장해 두면 clone·마켓플레이스·push가 묻지 않는다
    if BASE.startswith("https://"):
        creds.load(work)
        tok = os.environ.get("BITBUCKET_API_TOKEN")
        if not tok:
            cp, made = creds.ensure(work)
            open_for_person(cp)
            lines.append(f"  토큰     {cp} — {'만들어' if made else ''} 열어 두었다. 파일 안의 4단계대로 토큰 둘을 만들어 붙여 넣고 저장한 뒤 \"다 넣었어\"라고 말한다(대화창에는 붙여 넣지 않는다).")
            lines.append("  저장소는 토큰이 들어온 뒤에 받는다 — 회사 저장소는 비공개라 열쇠가 먼저 필요하다.")
            print("\n".join(lines)); return 0
        host = re.sub(r"^https://([^/]+)/.*$", r"\1", BASE)
        r = subprocess.run(["git", "credential", "approve"], input=f"protocol=https\nhost={host}\nusername=x-bitbucket-api-token-auth\npassword={tok}\n\n",
                           capture_output=True, text=True)
        lines.append(f"  git 열쇠 {host} — 토큰으로 저장했다(이 PC의 git 자격증명 저장소에, 값은 보이지 않는다)" if r.returncode == 0 else f"  git 열쇠 저장 실패 — {r.stderr.strip()[-120:]}")
    lines.append(clone(work, mine, "자기 것 — 쓰기·커밋·PR"))
    for r in READS.get(mine, []):
        lines.append(clone(work, r, "읽기용"))
    env = {"BITBUCKET_TOKEN": a.token, "BITBUCKET_API_TOKEN": a.bitbucket_token, "BITBUCKET_USER": a.user, "BITBUCKET_APP_PASSWORD": a.app_password, "JIRA_EMAIL": a.jira_email, "JIRA_TOKEN": a.jira_token}
    if a.app_password:
        lines.append("  ⚠️ 앱 비밀번호는 2026-06-09에 Bitbucket이 폐지했다 — 개인 API 토큰(Bitbucket 범위)으로 바꾼다")
    cp, made = creds.ensure(work)
    if any(env.values()):   # 옛 방식(명령줄로 넘김) — 파일에 넣되, 대화를 지난 토큰은 폐기·재발급을 권한다
        creds.put(work, {k: v for k, v in env.items() if k != "BITBUCKET_APP_PASSWORD"})
        lines.append(f"  자격증명 {cp}  — 넘겨받은 값을 넣었다. ⚠️ 대화창으로 받은 토큰이면 대화 기록에 남았다 — 폐기하고 새로 만들어 이 파일에 직접 붙여 넣는 것을 권한다")
    else:
        have = creds.read(cp)
        miss = [k for k in ("BITBUCKET_API_TOKEN", "JIRA_EMAIL", "JIRA_TOKEN") if k not in have]
        lines.append(f"  토큰     {cp}  " + ("— 빈 양식을 만들었다" if made else "— 있음") + (f". 비어 있는 것: {', '.join(miss)} → 이 파일을 열어 두었다. 파일 안의 4단계대로 만들어 붙여 넣고 저장한 뒤 \"다 넣었어\"라고만 말한다(대화창에 붙여 넣지 않는다)" if miss else " · 다 채워져 있다"))
        if miss:
            open_for_person(cp)
    name = my_name(a.name)
    lines += setup_memo(work, name)
    if name:
        for r in [mine] + READS.get(mine, []):   # 어느 저장소의 세션에서 /core:note 를 해도 내 폴더를 찾도록
            if (work / r).exists() and r != "memo":
                write_env(work / r, {"HARNESS_ME": name})
        lines.append(f"  이름     HARNESS_ME={name} → 각 저장소 .claude/settings.local.json (커밋되지 않는 파일)")
    if not a.no_plugins:
        lines += install_plugins(mine)
    lines.append("")
    lines.append("이제 사람이 할 것 (한 번):")
    lines.append(f"  1. Claude에서 **내 폴더 하나** {work / mine} 를 연다 — 앞으로도 이 폴더에서만 연다. 옆의 폴더들은 에이전트가 읽는 곳이다")
    lines.append("  2. '이 폴더를 신뢰하시겠습니까?'가 뜨면 '신뢰' — 보안 확인이라 대신 누를 수 없다")
    lines.append("  3. 토큰 파일이 비어 있으면 열린 파일 안의 4단계대로 채우고 \"다 넣었어\"라고 말한다 — 에이전트가 `init check`로 확인한다")
    lines.append("그 뒤로는 평소처럼 말하면 된다(\"정책 써 줘\", \"PR 봐줘\", \"이거 남겨 줘\"). git·명령어는 없다.")
    print("\n".join(lines)); return 0


if __name__ == "__main__":
    sys.exit(main())
