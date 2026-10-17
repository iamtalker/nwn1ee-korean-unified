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
| 공식 · Extra | Kingmaker, ShadowGuard, Witch's Wake, The Winds of Eremor, Neverwinter Chess, Contest of Champions, The Dark Ranger's Treasure, To Heir is Human | 구현 (기계번역 위주) |
| 프리미엄 | Doom of Icewind Dale, Tyrants of the Moonsea, Darkness over Daggerford, Pirates of the Sword Coast | 구현 (설치 시 자동 다운로드) |
| 프리미엄 | Dark Dreams of Furiae, Wyvern Crown of Cormyr, Infinite Dungeons | 구현 (기계번역 위주) |
| 커뮤니티 | A Hunt Through The Dark (캐릭터 생성기 + 1~6장), Nature Abhors a Vacuum, Eye of the Beholder I·II, Crimson Tides of Tethyr, Siege of Shadowdale, The Fall of Aielund Pt.1~3, Cult of the Reptile God 2.0, Defender of the Crown, Return of the Ironlord, Almraiven, Shadewood | **실험적** 구현 (아래 "커뮤니티 캠페인" 참고) |

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

## 번역 범위와 번역되지 않은 부분 (정직한 표기)

| 구분 | 번역 범위 | **번역되지 않은 것** |
|---|---|---|
| 엔진·UI | 한글 표시, 캠페인 선택 화면 | 일부 옵션 화면 문구는 게임 자체 번역이 없어 영어 |
| 본편 OC/SoU/HotU | `dialog.tlk` 약 99.8% | 영문 유지 항목 약 3천 개(고유명사 등), 미번역 약 190개 |
| DoD/ToTM/PotSC/DoIWD | 외부 한패 제작자의 번역 | 제작자가 영어로 남긴 스크립트 메시지 등 |
| Eremor/Chess/CoC/Dark Ranger/To Heir is Human | 대사·이름·설명(모듈 내 텍스트) 기계번역 | 스크립트 속 문장은 대부분 번역(v0.1.13~, 일부는 조합식 문구라 영어), 2DA 항목, 이미지·영상 속 글자 |
| Kingmaker/ShadowGuard/Witch's Wake/Wyvern Crown | 모듈 + HAK 안의 대사·이름·설명 기계번역 (v0.1.8~) | 일부 스크립트 조합 문구, 2DA, **Wyvern Crown 커스텀 TLK(354개)** |
| Dark Dreams of Furiae / Infinite Dungeons | 모듈 + HAK 번역 (Infinite Dungeons 28,805개 전부 적용, Furiae 4,761개는 모두 모듈 안) | 일부 스크립트 조합 문구, 2DA |
| 커뮤니티(AHTD, Nature Abhors a Vacuum, Eye of the Beholder I·II) | 대사·이름·설명(development 폴더 방식, 실험적, 스크립트 속 문장 포함 v0.1.14~) | 접두 `nw_` 리소스, TLK/2DA, 캠페인 업데이트로 바뀐 리소스 |
| 커뮤니티: Defender of the Crown 등 나머지 | **번역 중/미포함** | 전부 |
| 커뮤니티: 위 목록 외 | **미포함** | 전부 |

공통 사항:
- 위 모듈의 번역은 **기계번역이 기본이며 이름·UI 일부만 사람이 교정**했습니다. 문장이 어색하거나 존대·반말이 섞일 수 있습니다.
- **v0.1.3~v0.1.6 으로 설치한 Kingmaker, ShadowGuard, Witch's Wake, Wyvern Crown, Infinite Dungeons, Furiae 는 번역이 일부만 적용**되어
  있습니다(HAK 안의 텍스트가 빠져 있었음). v0.1.8 에서 다시 [패치]하세요.

## HAK 번역 (v0.1.8)

Kingmaker, ShadowGuard, Witch's Wake, Infinite Dungeons, Wyvern Crown, Dark Dreams of Furiae 는 아이템·크리처·대화 대부분이
모듈 파일이 아니라 **HAK 파일**(예: `km_resources.hak`)에 들어 있습니다. v0.1.8 부터 설치 프로그램이 HAK 안의 리소스도 번역해서
번역된 HAK 를 **문서 폴더의 `hak` 폴더**에 설치합니다(게임 원본 HAK 는 건드리지 않고, 문서 폴더의 HAK 가 우선합니다).
[원복]하면 번역된 HAK 도 함께 제거됩니다. 이전 버전(v0.1.3~v0.1.6)에서 설치한 모듈은 번역이 일부만 적용되어 있으니 다시 [패치]하세요.

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

## 커뮤니티 캠페인 (실험적)

게임이 NWSync 로 내려받은 캐시(문서 폴더의 `nwsync`)의 텍스트를 번역해 문서 폴더의 `development` 폴더에 설치합니다.
(`override` 는 모듈·NWSync 보다 우선순위가 낮아 번역이 적용되지 않았습니다. **v0.1.10 이하에서 커뮤니티 캠페인을 패치했다면 v0.1.11 에서 다시 [패치]하세요.**)

