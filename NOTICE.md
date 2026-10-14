# 출처 및 고지

이 프로젝트는 아래 작업물을 바탕으로 합니다.

| 구성 | 출처 | 라이선스 |
|---|---|---|
| `installer/engine_patch.py`, `hook/` (훅 DLL 원형), `installer/modbuild/`, 본편 번역(`assets/dialog.tlk` 의 원천) | [wonilclone/nwn_ee_korean](https://github.com/wonilclone/nwn_ee_korean) | MIT (`pyproject.toml` 의 `license = MIT` 명시) |
| 프리미엄 4종 한글(DoD/ToTM/PotSC/DoIWD) | Steam 창작마당 [nwn1ee_dod_kr](https://steamcommunity.com/sharedfiles/filedetails/?id=3437559043) | 라이선스 미표기. **이 저장소에 포함하지 않음** |
| 모듈 `inline/*.csv` (Winds of Eremor, Neverwinter Chess 번역) | wonilclone/nwn_ee_korean | MIT (원문 영어 열은 제거) |

수정 사항:
- `engine_patch.py`: 설치 스크립트에서 패치 로직만 분리, Nuklear 글리프 범위 패치 활성화
- `hook/nwn_korean_hook.c`: 로더/프로세스 인젝션 제거(`version.dll` 프록시로 대체), Nuklear UI 텍스트를 `width`/`query` 후킹으로 처리, 기존 메모리 스캔 방식 제거
- `installer/modbuild/premium/build_premium.py`: Windows 경로 및 임시 폴더 출력 지원

게임 에셋, 게임 바이너리, 프리미엄 모듈 파일, 원문 영어 텍스트는 이 저장소와 릴리스에 포함되지 않습니다.
폰트는 설치 시 사용자 PC 의 `맑은 고딕(malgun.ttf)` 을 복사해 사용합니다.

Neverwinter Nights, Forgotten Realms 등은 각 권리자의 상표입니다. 이 프로젝트는 Beamdog / Wizards of the Coast 와 무관한 비공식 팬 프로젝트입니다.
