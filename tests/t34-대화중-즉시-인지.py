#!/usr/bin/env python3
"""T34 — 대화 중 즉시 인지. backend 세션을 열어 두고(턴 1), 그 사이 product origin에 정책 개정을 밀어 넣은 뒤(턴 2 직전),
턴 2에서 에이전트가 [지금]·[영향] 줄로 바로 아는지 본다. UserPromptSubmit 훅(prompt_check.py)의 실측."""
import json, os, subprocess, sys, time, uuid
from pathlib import Path

TEAM = Path("/home/claude/team7")
BE = TEAM / "backend"
OTHER = TEAM / "product-other"
PLUG = Path("/home/claude/harness/plugins")

env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
env["CLAUDE_EFFORT"] = "low"
env["HARNESS_CHECK_INTERVAL"] = "0"
cmd = ["timeout", "420", "claude", "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
       "--no-session-persistence", "--session-id", str(uuid.uuid4()), "--strict-mcp-config", "--setting-sources", "project",
       "--plugin-dir", str(PLUG / "core"), "--plugin-dir", str(PLUG / "dev")]
p = subprocess.Popen(cmd, cwd=BE, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1)

def send(text):
    p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": text}}) + "\n"); p.stdin.flush()

def wait_result(tag):
    out = []
    while True:
        line = p.stdout.readline()
        if not line:
            break
        try:
            ev = json.loads(line)
        except Exception:
            continue
        out.append(ev)
        if ev.get("type") == "result":
            print(f"--- {tag}: {ev.get('num_turns')}턴 ${ev.get('total_cost_usd', 0):.2f} {ev.get('duration_ms', 0)/1000:.0f}s")
            print((ev.get("result") or "")[:900])
            return out
    return out

t0 = time.time()
send("세션 시작 알림에 [변경]이나 [지금] 줄이 있었어? 있으면 그대로 옮겨 적고, 없으면 '없음'. 파일은 열지 말고 2줄 안에.")
ev1 = wait_result("턴 1")

# 그 사이 — 기획 쪽이 POL-01 정책 2의 5초를 3초로 바꿔 올린다
pol = next(OTHER.glob("docs/policy/POL-01*.md"))
s = pol.read_text(encoding="utf-8")
s = s.replace("시스템은 즉시 기록하고", "시스템은 **3초 이내에** 기록하고", 1)
s = s.replace("| A2 | 취소이 기록되면 | 관리자 화면에 취소 횟수가 표시된다 |", "| A2 | 취소이 기록되면 | 관리자 화면에 취소 횟수가 표시된다 |\n| A3 | 주문자가 검사 화면을 취소하면 | 3초 이내에 취소 1회로 기록된다 |", 1)
s = s.replace("updated: 2026-09-25", "updated: 2026-10-01", 1)
s += "\n## 개정 이력\n| 날짜 | 무엇 | 근거 |\n|---|---|---|\n| 2026-10-01 | 정책 2 \"즉시\" → 3초, A3 추가 | 기획 회의 M-20261001 #1 |\n"
pol.write_text(s, encoding="utf-8")
g = lambda *a: subprocess.run(["git", "-c", "user.name=기획자", "-c", "user.email=p@t", *a], cwd=OTHER, capture_output=True, text=True)
g("add", "-A"); r = g("commit", "-q", "-m", "ORD-70 POL-01 정책 2 즉시→3초, A3"); print("commit:", r.returncode, r.stderr.strip()[-100:]); r = g("push", "-q", "origin", "master"); print("push:", r.returncode, r.stderr.strip()[-100:])
print("--- 그 사이: product origin에 밀어 넣음", g("log", "--oneline", "-1").stdout.strip())

send("방금 내가 말하기 전에 새로 들어온 알림 줄([지금]·[영향]·[결정])이 있어? 있으면 그 줄들을 그대로 옮겨 적고, 그게 내 스펙에 뜻하는 바를 한 문장으로. 파일은 열지 말고 4줄 안에.")
ev2 = wait_result("턴 2")
p.stdin.close()
try:
    p.wait(timeout=30)
except Exception:
    p.kill()
err = p.stderr.read()
if err.strip():
    print("--- stderr:", err[-600:])
print(f"--- 전체 {time.time()-t0:.0f}s")
# 훅 출력이 실제로 컨텍스트에 들어갔는지: 턴 2 이벤트에서 [지금] 문자열 검색
blob = json.dumps(ev2, ensure_ascii=False)
print("--- 턴 2 이벤트에 훅 출력 포함:", "방금 커밋" in blob, "/ [영향] SPEC-01:", "전제가 바뀐 내 문서" in blob)
