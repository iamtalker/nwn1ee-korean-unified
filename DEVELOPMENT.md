# 개발 현황 및 다음 작업 (인수인계용)

사용자용 설명은 [README.md](README.md). 이 문서는 작업을 이어받기 위한 메모입니다.

## 현재 상태 (v0.1.2)

| 영역 | 상태 |
|---|---|
| 엔진·UI 한글 (`nwmain.exe` 바이너리 패치 + `version.dll` 프록시) | 완료, 8193.37 원본 해시 전용 |
| 캠페인 선택 화면(Nuklear) | 완료 (`width`/`query` 후킹으로 CP949 쌍을 음절 글리프로 묶음) |
| 본편 OC/SoU/HotU | 완료 (`assets/dialog.tlk`, 번역률 약 99.8%) |
| The Winds of Eremor, Neverwinter Chess | 완료 (번역 CSV → 로컬 `.mod` 재패킹) |
| Contest of Champions, The Dark Ranger's Treasure, To Heir is Human | 완료 (기계번역 + 이름·UI 수동 교정, 긴 문단은 기계번역 위주) |
| DoD/ToTM/PotSC/DoIWD | 완료 (창작마당 `nwn1ee_dod_kr` 자동 다운로드 후 설치) |
| Dark Dreams of Furiae | 완료 (고유 문장 2,568개 기계번역 + 이름·UI 377개 수동 교정, 긴 대사는 기계번역 위주) |
| Witch's Wake, ShadowGuard, Kingmaker, Wyvern Crown, Infinite Dungeons | 완료(v0.1.6): 기계번역 + 전역 용어 교정(557개) 자동 적용. 이름·UI 개별 검수는 **미완** |
| 커뮤니티 7종 | **미구현**. NWSync 캐시에서 텍스트 추출·기계번역은 가능(`tools/nwsync_extract.py`), 적용 방식 미정 | **미구현** (설치 창에 "미구현" 표시) |

## 구조

```
installer/nwn_ko_installer.py   GUI + CLI(--list/--patch-all/--restore-all). 항목은 Item 서브클래스
installer/engine_patch.py       nwmain.exe 바이너리 패처 (patch_bytes)
installer/modbuild/             모듈 번역 빌더 (premium/<short>/config.py + inline/*.csv)
hook/                           version.dll 소스 (MinGW-w64 로 빌드)
tools/build_release.py          릴리스 zip (assets/ 필요)
assets/                         version.dll, dialog.tlk  (git 제외, 릴리스 zip 에만 포함)
```

새 모듈 추가 절차:
1. `installer/modbuild/premium/<short>/config.py` 와 `inline/*.csv`(열: Resource,ResType,FieldPath,LangID,StrRef,Text) 추가
2. `nwn_ko_installer.py` 의 `Todo(...)` 를 `BuiltMod(...)` 로 교체
3. README 현황표, NOTICE 갱신 → 새 버전 태그로 릴리스

## 번역 작업 계획

규모(미번역 인라인 텍스트, 원본 저장소 `wonilclone/nwn_ee_korean/premium/` 기준 추출분):

| 모듈 | 항목 수 |
|---|---|
| Witch's Wake | 약 6,160 |
| ShadowGuard | 약 8,100 |
| Kingmaker | 약 10,070 |
| Wyvern Crown of Cormyr | 약 17,430 |
| Infinite Dungeons | 약 28,830 (대부분 GIT 인스턴스 이름이라 고유 문자열은 훨씬 적음) |

**방식**: 오프라인 기계번역(NLLB-200 distilled 600M, CTranslate2 int8) → 자동 검사로 의심 항목 선별 → 사람이(또는 Claude 가) 교정.
- 같은 영어 문장은 한 번만 번역(중복 제거). Contest of Champions 는 1,076행 중 고유 문장이 222개였음.
- 속도: CPU(Ryzen 5 5600G)에서 약 12문장/초. 소규모 모듈은 수 분.
- 게임 토큰(`<FirstName>`, `<CUSTOM500>` 등)은 자리표시자로 보호 후 복원 (`tools/mt_translate.py`).
- 용어는 `dialog.tlk`(본편 번역)의 지명·주문·아이템·직업 이름을 우선 사용해야 함 (용어집 단계는 **미구현**).

### 기계번역 시험 결과 (Contest of Champions, 60문장)

잘 되는 것: 일반 안내문, 상점 인사, 시스템 메시지.
교정이 꼭 필요한 것:
- 문맥 없는 짧은 단어 오역 (`Goodbye` → "안녕하세요", `2000` → "2000년", `No` → "아니")
- 존대/반말 혼용 ("체크인할 수 없어, 현재 팀은 잠겨있어요")
- 고유명사/직업명 음차 ("마직 매장", "워리어 매장")
- 문장 끝의 토큰 뒤 내용 누락 (`The Battle Master is: <CUSTOM500>` → 번역 일부 소실)

→ **자동 검사 규칙** 필요: 숫자만 있는 문자열은 번역하지 않음, 길이 3자 이하 문장 별도 처리, 토큰 개수 불일치, 경어체 일관성, 용어집 불일치.

## 환경 / 함정 메모

