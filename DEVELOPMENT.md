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
| 나머지 공식 Extra 3종(Kingmaker/ShadowGuard/Witch's Wake), 프리미엄 3종, 커뮤니티 7종 | **미구현** (설치 창에 "미구현" 표시) |

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
| Dark Dreams of Furiae | 약 4,760 |
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