- **게임의 커뮤니티 탭에서 해당 캠페인을 먼저 내려받아야** 합니다.
- **커뮤니티 캠페인은 캠페인별 폴더에 번역본을 보관하고, 플레이할 캠페인으로 전환합니다 (v0.1.24~).** 20개 캠페인이 `module.ifo`, `area001` 같은 같은 이름의 파일을 공유하고(6천여 개) 게임은 `문서\development` 폴더 하나만 읽기 때문에, 한꺼번에 켜 두면 서로 덮어써서 모듈 손상·에러·멈춤이 납니다. 그래서 번역본은 `문서\ko_campaigns\<캠페인>\` 에 캠페인마다 따로 만들어 두고(캠페인당 약 13MB), 각 캠페인의 [패치]는 이미 만든 번역본을 `development` 에 복사해 그 캠페인으로 전환합니다(다른 캠페인은 자동 해제, 전환은 몇 초). [전체 일괄 패치]는 게임에서 내려받은 캠페인의 번역본을 전부 미리 만들어 두기만 하고(상태 '준비됨'), [전체 원복]은 해제와 함께 번역본 폴더도 지웁니다. 같은 시각에 활성화되는 캠페인은 하나뿐입니다.
- 게임의 "Find more content!"로 새 캠페인을 내려받으면, 설치 프로그램 목록 맨 아래 **"번역 없음"** 묶음에 이름이 표시됩니다(번역은 개발자가 따로 만들어야 합니다). 커뮤니티 목록은 알파벳순입니다.
- 게임 내 동작은 아직 충분히 검증되지 않았습니다. 문제가 있으면 [원복] 후 알려 주세요.

## 로드맵

- **커뮤니티 캠페인 자동 전환 (진행 예정, 1순위)**: 지금은 게임이 `development` 폴더 하나만 읽기 때문에, 커뮤니티 캠페인을 바꿔 플레이할 때마다 설치 프로그램에서 그 캠페인의 [패치]를 눌러 전환해야 합니다(번역본은 캠페인별 폴더에 만들어 두므로 전환 자체는 몇 초). 번역본을 모두가 보는 폴더에 두기 때문에 같은 이름의 다른 캠페인 파일을 가로채는 것이 원인입니다.
  1. **엔진 후킹(먼저 시도)**: 게임이 모듈을 열 때 모듈 이름을 잡아 해당 캠페인의 폴더를 읽게 하면 20개를 전부 설치해 두고도 아무것도 누르지 않아도 됩니다. 모듈 이름을 얻을 지점이 있는지부터 조사합니다.
  2. **번역을 캠페인 파일에 직접 넣기(후킹이 안 될 때)**: 영어 원본처럼 캠페인 안에서만 읽으므로 충돌이 없습니다. 다만 NWSync 캐시를 고치면 게임이 어떻게 반응하는지 아직 확인하지 않았고(되돌리거나 손상으로 볼 수 있음), 별도 모듈 파일로 만들면 캠페인 20개를 각각 확인해야 합니다.
- 번역 품질 보정(로컬 Qwen 후편집) 결과를 번역에 반영.
- 본편·Darkness over Daggerford 등 스크립트 문장 번역(.nwm 재패킹).
- **더 나은 기계번역 모델 비교 (맨 뒤 순서)**: 지금의 기계번역(NLLB-200 600M)은 "무료·오프라인" 조건에서 고른 것이라 최선인지 검증된 적이 없습니다. 같은 표본 100문장으로 더 큰 NLLB와 다른 후보를 비교하고, 더 나으면 **감수를 통과하지 못했거나 처리되지 않은 문장에만** 적용합니다(기반 번역을 통째로 바꾸면 감수·반영 단계를 다시 해야 해서). 선택 이유와 측정 결과는 방법서 변경 이력에 남깁니다.

## 알려진 제한

- **빌드 종속**: 바이너리 패치와 후킹이 `nwmain.exe` 8193.37 의 오프셋에 맞춰져 있습니다. 게임이 업데이트되면 안내 후 중단되며(한글만 깨짐),
  새 빌드용 오프셋이 필요합니다.
- Windows 전용입니다. 서명되지 않은 `version.dll` 을 게임 폴더에 두는 방식이라, 일부 백신이 의심할 수 있습니다. 소스를 공개하니 직접 빌드할 수 있습니다.
- 커뮤니티 캠페인은 게임이 내려받는 방식(NWSync/창작마당)이라 번역 대상 파일을 로컬에서 확보해야 하며, 아직 구현되지 않았습니다.
- 번역 품질은 각 원 작업물에 따릅니다. 이슈와 제보를 환영합니다.

## 개발 / 기여

- 번역 방법(기계번역 → 용어집 → 자동 검사 → LLM 감수)을 다른 게임·다른 AI 에 적용할 수 있게 정리한 방법서는 별도 저장소로 옮겼습니다: [iamtalker/game-translation-pipeline](https://github.com/iamtalker/game-translation-pipeline). 방법서가 말하는 참고 구현 스크립트는 이 저장소의 `tools/` (`mt_translate.py`, `llm_postedit.py`, `review_triage.py`, `build_glossary.py`, `apply_glossary.py`)에 있습니다.

개발 현황과 다음 작업은 [DEVELOPMENT.md](DEVELOPMENT.md) 를 참고하세요.

## 출처 / 라이선스

[NOTICE.md](NOTICE.md) 참고. 이 저장소의 코드는 MIT 라이선스입니다 ([LICENSE](LICENSE)).