- 게임 빌드 8193.37 (`nwmain.exe` sha256 `3b7cb125…`). 업데이트되면 오프셋 재조사 필요 (`hook/nwn_korean_hook.c` 의 `NKV2_*_RVA`, `installer/engine_patch.py` 의 `VERSION_OFFSETS`).
- 문서 폴더: 게임은 `Neverwinter Nights` 폴더가 먼저 있고 `nwn.ini` 가 없으면 `Neverwinter Nights.0` 을 새로 만든다. 설치 프로그램은 `nwn.ini` 가 있는 폴더를 찾는다.
- 이 저장소에는 게임 바이너리, 유료 모듈, 원문 영어 텍스트를 넣지 않는다. 폰트는 설치 시 PC 의 `malgun.ttf` 를 복사.
- 테스트는 반드시 `NWN_GAME_DIR`/`NWN_DOCS_DIR` 환경변수로 **격리된 폴더**에서 한다 (빈 값이면 실제 게임에 적용되므로 주의).
- 릴리스 전: zip 을 풀어 `run_installer.bat` 와 `--list` 까지 확인.
- 작업 폴더(임시/테스트)와 업로드 폴더(깃 클론)는 분리해서 사용한다.

## 인수인계 (v0.1.21 시점, 새 세션용) — 가장 먼저 읽을 것

### 한 줄 요약
NWN1 EE(8193.37) 통합 한글패치. 모든 캠페인(본편·확장·프리미엄·커뮤니티 20개)에 **기계번역 + 용어 정리**가 들어가 있고, 지금은 "다듬는 단계"(로컬 Qwen 후편집) + "실제 게임에서 확인하는 단계"다.

