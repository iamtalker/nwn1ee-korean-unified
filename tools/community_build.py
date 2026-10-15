# -*- coding: utf-8 -*-
"""커뮤니티(NWSync) 캠페인 번역본을 override 용 GFF 파일로 만든다.

usage: py community_build.py <nwsync 폴더> <community 작업 폴더> <출력 폴더>
 - community/<slug>/all.json : 영어 -> 한국어 (mt_translate 결과)
 - 출력: <출력>/<slug>/<resref>.<ext>  +  <출력>/<slug>/FILES.json (설치/원복 목록)
충돌 방지:
 - 같은 (resref, 타입)이 다른 모듈에서 내용(sha1)이 다르게 쓰이면 둘 다 제외
 - 기본 게임 접두(nw_)로 시작하는 리소스는 제외
 - ifo(모듈 정보)는 제외
"""
import collections, json, os, re, sqlite3, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "pylib"))
sys.path.insert(0, os.path.join(HERE, "..", "repo"))
import zstandard
from gff_tool import GffFile, CExoLocString, CEXOLOCSTRING, STRUCT, LIST

EXT = {2029: "dlg", 2027: "utc", 2025: "uti", 2044: "utp", 2042: "utd", 2051: "utm",
       2040: "ute", 2035: "uts", 2032: "utt", 2056: "jrl", 2012: "are"}
TOK = re.compile(r"<[^<>]{1,40}>")
REPL = [("챔피언스", "챔피언"), ("화살표", "화살"), ("클래스", "직업"), ("아이템 비용", "아이템 가격"),
        ("물품 비용", "아이템 가격"), ("항목 비용", "아이템 가격"), ("배틀 마스터", "배틀마스터")]


def clean(ko):
    ko = ko.replace(" ⁇ ", " ").replace("⁇", "")
    for a, b in REPL:
        ko = ko.replace(a, b)
    return re.sub(r"  +", " ", ko).strip()


def slug(name):
    return (re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_"))[:60] or "module"


def locstrings(st):
    out = []
    for label, (ft, val) in st.fields.items():
        if ft == CEXOLOCSTRING and isinstance(val, CExoLocString):
            if val.substrings:
                out.append(val)
        elif ft == STRUCT:
            out += locstrings(val)
        elif ft == LIST and isinstance(val, list):
            for it in val:
                out += locstrings(it)
    return out


def main(nws, comm, outdir):
    glob = json.load(open(os.path.join(HERE, "corr_global.json"), encoding="utf-8"))
    meta = sqlite3.connect(os.path.join(nws, "nwsyncmeta.sqlite3"))
    data = sqlite3.connect(os.path.join(nws, "nwsyncdata_0.sqlite3"))
    dctx = zstandard.ZstdDecompressor()

    # 1) 충돌 목록: (resref,type) -> 서로 다른 sha1 개수
    seen = collections.defaultdict(set)
    for _m, rsha, resref, rtype in meta.execute(
            "select manifest_sha1, resref_sha1, resref, restype from manifest_resrefs"):
        if rtype in EXT:
            seen[(resref.lower(), rtype)].add(rsha)
    conflict = {k for k, v in seen.items() if len(v) > 1}
    print("conflicting resources:", len(conflict), flush=True)

    for sha, name in meta.execute("select manifest_sha1, module_name from manifest_metadata").fetchall():
        sl = slug(name)
        allp = os.path.join(comm, sl, "all.json")
        if not os.path.exists(allp):
            print(name, "-> skip (no translation yet)")
            continue
        mt = json.load(open(allp, encoding="utf-8"))

        def tr(en):
            t = en.strip()
            if not t or re.fullmatch(r"[\d\s.,:+\-/%]*", t):
                return None
            ko = glob.get(t) or clean(mt.get(t, ""))
            if not ko:
                return None
            if sorted(TOK.findall(t)) != sorted(TOK.findall(ko)):
                return None
            return ko

        od = os.path.join(outdir, sl)
        os.makedirs(od, exist_ok=True)
        files, skipped_conf, skipped_nw, nres, nstr = [], 0, 0, 0, 0
        for rsha, resref, rtype in meta.execute(
                "select resref_sha1, resref, restype from manifest_resrefs where manifest_sha1=?", (sha,)):
            ext = EXT.get(rtype)
            if not ext:
                continue
            if (resref.lower(), rtype) in conflict:
                skipped_conf += 1
                continue
            if resref.lower().startswith("nw_"):
                skipped_nw += 1
                continue
            r = data.execute("select data from resrefs where sha1=?", (rsha,)).fetchone()
            if not r:
                continue
            blob = r[0]
            i = blob.find(b"\x28\xb5\x2f\xfd")
            try:
                raw = dctx.decompress(blob[i:], max_output_size=64_000_000)
                gff = GffFile.from_bytes(raw)
            except Exception:
                continue
            changed = 0
            for loc in locstrings(gff.root):
                for lang, text in list(loc.substrings.items()):
                    ko = tr(text)
                    if ko:
                        loc.set_text(ko, lang)
                        changed += 1
            if changed:
                fn = f"{resref.lower()}.{ext}"
                open(os.path.join(od, fn), "wb").write(gff.to_bytes())
                files.append(fn)
                nres += 1
                nstr += changed
        json.dump({"module": name, "files": files}, open(os.path.join(od, "FILES.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        print(f"{name}: files={nres} strings={nstr} skipped(conflict)={skipped_conf} skipped(nw_)={skipped_nw}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
