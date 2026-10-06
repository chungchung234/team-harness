# team-harness

Claude Code로 함께 일하는 팀을 위한 **하네스** PoC입니다.

에이전트는 모델과 하네스로 이루어져 있습니다. 모델을 뺀 나머지, 곧 저장소를 어떻게 나누는지, 지도 파일, 자동 검사, 스킬, 양식, 승인 규칙이 하네스입니다. 이 저장소는 그 하네스를 Claude Code 플러그인으로 묶은 것입니다. 왜 이렇게 짰는지는 [PHILOSOPHY.md](PHILOSOPHY.md)에 있습니다.

## 구조

```
team-harness/
├─ PHILOSOPHY.md                 하네스의 철학
├─ .claude-plugin/marketplace.json   이 저장소 전체가 플러그인 마켓플레이스 "team-harness"
├─ plugins/
│   ├─ core/                     모든 저장소 공통 — 훅(저장 검사·이슈 키·대화 중 변경 알림), 스크립트, 공통 스킬, 공통 규칙
│   └─ product/ dev/ frontend/ ui/ infra/   역할별 스킬 (기획·개발·프론트·퍼블리셔·운영)
├─ repo-template/                저장소 지도(AGENTS.md)와 양식의 원본
├─ sync.py                       팀 저장소의 골격(지도·설정·검사 파이프라인)을 만들고 고친다
├─ build.py                      공통 스크립트를 역할 플러그인에 복사하고 버전을 맞춘다
├─ remote.py                     원격 저장소를 만들고 설정한다 (Bitbucket)
├─ remotes.json                  팀에 맞출 값 — 원격 주소, Jira, 메일 도메인, 마켓플레이스
├─ demo/                         시연용 팀 저장소 7개와 예시 문서(주문 취소 정책·스펙)
│   └─ try.py                    내 컴퓨터에 시연 환경을 만든다
└─ tests/                        회귀 시험
```

팀 저장소는 역할마다 하나씩입니다. 기획은 `product`, 개발은 `backend`·`agent`, 화면은 `frontend`·`ui`, 운영은 `infra`, 개인 메모는 `memo`에 씁니다. 저장소에는 지도와 설정만 있고, 동작은 모두 플러그인에서 옵니다.

## 시연 (5분)

필요한 것: Claude Code, git, python3. Bitbucket이나 Jira는 필요 없습니다.

1. 이 저장소를 받아 그 폴더를 Claude Code로 열고 **"써 보고 싶어"** 라고 말합니다. (직접 하려면 `python3 demo/try.py`)
2. 기획자·백엔드·프론트 세 사람의 폴더가 생깁니다. Claude Code 창을 세 개 열고, 처음 열 때 '신뢰'를 누릅니다.
3. 기획자 창에서 **"주문 취소 정책에서 취소 가능 시간을 30분에서 1시간으로 바꿔 줘"**
4. 백엔드 창과 프론트 창에서 **"지금 내 스펙 상태 어때?"**

아무도 전하지 않았는데, 두 창의 Claude가 바뀐 정책과 영향받는 자기 스펙을 먼저 이야기합니다.

## 우리 팀에 맞추기

바꿀 곳은 `remotes.json` 하나입니다.

| 값 | 무엇 |
|---|---|
| `base` | 팀 저장소들이 있는 원격 주소 |
| `jira` | 이슈 트래커 주소와 프로젝트 키 |
| `company_email_domain` | 커밋 메일 검사용 도메인 (비우면 검사하지 않는다) |
| `marketplace`, `marketplace_add` | 이 플러그인 마켓플레이스를 받을 곳 |

바꾼 뒤 `python3 sync.py update <저장소들>`와 `python3 build.py`를 돌립니다.

## 아직 PoC입니다

- GitHub 주소로 플러그인을 설치하는 것은 아직 시험하지 않았습니다. 시연은 이 폴더를 마켓플레이스로 씁니다.
- Jira 연동(티켓 상태 읽기, 댓글로 질문하기)은 만들어 두었지만 실제 Jira에 연결해 보지는 않았습니다.
- 시연 중 에이전트가 허용 목록 밖의 명령을 쓰면 실제 앱에서 "허용할까요?"가 뜹니다. 세 창 시연에서 드물게 한 번 정도 남아 있습니다.