### 위치 (모두 이 PC)
| 용도 | 경로 |
|---|---|
| 깃 저장소(업로드용) | `C:\Program Files (x86)\Steam\steamapps\common\한글패치\nwn1ee-korean-unified` → GitHub `iamtalker/nwn1ee-korean-unified` |
| 번역 작업 데이터 백업 (영어 원문 포함, **깃에 올리지 말 것**) | `...\common\한글패치\번역작업백업\` (mt/ community/ ncs/ llm/) |
| 로컬 LLM 일체 | `C:\claude program\1. 개발중\local-llm` (bin, models, *.bat, room/) |
| 순정 게임 폴더 백업 zip | `...\common\Neverwinter Nights.zip` (6.8GB, 현재 게임 폴더와 파일 단위로 일치 확인됨) |
| 문서 폴더 | `C:\Users\misti\Documents\Neverwinter Nights` (nwsync 4GB = 내려받은 커뮤니티 캠페인) |
| 스크래치(세션마다 사라짐) | `...\scratchpad` — 중요한 것은 위 백업 폴더에 있음 |

### 사용자 선호 / 규칙 (꼭 지킬 것)
- 컨텍스트 사용률은 **사용자가 알아서 본다. 새 세션 전환을 권하는 말을 하지 말 것.**
- 토큰을 아끼고 싶어 한다. 큰 일은 로컬 Qwen에 맡기고 Claude는 검증·판정만(아래 "보정 작업").
- 소음에 민감(그래픽카드 팬). 서버·보정을 켜기 전에 사용자가 PC를 쓰는 중인지 고려.
- 마일스톤마다 커밋 + 릴리스까지 한다(`tools/build_release.py vX.Y.Z` → `gh release create`). 커밋 메시지 끝에 Co-Authored-By 줄.
- 삭제·공개 등 되돌리기 어려운 일, 시스템/전원 설정 변경, 파일 다운로드는 먼저 허락을 받는다.
- 게임 바이너리·유료 모듈·영어 원문은 저장소/릴리스에 넣지 않는다.

### 도구 환경 함정
- 이 PC에서 `python`은 Store 스텁 → **`py -X utf8`** 사용(heredoc 로 한글 소스를 넘길 때 `-X utf8` 필수). `py` 런처는 공백 든 인자를 쪼갤 수 있으니 환경변수로 경로 전달.
- 이 도구 환경에서 bash/py 코드 안의 `\\`가 한 번 풀려 `\n`이 실제 개행이 되거나 `\b`가 백스페이스가 된다 → 개행·역슬래시가 필요한 코드는 `chr(92)`를 쓰거나 Write 도구로 파일을 만든다.
- 한글 경로에서 `cmd /c 상대경로.bat` 실행이 안 된다(전체 경로로). `Start-Process -ArgumentList`는 공백 든 인자를 따옴표로 감싼다 → 한 문자열로.
- 설치 테스트는 반드시 격리: `NWN_GAME_DIR`/`NWN_DOCS_DIR`(+`LOCALAPPDATA`, `NWN_NWSYNC_DIR`) 환경변수. 비면 실제 게임에 적용된다.

### 구조 (자세한 건 위쪽 "구조" 절)
- `installer/nwn_ko_installer.py` GUI+CLI(`--list`, `--patch-all`, `--restore-all`, `--restore-community`), 작업은 스레드로 실행(응답 없음 방지).
- 확장 모듈: `installer/modbuild/premium/<short>/inline/*.csv` + `ncs/ncs.csv`(스크립트 문장, CRC 검증) → `build_premium.py`가 모듈/HAK 재패킹.
- 커뮤니티: `installer/community/<slug>/translations.csv` + `ncs.csv` → NWSync 캐시에서 리소스를 꺼내 번역본을 **`문서\development`**(override는 컨테이너보다 우선순위가 낮아 무효)에 설치. 캠페인별 번역본은 `문서\ko_campaigns\<slug>\`(v0.1.24~, `_complete.json` 에 NWSync manifest+번역 csv 해시를 기록해 바뀌면 자동 재생성)에 두고, [패치]는 그 폴더를 development 에 복사해 전환(활성은 항상 하나 — 같은 이름 파일 6천여 개 충돌 때문). 일괄 패치는 번역본만 미리 만든다(`CommunityModule.prepare`), 일괄 원복은 `purge`.
- NCS 문자열 번역: `installer/modbuild/ncs_tool.py`(점프 오프셋 재계산). 파이프라인 `tools/ncs_extract*.py` → `mt_translate.py` → `tools/ncs_pack.py`.
- 용어집: `tools/build_glossary.py`(본편 TLK 12,204쌍), `tools/apply_glossary.py`.
- 새 캠페인을 내려받으면 목록 맨 아래 "번역 없음" 묶음에 표시된다(번역은 개발자가 추가).

### 상태 (릴리스 v0.1.20 → 이 문서가 들어간 v0.1.21)
| 항목 | 상태 |
|---|---|
| 엔진·UI·본편 | 완료(사용자 확인) |
| 확장·프리미엄 | 번역 포함. Kingmaker 대사는 게임에서 확인됨, 나머지 미확인 |
| 커뮤니티 20개 | 번역 포함. v0.1.16에서 충돌 수정(구조 검증 통과), **게임 안 확인은 사용자 대기 중** |
| Qwen 후편집 | 약 2.6만 / 8.55만 문장 처리(승인 ok 약 1.9만). **설치 프로그램에는 아직 연결 안 됨** |

### 남은 일 (우선순위)
1. **사용자가 "패치 후 게임 실행하니 에러"를 보고함** — 정확한 에러 문구·시점 확인 필요. 크래시 파일: `문서\...\crashreport\*.nwcrash.txt`. 확인된 패턴: 크래시가 쌍으로 생김(하나는 `nwsync: database is locked` = 게임이 거의 동시에 두 번 실행되거나 이전 nwmain.exe 가 남아 있을 때), 다른 하나는 `exception=16`이며 10-15·10-16 오전(정상 동작하던 때)에도 같은 주소로 있었음 → 종료 시/실행 직후 크래시일 수 있음. 순정 상태에서 같은 에러가 나는지(전체 원복 후 실행)부터 비교할 것.
2. (해결됨: 5건 모두 단독 설치 시 정상 확인, Shadewood·Ironlord 의 메시지는 '이전 캠페인 먼저' 안내) 커뮤니티 5건(Reptile God 일부 영어, Crimson Tides 멈춤, Almraiven 손상, Shadewood·Ironlord 에러 종료)의 **게임 내 확인**. Reptile God 영어 잔존분은 v0.1.22에서 330행 추가(Qwen 352 + 직접 165, 토큰 검증 통과)로 해결 — 게임 내 확인 대기. 기존 행은 배포본 그대로 유지(백업 all.json 은 배포본과 달라 그대로 재생성하면 안 됨).
   보정 스크립트(`llm_postedit.py`)는 v0.1.22에서 강제 종료해도 번역이 유실되지 않게 고침(기록 파일에 번역문 저장·복구, 20건마다 저장). 예전 결함으로 유실된 367건은 이어하기 때 자동 재처리됨.
3. **(2차 감수 도구 완료, 연결은 남음)** `tools/review_triage.py <백업폴더>` 가 `llm/review/final.json`(규칙 통과한 Qwen 번역만, {영문:한글})을 만든다. 규칙: 허용 문자 밖(이모지·키릴 등)·반복·설명문 섞임·원문에 없는 기호·잘림/부풀림 거부, `<StartCheck>[..]` 대괄호 복구. 표본 100개 판정(비김 제외) Qwen 승률 72%(대화 82, 긴문장 71, 이름 69, UI 60). **Qwen 보정이 끝난 뒤 다시 실행**해서 final.json 을 갱신할 것. 주의: 배포본 translations.csv 에는 영어가 없어서 영문 키로 덮으려면 NWSync/모듈에서 영어를 다시 추출해 행과 맞춰야 하고, 백업 all.json 은 배포본과 다르므로(Reptile 확인) 각 모듈이 어떻게 만들어졌는지 먼저 확인할 것.
3-0. **(v0.1.26: 고유명사 통일 반영 + 설명문 섞인 Qwen 번역 42개를 기계번역으로 되돌림, `apply_review.py` 가 `final_v0.1.25.json` 과 비교해 되돌리기 처리, 3,428행 변경) (v0.1.25 에서 1차 감수 결과를 규칙 통과분만 반영함: `apply_review.py --no-names`, 358,226행 중 183,013행(51.0%) 변경, 행 수·키 열·토큰 검증 통과. 고유명사 통일(`name_unify.py --apply`)은 아직 미반영 → 다음 릴리스)** 연결 도구 설명: `tools/apply_review.py <백업폴더> [--write]`: 배포 CSV 에 영어가 없으므로 '예전 한국어 → 새 한국어'(기계번역+clean+전역교정 재현, 모호하면 제외, 토큰 불일치 제외)로 final.json·names_fixed.json 을 반영. 모의 실행 결과 358,929행 중 148,893행(41.5%) 변경 예상. 손으로 고친 행은 예전 값과 달라 보호됨. 순서: Qwen 종료 → `review_triage.py` → `name_unify.py --apply` → `apply_review.py --write` → 구조 검증 → 릴리스. NCS(ncs.csv)·본편 TLK 는 아직 미반영.
3-1. **Qwen 후편집 결과를 번역에 연결**: `번역작업백업\llm\all.llm.json`(게이트 v2 통과분, {영문:한글})을 `apply_mod.py`/`community_pack.py`/ncs 포장에서 우선 적용하도록 하고(원본 `all.json`은 불변), 재빌드·릴리스. 채택 기준은 아래 "연구" 절(게이트 v2).
4. 보정 계속: `local-llm\run-postedit-max.bat`(출근 전 켜 두는 용도, 이어하기·자동 재시작). 병렬 4/8/12 모두 초당 약 2.4~2.5문장(GPU 한계) → 나머지는 10시간 이상. 로그: `번역작업백업\llm\run.log, bat.log, server.log`.
5. 본편(OC/SoU/HotU)·DoD 4종 스크립트 문장: `.nwm` 재패킹 방식이 필요(development 방식은 캠페인 간 충돌 위험).
7-1. **(미룸) 게임 설정(옵션) 화면 번역** — 조사 결과(2026-10-17): 옵션 창에서 탭 이름·구역 제목(규칙 세트/로깅/그래픽/입력/멀티플레이어)은 dialog.tlk 에서 와서 한글이지만, **항목 이름은 영어**(Show Challenge Ratings, Game Log Chat Text 등). 이 문구는 TLK·BIF·lang/en 에 없고(검색 확인), `settings.tml` 의 설정 키(kebab-case, 예 `ruleset.show-challenge-ratings`)에서 엔진이 영어 제목(Title Case)으로 생성하는 것으로 보임(문서\settings.tml 의 `~~schema` 는 쓰기 전용 설명이며 `label =` 값은 다른 표기: 예 키 show-challenge-ratings 의 label 은 "Examine CR On Creatures", 화면 표시는 "Show Challenge Ratings" 라서 label 이 아님). "Value will not persist over restarts." 는 nwmain.exe(RVA 약 0xe4a778 문자열) 에 박혀 있음. 해결안: 후킹으로 글자 그리는 시점에 영어→한국어 표 치환(키 약 600개 + 부가 문구). 필요: C 컴파일러(w64devkit, 다운로드 허락 필요), 후킹 지점 RE. TLK 에 영어로 남은 2,687개(중복 제외)는 대부분 툴셋·맵 타일 이름이라 우선순위 낮음(목록: 번역작업백업\settings	lk_untranslated.json). 사용자 판단: 작업이 커 보여 나중으로 미룸.
7-00. **자동 전환 구현 완료(v0.2.0)**: E7(지웠다 다시 넣은 파일도 반영됨) 확인 → `hook/autoswitch.c`(nwn_korean_hook.c 에 #include, 같은 빌드 명령)가 시작 시 합집합 이름(20,475개)을 하드링크로 깔고 로그 `Loading Module: <해시>` 로 캠페인 전환(실측 1.2~2.2초, 시작 지연 6~7초), 공식 모듈이면 전부 삭제, 종료 시 정리, 비정상 종료 잔여는 `ko_campaigns\_dll_seed.txt` 로 다음 실행 때 정리. 설정 파일은 `bin\win32
wn_ko_autoswitch.txt`(설치 프로그램 [자동 전환] 항목이 작성, enabled=0/없음이면 아무것도 안 함). 실게임 시험: 커뮤니티 5개 모두 한글, 공식(OC)·ShadowGuard·Kingmaker 정상. 컴파일러: w64devkit 2.10.1(`C:\claude program	oolchain\w64devkit`, sha256 add1edf9…), 빌드: `gcc -shared -O2 -o assets/version.dll hook/nwn_korean_hook.c hook/version_proxy.c -lpsapi`(옛 소스로 빌드하면 배포본과 같은 98,404바이트). 프로토타입 `tools/campaign_watcher.py`(별도 프로세스 방식)는 참고용으로 남김. 미확인: 게임 업데이트 시 동작, 다른 PC 의 백신 반응.
7-0. **자동 전환 실험 결과(2026-10-17, 후킹 없이 development 폴더 동작만 조사)**: ① 게임은 `development` 의 **파일 목록을 시작할 때 정한다** — 게임 실행 후에 넣은 파일은 안 보임(E4). ② **내용은 열 때 읽는다** — 실행 후 같은 이름 파일의 내용을 바꾸면 반영됨(E5: 대사에 `[E5]` 표시 확인). ③ **실행 후 파일을 지우면 모듈 안의 원본으로 돌아감**(E6: 영어 대사, 오류 없음). ④ 한 번 지웠다가 다시 넣은 파일이 반영되는지는 미확인(E7, 게임이 꺼져 결과 못 받음). → **유력안(2번 방식)**: 시작 시 모든 캠페인의 파일 이름을 합집합으로 깔아 두고(내용은 아무 캠페인 것이나), 캠페인을 열 때(`campaign_watcher.py` 가 `Loading Module: <해시>` 로그를 읽음) 그 캠페인의 번역본으로 내용을 덮고 나머지 이름은 삭제. 걸림돌: 합집합 파일 수/용량, 전환 시간(복사 1.5~13초 vs 로드 약 20초), E7 확인. 안 되면 런처(게임 켜기 전에 캠페인 선택)나 후킹. 후킹은 모듈 로드 함수 RVA 0x565c50(2번째 인자 CExoString = 해시)이 후보이나 이 PC 에 C 컴파일러가 없음(w64devkit 재설치 필요, 다운로드는 허락 필요).
7. **(로드맵, 사용자 요청) 커뮤니티 캠페인 자동 전환**: 지금은 캠페인을 바꿀 때마다 설치 프로그램 [패치]로 전환해야 해서 폴더 방식의 이득이 속도뿐. 결정(사용자와 합의, 2026-10-17): 후킹을 먼저 시도하고 안 되면 재패킹. 재패킹 쪽 미확인 사항: NWSync 캐시 데이터를 바꾸면 게임이 되돌리는지/손상으로 보는지(시험하려면 문서
wsync 백업 후 파일 하나 교체). 1순위 조사: 엔진 후킹(`hook/nwn_korean_hook.c`)으로 모듈 로드 시점에 모듈 이름을 얻어 `development` 검색 경로를 해당 캠페인 폴더(`문서/ko_campaigns/<slug>`)로 바꾸기 → 20개 동시 설치. 안 되면 `.nwm`/HAK 재패킹. 사용자는 캠페인 5건 모두 단독 설치 시 정상임을 확인함(충돌이 원인으로 확정).
8. **(로드맵 맨 뒤) 더 나은 기계번역 모델 비교**: 현재 NLLB-200 distilled 600M(ct2 int8, CPU, 초당 12문장). 이 PC: Ryzen 5 5600G 6C/12T, RAM 16GB(Qwen 서버가 켜져 있으면 여유 거의 없음), GPU RX 6600 8GB(CTranslate2 는 CUDA 전용이라 CPU 로만 돎). 후보: 더 큰 NLLB(1.3B/3.3B), LLM 직접 번역, 한국어에 강한 모델. 같은 표본 100문장 익명 비교로 판정 → 좋으면 감수 미통과/미처리 문장에만 적용하고 방법서 v1.2 로 올리며 이유·측정을 이력에 기록. 기계번역 자체는 이미 끝난 상태라 급하지 않음(1차 감수 종료 후 GPU/메모리가 빌 때).
6. 새 커뮤니티 캠페인 추가 절차: 사용자가 게임에서 내려받음 → `tools/ncs_extract_community.py`, `mt/community_run.py` 방식으로 번역 → `apply_glossary.py` → `community_pack.py` → `ncs_pack.py --community` → `CommunityModule` 항목 추가 → 릴리스.

### 로컬 LLM / 공동 작업방
- 서버: `start-server.bat`(채팅 http://127.0.0.1:8080), `stop-server.bat`. 보정: `run-postedit.bat [병렬수]`, `-quiet`(2), `-max`(8, 절전 방지 포함). 서버가 소리 없이 죽은 적이 있어 실행기는 연속 실패 12회에 종료코드 2로 끝나고 배치가 서버를 재시작(최대 5회).
- 공동 작업방(의뢰인/Claude/Qwen): `start-room.bat` → http://127.0.0.1:8090. 방마다 Claude·Qwen 세션 기억, 받는 사람 체크박스. 사용자가 부를 때만 `claude -p`(읽기 전용 도구, 호출 부담 약 3.7천 토큰으로 최적화), `[[ORDER qwen]]`/`[[RUN postedit]]`(승인 필요).
- 맡길 일: 대량 번역·정리·분류. 맡기지 말 일: 사실 확인, 코드 설계. Qwen 출력은 반드시 자동 검증.

### 알려진 함정 (이미 한 번 겪음)
- `.orig` 백업이 오염되면 원복해도 순정이 안 된다: 우리 전용 폴더(`development`, 문서 `hak`의 번역 HAK)는 `.orig`를 만들지 않고 삭제하도록 고침(v0.1.17, v0.1.21).
- 순정 확인: 게임 폴더에 `.orig`·`version.dll` 없음, `nwmain.exe` 해시 `3b7cb125…`, Steam 무결성 검사. 순서는 "전체 원복 → 무결성 검사".
- `gff_tool` 쓰기 인코딩은 한글 CP949, 악센트 영문 CP1252(고침).
- 캠페인 업데이트로 이름·내용이 바뀌면 번역 일부가 영어로 남는다(오류 없이).


## 이전 인수인계 (v0.1.8 시점, 참고용)

- **v0.1.8**: 번역을 모듈 파일뿐 아니라 연결된 HAK 에도 적용(`installer/modbuild/premium/build_premium.py` 의 HAK 단계,
  `NWN_HAK_DIR` 환경변수, `BuiltMod` 이 HAK 를 `문서/hak` 에 설치·원복). Kingmaker 로 검증(적용 10,068개 중 모듈 1,390 + HAK 8,678).
  ShadowGuard/Witch's Wake/Wyvern Crown 도 격리 시험 통과. Infinite Dungeons(id_resources 193MB)는 v0.1.9 에서 시험 통과(적용 28,805개 = 모듈 24,975 + HAK 3,830, 약 6초). Dark Dreams of Furiae 는 번역 4,761개가 전부 `.nwm` 안에 있어 ddf.hak(708MB)은 건드리지 않음(약 2초).
- **커뮤니티**: NWSync 캐시에 20개 모듈 확인. 앞 10개(AHTD 0~6, Nature Abhors a Vacuum, EotB I·II)는 기계번역 완료,
  나머지 10개(Defender of the Crown, Return of the Ironlord, The Fall of Aielund Pt.1~3, Almraiven, Crimson Tides of Tethyr EE,
  Siege of Shadowdale EE, Against the Cult of the Reptile God 2.0, Shadewood)는 `scratchpad/mt/community_run.py` 로 백그라운드 번역 중이었음(약 9만 문장).
  완료되면 `mt/community_pack.py community ../pub/installer/community` 로 CSV 를 만들고 `CommunityModule` 항목(id/이름/slug)을 추가, 릴리스.
  v0.1.9: EotB I·II `translations.csv` 를 `installer/community` 에 포함. **나머지 10개는 번역 미완**(스크래치 mt/community 에서 진행 중, 약 8.7만 문장 ≈ 6~7시간).
  끝난 모듈마다 `community_pack.py` → 새 폴더만 `installer/community` 에 복사 + index.json 병합 + `CommunityModule` 추가 → 릴리스.
- 알려진 문제: 번역 품질은 기계번역 위주(이름·UI 만 일부 교정). 커뮤니티 override 방식은 게임 내 검증 전(실험적).
- 사용량 팁: 대화가 길어지면 요청마다 전체를 다시 읽어 한도가 빨리 줄어듦 → 새 세션에서 이 문서를 읽고 시작할 것.

## 작업 메모 (이전 중단 시점 기록, 참고용)

- **Witch's Wake** 번역 진행 중이었음: 고유 문장 2,874개, 기계번역은 약 800개까지 진행 후 PC 종료로 중단(결과 미저장).
  - 재개: `tools/mt_translate.py <inline 폴더> <출력.json>` — 이제 체크포인트(`.partial`)로 이어하기를 지원한다.
  - 이후: `tools/mt_fix.py`(깨진 항목 재번역) → 이름/UI 교정 JSON 작성 → `tools/apply_mod.py <short> <교정.json>` →
    `installer/nwn_ko_installer.py` 의 `Todo("ww", ...)` 를 `BuiltMod("ww", "Witch's Wake", "witchswake", "Witch's Wake.mod")` 로 교체 → README/DEVELOPMENT 갱신 → 릴리스.
- 다음 후보 순서: ShadowGuard(약 8,100) → Kingmaker(약 10,070) → Wyvern Crown(약 17,430) → Infinite Dungeons.
- 기계번역은 CPU 를 오래 점유하므로(약 4문장/초, 긴 문장은 더 느림) 낮 시간에 돌리는 것이 좋다.

## 용어집 단계 (v0.1.10 진행 중)

토큰 최소화 로드맵 1단계. 본편 `dialog.tlk`(영문/한글) 쌍에서 고유명사형 용어를 뽑아 기계번역에 적용한다. 토큰 비용 0.

1. `tools/build_glossary.py <en dialog.tlk(lang/en/data)> <assets/dialog.tlk> glossary.json` — 12,204쌍 (영문 TLK 는 cp1252, 한글 TLK 는 **cp949**)
2. `tools/apply_glossary.py glossary.json <all.json...> [--retranslate] [--dry]` — 정확 일치 치환 + (옵션) 문장 속 용어 보호 재번역. `.bak` 자동 보관.
   - 시험: shadowguard 정확 일치 115, 재번역 80. 전체 모듈 기준 정확 일치 약 2,449개가 기존과 달랐다.
   - 일반 조각("Talk to", "Thank you")이 용어로 잡히면 오히려 나빠지므로 `proper()` 필터(8자 이상, 마지막 단어가 전치사/대명사 아님)를 둠.
   - **아직 실제 all.json 에는 적용하지 않음(dry 만 실행)**. 다음 세션: 완료된 all.json 에 적용 → corr_*.json 재적용(apply_mod) → 재빌드 → 릴리스.
3. 설치 프로그램 GUI: 패치/원복/상태 확인을 작업 스레드로 옮겨 '응답 없음' 해소(v0.1.10). 대화상자는 `_ui_call` 로 메인 스레드에서 띄움.
- 환경 메모: bash heredoc 으로 `py -` 에 한글 소스를 넘기면 cp949 로 깨진다 → 한글이 든 편집은 파일로 저장해 `py -X utf8 파일` 로 실행할 것. `py` 런처는 공백 든 인자를 쪼갤 수 있으니 환경변수로 경로 전달.

- **v0.1.11 수정**: 커뮤니티 캠페인 번역은 `override/` 가 아니라 `문서\development/` 에 설치한다. 게임 문서(패치노트 v79)에 따르면 override 는
  HAK 같은 ERF 컨테이너 **아래**라 모듈/NWSync 리소스를 덮지 못하고, development 가 검색 경로 최상단이다. (v0.1.7~0.1.10 의 커뮤니티 번역은 그래서 영어로 나왔음)
- 알려진 한계: NPC 머리 위 말풍선(SpeakString)·스크립트 메시지는 컴파일된 `.ncs` 안에 있어 아직 영어다. 다음 과제: NCS 문자열 상수 치환(점프 오프셋 재계산 필요).

## v0.1.12 (용어집 적용 완료)
- 용어집(`tools/build_glossary.py`, `apply_glossary.py`)을 premium 9종 + 커뮤니티 10종에 적용(정확 일치 약 2,400, 문장 속 용어 재번역 약 1,400). 교정(`corr_global/ddf/darkranger/toheirishuman`)은 그 위에 다시 적용.
- 커뮤니티에 **Crimson Tides of Tethyr**(7,743행), **Siege of Shadowdale**(3,414행) 추가.
- 남은 커뮤니티 번역 중: Defender of the Crown, Return of the Ironlord, Aielund 1~3, Almraiven, Cult of the Reptile God 2.0, Shadewood. 끝나면 `community_pack.py` → 복사 → `CommunityModule` 추가.
- 다음 과제: (1) NCS 문자열 치환(NPC 머리 위 말풍선), (2) 용어집 재번역은 `--retranslate` 가 CPU 를 오래 쓰므로 새 모듈은 번역 직후 한 번에.

## v0.1.13 (NCS 스크립트 문자열 번역)
NPC 머리 위 말풍선(SpeakString)·시스템 메시지는 컴파일된 `.ncs` 의 문자열 상수라 GFF 번역으로는 닿지 않았다.
- `installer/modbuild/ncs_tool.py`: NCS 파서/치환기. 문자열 길이가 바뀌면 JMP/JSR/JZ/JNZ 상대 오프셋을 다시 계산한다(왕복 검증: Kingmaker 1,389개 바이트 동일).
- 저장소에는 영어를 넣지 않는다: `premium/<short>/ncs/ncs.csv` = (스크립트, 문자열 순번, 원문 CRC32, 한글). 적용 시 CRC 가 일치할 때만 치환.
- 파이프라인: `tools/ncs_extract.py <작업폴더>` → `mt_translate.py <작업폴더> all.json` → `tools/ncs_pack.py ncs_src.csv all.json --glossary glossary.json --corr corr_global.json`.
  고유 문장 4,432개(전 모듈), 번역 약 11분.
- 대상 판별: `is_sentence()` (공백 포함, `_`/`***`/`os_` 제외, 3단어 이상 또는 문장부호로 끝남). 앞뒤 공백은 보존(문자열 이어붙이기용).
- 한계: 문장이 조각으로 쪼개져 조합되는 메시지(`"You have " + IntToString(n) + " gold"`)는 조각별로 번역되어 어색할 수 있음.
  기본 캠페인(OC/SoU/HotU)과 DoD 4종 스크립트는 이 방식 대상이 아님(별도 작업).

## v0.1.14 (커뮤니티 NCS + 추가 캠페인)
- 커뮤니티 캠페인의 스크립트 문장: `tools/ncs_extract_community.py`(NWSync 캐시에서 NCS 추출) → `mt_translate.py` → `tools/ncs_pack.py ... --community` → `installer/community/<slug>/ncs.csv`.
  설치 시 `CommunityModule.patch` 가 CRC 일치 NCS 를 재빌드해 `development/<resref>.ncs` 로 둔다. 고유 문장 7,109개(20개 캠페인 전체)는 이미 번역됨.
- 번역 CSV(translations.csv)가 없는 캠페인 폴더에는 ncs.csv 를 만들지 않는다 → 캠페인 번역이 끝나 폴더가 생기면 `ncs_pack.py --community` 를 다시 실행하면 된다(번역은 재실행 불필요, 스크래치 `ncs_comm_all.json`).
- 추가: The Fall of Aielund Pt.1, Against the Cult of the Reptile God 2.0.
- 아직 번역 중: Defender of the Crown, Return of the Ironlord, Aielund Pt.2·3, Almraiven, Shadewood.

## v0.1.15
- 커뮤니티 20개 캠페인 번역·스크립트 문장 모두 포함(20/20). 설치 프로그램 항목은 Auren Saga 만 미구현(Todo).
- 새로 번역 의뢰할 커뮤니티 모듈이 생기면: `mt/community_run.py` 방식(이름→NWSync 추출→mt_translate→apply_glossary→community_pack→ncs_*).

## 번역 품질 보정 연구 (로컬 LLM 후편집) — 2026-10-16

환경: RX 6600 8GB + llama.cpp(Vulkan b11675) + Qwen2.5-7B-Instruct Q4_K_M, 설치 위치 `C:\claude program\1. 개발중\local-llm` (`start-server.bat`, OpenAI 호환 API :8080).
속도: 병렬 4에서 약 2문장/초(60토큰/초). 고유 문장 11.2만개 전체는 약 15시간 → 우선순위 처리 필요.

### 시험 (층화 400문장: UI/대사/긴 서술/고유명사 각 100, 변경된 352 중 260개를 블라인드 A/B 판정, 판정자=Claude 1인)
- 무게이트 전체 교체: LLM 승 105 / 기존 승 65 / 동률 79 / 둘 다 불량 11 → 순이득 +40 (그대로 쓰면 악화 사례가 많다)
- 하드 게이트 v2 통과 189건: **LLM 승 98 / 기존 승 17 / 동률 74**, 비동률 정밀도 85%, 순이득 +81
- 게이트 v2 = ① `<...>` 토큰·닫는 태그(`</Start>`) 완전 일치 ② 한자/가나/⁇ 없음 ③ 출력의 영어 단어 ⊆ 기존 번역의 영어 단어 ④ 원문이 식별자(`_`, CamelCase, 전부 대문자)면 LLM 제외
- 길이/편집거리 하한을 더하면 오히려 순이득이 줄어든다(좋은 수정도 많이 거름) → 쓰지 않음
- **역번역 유사도는 합격 기준으로 부적합**: 평균 유사도가 기존 0.546 / LLM 0.506으로 사람 판정(LLM 우세)과 반대. NLLB 정방향 확률은 기존 번역이 NLLB 자신의 출력이라 순환적(LLM 1/169만 우세). 참고 지표로도 쓰지 않는다.
- 남은 오류(기존 승 17): 이름 음역 환각(Black Onyx→블랙 옐리스), 고유명사 변형, 의미 오역 → 규칙으로 못 거름. 용어집 힌트 + 고유명사 목록 강화로 완화.
- 부수 발견: **현재 배포 번역 자체에** 한자/`####` 쓰레기가 400개 중 12개(3%) 있다. 팩 단계는 토큰 불일치·한글 유무만 검사하므로 이를 막지 못함 → 팩 단계에 한자/반복 `#` 검사를 추가하고 LLM 재번역 대상으로 돌릴 것.
- 한계: 판정자 1인(비완전 블라인드: 띄어쓰기 깨짐 패턴으로 기존 번역을 알아볼 수 있었음), 긴 문장은 230자까지만 비교. 사람 검수 표본이 더 필요.

### 권장 파이프라인
1. 규칙 후처리(무료): 조사 앞 공백 제거, `".` → `."`, 한자/`#` 쓰레기 검출
2. LLM 후편집(원문+기존 번역+문장 속 용어 힌트, 수정문만 출력) — 우선순위: UI·이름 → 짧은 대사 → 빈도 높은 문장 → 긴 서술
3. 게이트 v2 통과분만 `all.llm.json`에 별도 저장(원본 `all.json` 불변), 실패 문장만 재시도(온도 조정)
4. 팩 단계에서 `all.llm.json` 우선 적용, 없으면 기존

## v0.1.16 (커뮤니티 충돌 수정)
- **원인**: 커뮤니티 20개 캠페인이 같은 리소스 이름 6,209개(module.ifo 는 20개 전부, area001.are/git 17개 등)를 공유한다. `development/` 는 전역이라 여러 캠페인을 동시에 설치하면 마지막 캠페인의 파일이 나머지를 덮어 → 모듈 손상/에러/멈춤(Almraiven 손상, Shadewood·Ironlord 에러 종료, Crimson Tides 로딩 정지).
- **수정**: `CommunityModule.patch` 가 다른 커뮤니티 캠페인을 먼저 원복(한 번에 하나만), 전체 일괄 패치에서 커뮤니티 제외, GUI 시작 시 여러 개 적용돼 있으면 정리 제안, CLI `--restore-community`.
- `gff_tool` 쓰기 인코딩: 영문 텍스트의 악센트 문자(û 등)가 `?` 로 바뀌던 문제(CP949 강제) 수정 — 한글은 CP949, 그 외는 CP1252 로 보존.
- 구조 검증(다섯 캠페인 중 Crimson Tides 로 실시): GFF 번역 적용 후 구조 변화 0건, NCS 점프 대상 197/197 일치 → 파일 손상이 아니라 캠페인 간 충돌이 원인.
- Cult of the Reptile God "일부 영어": 번역 대상 12,265행 중 334행(토큰 불일치 296, 한자 포함 27 등)이 안전 검사로 제외됨. 이 문장들은 영어로 남는다 → 다음 과제: 제외 문장 재번역(LLM 후편집 파이프라인).

## v0.1.17
- 커뮤니티 설치 폴더(`문서\development`)는 `.orig` 백업을 만들지 않고, 원복 때 파일과 예전 `.orig` 를 함께 삭제한다. (캠페인을 겹쳐 패치했을 때 다른 캠페인 파일이 '백업'으로 남아 원복해도 오염이 남던 문제)
- 순정 확인 방법: 게임 폴더의 `.orig` 가 모두 사라졌는지, `nwmain.exe` 해시가 순정(3b7cb125…)인지, `bin\win32\version.dll` 이 없는지 본다. 최종 확인은 Steam '게임 파일 무결성 검사'.
