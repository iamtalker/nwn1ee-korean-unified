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

## 인수인계 (v0.1.8 시점, 새 세션용)

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
