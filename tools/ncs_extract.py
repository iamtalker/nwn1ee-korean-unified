# -*- coding: utf-8 -*-
"""모듈/HAK 안의 NCS 에서 사람이 읽는 문자열을 뽑아 번역용 CSV 를 만든다.

usage: py ncs_extract.py <출력 inline 폴더> [short ...]
  환경변수 NWN_BASE (게임 폴더), NWN_HAK_DIR (선택)
출력: <폴더>/ncs_src.csv  열: Short,Resource,Index,Check,TextEng
  Check = 원문 바이트의 CRC32 (저장소에 영어를 넣지 않고 대응을 검증하기 위함)
다음 단계: mt_translate.py <폴더> <all.json> -> ncs_pack.py
"""
import csv, os, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREM = ROOT / "installer" / "modbuild" / "premium"
sys.path.insert(0, str(ROOT / "installer" / "modbuild"))
sys.path.insert(0, str(PREM))
import ncs_tool  # noqa: E402
import build_premium as bp  # noqa: E402
from analyze_premium_modules import read_erf_entries, read_resource_data  # noqa: E402


def sources(short):
    cfg = bp.load_module_config(short)
    files = []
    mp = bp.get_module_path(cfg)
    if mp and mp.exists():
        files.append(mp)
    for h in cfg.get("hak", []) or []:
        hp = bp.HAK_DIR / f"{h}.hak"
        if hp.exists():
            files.append(hp)
    return files


def main(out_dir, shorts):
    shorts = shorts or [d.name for d in sorted(PREM.iterdir()) if (d / "config.py").exists()]
    os.makedirs(out_dir, exist_ok=True)
    rows, seen = [], set()
    for short in shorts:
        try:
            files = sources(short)
        except Exception as e:  # noqa: BLE001
            print(short, "skip:", e)
            continue
        n = 0
        for f in files:
            _t, _v, entries = read_erf_entries(f)
            for resref, rtype, _id, off, size in entries:
                if rtype != 2010:
                    continue
                try:
                    data = read_resource_data(f, off, size)
                    for idx, s in ncs_tool.indexed_strings(data):
                        key = (short, resref, idx)
                        if key in seen:
                            continue
                        seen.add(key)
                        raw = s.encode("latin-1")
                        rows.append((short, resref, idx, zlib.crc32(raw), raw.decode("cp1252", "replace")))
                        n += 1
                except Exception:
                    continue
        print(f"{short}: {n} strings from {len(files)} files")
    with open(os.path.join(out_dir, "ncs_src.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["Short", "Resource", "Index", "Check", "TextEng"])
        w.writerows(rows)
    print("total", len(rows), "unique sentences", len({r[4] for r in rows}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
