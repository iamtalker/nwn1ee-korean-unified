# -*- coding: utf-8 -*-
"""NWSync 캐시(커뮤니티 캠페인)에서 GFF 인라인 텍스트를 뽑아 모듈별 CSV 로 저장한다.

usage: py nwsync_extract.py <nwsync 폴더> <출력 폴더>
출력: <출력>/<slug>/inline/<ext>.csv  (열: Resource,ResType,FieldPath,LangID,StrRef,TextEng,Text)
"""
import csv, io, os, re, sqlite3, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "pylib"))
sys.path.insert(0, os.path.join(HERE, "..", "repo"))
import zstandard
from gff_tool import GffFile, CExoLocString, CEXOLOCSTRING, STRUCT, LIST

# 번역 대상 GFF 리소스 타입 (NWN restype id)
EXT = {2029: "dlg", 2027: "utc", 2025: "uti", 2044: "utp", 2042: "utd", 2051: "utm",
       2040: "ute", 2035: "uts", 2032: "utt", 2056: "jrl", 2014: "ifo", 2012: "are", 2023: "git"}


def walk(st, prefix=""):
    out = []
    for label, (ft, val) in st.fields.items():
        p = f"{prefix}/{label}" if prefix else label
        if ft == CEXOLOCSTRING and isinstance(val, CExoLocString):
            if val.substrings:
                out.append((p, val))
        elif ft == STRUCT:
            out += walk(val, p)
        elif ft == LIST and isinstance(val, list):
            for i, it in enumerate(val):
                out += walk(it, f"{p}/{i}")
    return out


def slug(name):
    s = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
    return s[:60] or "module"


def main(nws, outdir):
    meta = sqlite3.connect(os.path.join(nws, "nwsyncmeta.sqlite3"))
    data = sqlite3.connect(os.path.join(nws, "nwsyncdata_0.sqlite3"))
    dctx = zstandard.ZstdDecompressor()
    mods = meta.execute("select manifest_sha1, module_name from manifest_metadata").fetchall()
    for sha, name in mods:
        rows = collections.defaultdict(list)
        n = bad = 0
        for rsha, resref, rtype in meta.execute(
                "select resref_sha1, resref, restype from manifest_resrefs where manifest_sha1=?", (sha,)):
            ext = EXT.get(rtype)
            if not ext:
                continue
            r = data.execute("select data from resrefs where sha1=?", (rsha,)).fetchone()
            if not r:
                continue
            blob = r[0]
            try:
                i = blob.find(b"\x28\xb5\x2f\xfd")
                raw = dctx.decompress(blob[i:], max_output_size=64_000_000) if i >= 0 else blob[24:]
                gff = GffFile.from_bytes(raw)
            except Exception:
                bad += 1
                continue
            n += 1
            for path, loc in walk(gff.root):
                for lang, text in loc.substrings.items():
                    if text.strip():
                        rows[ext].append({"Resource": resref, "ResType": ext, "FieldPath": path,
                                          "LangID": lang, "StrRef": loc.strref, "TextEng": text, "Text": ""})
        d = os.path.join(outdir, slug(name), "inline")
        os.makedirs(d, exist_ok=True)
        total = uniq = chars = 0
        seen = set()
        for ext, rs in rows.items():
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=["Resource", "ResType", "FieldPath", "LangID", "StrRef", "TextEng", "Text"],
                               lineterminator="\n")
            w.writeheader(); w.writerows(rs)
            open(os.path.join(d, ext + ".csv"), "wb").write(buf.getvalue().encode("utf-8"))
            for r in rs:
                total += 1
                t = r["TextEng"].strip()
                if t not in seen:
                    seen.add(t); uniq += 1; chars += len(t)
        print(f"{name} | gff={n} bad={bad} rows={total} unique={uniq} chars={chars}", flush=True)
        open(os.path.join(outdir, slug(name), "NAME.txt"), "w", encoding="utf-8").write(name)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
