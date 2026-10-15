# -*- coding: utf-8 -*-
"""NWSync 캐시에 내려받은 커뮤니티 캠페인의 NCS 에서 번역용 문자열을 뽑는다 (tools/ncs_extract.py 의 커뮤니티판).

usage: py ncs_extract_community.py <출력 폴더> <slug=모듈이름> [slug=모듈이름 ...]
  예) AHTD_1_The_Hunt_begins_4_1="AHTD 1 - The Hunt begins 4.1"
환경변수 NWN_NWSYNC_DIR (기본: 문서\\Neverwinter Nights\\nwsync)
출력: <폴더>/ncs_src.csv  열: Short,Resource,Index,Check,TextEng
"""
import csv, os, sqlite3, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "installer" / "modbuild"))
import ncs_tool  # noqa: E402


def zstd():
    try:
        from compression import zstd as z        # Python 3.14+
        return z.decompress
    except Exception:
        import zstandard as zs
        d = zs.ZstdDecompressor()
        return lambda b: d.decompress(b, max_output_size=64_000_000)


def main(out_dir, pairs):
    nws = Path(os.environ.get("NWN_NWSYNC_DIR") or (Path.home() / "Documents" / "Neverwinter Nights" / "nwsync"))
    meta = sqlite3.connect(str(nws / "nwsyncmeta.sqlite3"))
    data = sqlite3.connect(str(nws / "nwsyncdata_0.sqlite3"))
    dec = zstd()
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for pair in pairs:
        slug, name = pair.split("=", 1)
        m = meta.execute("select manifest_sha1 from manifest_metadata where module_name=?", (name,)).fetchone()
        if not m:
            print(slug, "not downloaded")
            continue
        n = 0
        seen = set()
        for resref, sha in meta.execute(
                "select resref, resref_sha1 from manifest_resrefs where manifest_sha1=? and restype=2010", (m[0],)):
            resref = resref.lower()
            if resref in seen or resref.startswith("nw_"):
                continue
            seen.add(resref)
            b = data.execute("select data from resrefs where sha1=?", (sha,)).fetchone()
            if not b:
                continue
            blob = b[0]
            i = blob.find(b"\x28\xb5\x2f\xfd")
            try:
                d = dec(blob[i:]) if i >= 0 else blob
                for idx, s in ncs_tool.indexed_strings(d):
                    raw = s.encode("latin-1")
                    rows.append((slug, resref, idx, zlib.crc32(raw), raw.decode("cp1252", "replace")))
                    n += 1
            except Exception:
                continue
        print(f"{slug}: {n} strings")
    with open(os.path.join(out_dir, "ncs_src.csv"), "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["Short", "Resource", "Index", "Check", "TextEng"])
        w.writerows(rows)
    print("total", len(rows), "unique sentences", len({r[4] for r in rows}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
