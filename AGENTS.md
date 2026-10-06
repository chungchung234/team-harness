# team-harness PoC — 이 저장소의 지도

이 저장소는 팀 하네스의 PoC다. 사람은 대부분 "써 보고 싶어" 또는 "이게 뭐야"라고 말한다.

- **"써 보고 싶어", "시연 환경 만들어 줘", "처음이야"** → `python3 demo/try.py` 를 돌린다(기본 위치 `~/team-harness-work`). 끝에 나오는 "이제 이렇게 써 보세요"를 사람 말로 전한다. git·명령어 이야기는 하지 않는다. Claude Code 플러그인(team-harness 마켓플레이스)이 사용자 범위로 설치된다는 것은 한 줄로 미리 말한다. 원하지 않으면 `--no-plugins`.
- **"이게 뭐야", "핵심이 뭐야"** → `PHILOSOPHY.md`의 "다섯 가지를 지킵니다"를 쉬운 말로 전한다. 설계 세부는 묻기 전에는 꺼내지 않는다.
- **"우리 팀 구조 정하자", "저장소 어떻게 나눌까", "저장소 하나 더"** → core 플러그인의 `team` 스킬. 대화로 정하고, 사람이 "승인"한 뒤에만 `team.json`에 적는다.
- **하네스 자체를 고치는 일**(하네스 담당) → `docs/하네스-담당.md`. 플러그인을 고친 뒤에는 `python3 build.py`, 저장소 골격이 바뀌면 `python3 sync.py update demo/*`.

| 경로 | 무엇 |
|---|---|
| `PHILOSOPHY.md` | 하네스의 철학 |
| `.claude-plugin/marketplace.json` · `plugins/` | Claude Code 플러그인 마켓플레이스 `team-harness` (core + 역할 5) |
| `demo/` | 시연 저장소 일곱(product·backend·agent·frontend·ui·infra·memo) — 예시 정책서 POL-01·스펙 SPEC-01 포함. `demo/try.py`가 이것으로 시연 환경을 만든다 |
| `team.json` | 팀 구성 — 저장소·주인(역할)·읽기·문서 종류·플러그인 |
| `build.py` · `sync.py` · `remote.py` · `remotes.json` · `repo-template/` | 하네스 담당용 도구 |
| `docs/` | 구조·동작·시연·팀에 맞추기·하네스 담당 문서 |
| `tests/` | 회귀 시험 |
