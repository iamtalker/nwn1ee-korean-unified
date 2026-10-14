# NWN:EE 통합 한글 패치 (Windows, 최신 빌드)

Neverwinter Nights: Enhanced Edition(Steam, 빌드 **8193.37**)을 한글로 즐기기 위한 통합 설치 프로그램입니다.
게임의 캠페인 선택 화면(공식 / 프리미엄 / 커뮤니티 / 로컬) 분류대로 항목이 나열되며,
항목별 **패치 / 원복**과 **전체 일괄 패치**를 지원합니다. 구현되지 않은 항목은 **미구현**으로 표시됩니다.

> 비공식 팬 프로젝트입니다. Neverwinter Nights 는 Beamdog 의 상표입니다.
> **게임 파일(`nwmain.exe`, 모듈 등)은 재배포하지 않습니다.** 설치 프로그램이 사용자의 로컬 게임 파일에 패치를 적용하거나,
> 로컬 모듈 + 번역 CSV 로 번역본을 새로 만듭니다.

## 구현 현황

| 분류 | 항목 | 상태 |
|---|---|---|
| 공통 | 엔진·UI 한글 지원 (캠페인 선택 화면 포함) | 구현 |
| 공식 · Classic | The Wailing Death(오리지널), Shadows of Undrentide, Hordes of the Underdark | 구현 (본편 번역 약 99.8%) |
| 공식 · Extra | The Winds of Eremor, Neverwinter Chess | 구현 |
| 공식 · Extra | Kingmaker, ShadowGuard, Witch's Wake, Contest of Champions, The Dark Ranger's Treasure, To Heir is Human | 미구현 |
| 프리미엄 | Doom of Icewind Dale, Tyrants of the Moonsea, Darkness over Daggerford, Pirates of the Sword Coast | 구현 (설치 시 자동 다운로드) |
| 프리미엄 | Dark Dreams of Furiae, Wyvern Crown of Cormyr, Infinite Dungeons | 미구현 |
| 커뮤니티 | A Hunt Through The Dark, Eye of the Beholder, Aielund Saga, Auren Saga, Crimson Tides of Tethyr, Siege of Shadowdale, Cult of the Reptile God | 미구현 |

※ 프리미엄 4종(DoD/ToTM/PotSC/DoIWD)의 번역은 [Steam 창작마당 nwn1ee_dod_kr](https://steamcommunity.com/sharedfiles/filedetails/?id=3437559043)
제작자의 작업물이고 유료 모듈 파일을 포함하므로, 이 저장소에는 넣지 않았습니다.
대신 설치 프로그램이 **제작자가 공개한 링크에서 자동으로 내려받아** 설치합니다(PC에 이미 있으면 그 파일을 사용). 따로 할 일은 없습니다.

## 사용 방법

1. 게임을 **한 번 실행했다가 종료**합니다 (문서 폴더에 `nwn.ini` 가 만들어져야 합니다).
2. [Releases](../../releases)에서 zip 을 받아 압축을 풀고 `run_installer.bat` 을 실행합니다. (Python 이 없으면 winget 으로 설치할지 물어봅니다)
3. 항목별 **[패치]** 또는 **[전체 일괄 패치]**.
4. Steam 에서 평소처럼 게임을 실행합니다. 별도 로더는 필요 없습니다.

원복: 설치 프로그램의 **[원복]** / **[전체 원복]** (덮어쓴 파일은 `*.orig` 로 백업됨),
또는 Steam 의 "게임 파일 무결성 검사".

## 동작 원리

- `installer/engine_patch.py` : 로컬 `nwmain.exe` 에 CP949 텍스트 디코더, 글리프 한도 확장, 텍스처 확장 등을 바이너리 패치로 적용합니다.
  지원 빌드 해시와 일치할 때만 동작하며, 다른 빌드에서는 중단합니다.
- `hook/` : `version.dll` 프록시 소스입니다. 게임이 시작할 때 스스로 로드하며(프로세스 인젝션/별도 로더 없음),
  한글 폰트 베이킹과 Nuklear UI(캠페인 선택·옵션 화면)의 한글 글리프 처리(width/query 후킹)를 담당합니다.
- `installer/modbuild/` : 로컬 `.mod` 에 번역 CSV 를 적용해 번역 모듈을 만드는 도구입니다.

## 직접 빌드

`assets/version.dll` 은 `hook/` 을 MinGW-w64 로 빌드한 것입니다.

```
gcc -shared -O2 -o assets/version.dll hook/nwn_korean_hook.c hook/version_proxy.c -lpsapi
```

`assets/dialog.tlk` 는 [wonilclone/nwn_ee_korean](https://github.com/wonilclone/nwn_ee_korean)(MIT)의
번역 CSV 를 같은 저장소의 `translate/merge_dialog_files.py` 로 빌드한 것입니다(이 저장소에는 원문 영어가 포함된 CSV 를 넣지 않았습니다).

## 알려진 제한

- **빌드 종속**: 바이너리 패치와 후킹이 `nwmain.exe` 8193.37 의 오프셋에 맞춰져 있습니다. 게임이 업데이트되면 안내 후 중단되며(한글만 깨짐),
  새 빌드용 오프셋이 필요합니다.
- Windows 전용입니다. 서명되지 않은 `version.dll` 을 게임 폴더에 두는 방식이라, 일부 백신이 의심할 수 있습니다. 소스를 공개하니 직접 빌드할 수 있습니다.
- 커뮤니티 캠페인은 게임이 내려받는 방식(NWSync/창작마당)이라 번역 대상 파일을 로컬에서 확보해야 하며, 아직 구현되지 않았습니다.
- 번역 품질은 각 원 작업물에 따릅니다. 이슈와 제보를 환영합니다.

## 개발 / 기여

개발 현황과 다음 작업은 [DEVELOPMENT.md](DEVELOPMENT.md) 를 참고하세요.

## 출처 / 라이선스

[NOTICE.md](NOTICE.md) 참고. 이 저장소의 코드는 MIT 라이선스입니다 ([LICENSE](LICENSE)).
