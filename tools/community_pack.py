# -*- coding: utf-8 -*-
"""커뮤니티 캠페인 번역 결과(all.json) -> 배포용 translations.csv (한국어 번역만, 영어 원문 없음)

usage: py community_pack.py <community 작업 폴더> <출력: installer/community>
열: Resource,ResType,FieldPath,LangID,Text
"""
import csv, glob, io, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
TOK = re.compile(r"<[^<>]{1,40}>")
REPL = [("챔피언스", "챔피언"), ("화살표", "화살"), ("클래스", "직업"), ("아이템 비용", "아이템 가격"),
        ("물품 비용", "아이템 가격"), ("항목 비용", "아이템 가격"), ("배틀 마스터", "배틀마스터")]


def clean(ko):
    ko = ko.replace(" ⁇ ", " ").replace("⁇", "")
    for a, b in REPL:
        ko = ko.replace(a, b)
    return re.sub(r"  +", " ", ko).strip()


def main(comm, out):
    glob_c = json.load(open(os.path.join(HERE, "corr_global.json"), encoding="utf-8"))
    index = {}
    for d in sorted(os.listdir(comm)):
        base = os.path.join(comm, d)
        allp = os.path.join(base, "all.json")
        if not os.path.exists(allp):
            print(d, "skip (no translation)")
            continue
        mt = json.load(open(allp, encoding="utf-8"))
        name = open(os.path.join(base, "NAME.txt"), encoding="utf-8").read().strip()
        rows = []
        for p in sorted(glob.glob(os.path.join(base, "inline", "*.csv"))):
            for r in csv.DictReader(io.StringIO(open(p, "rb").read().decode("utf-8-sig"))):
                en = (r.get("TextEng") or "").strip()
                if not en or r["Resource"].lower().startswith("nw_"):
                    continue
                if re.fullmatch(r"[\d\s.,:+\-/%]*", en):
                    continue
                ko = glob_c.get(en) or clean(mt.get(en, ""))
                if not ko or sorted(TOK.findall(en)) != sorted(TOK.findall(ko)):
                    continue
                rows.append((r["Resource"].lower(), r["ResType"], r["FieldPath"], r["LangID"], ko))
        od = os.path.join(out, d)
        os.makedirs(od, exist_ok=True)
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["Resource", "ResType", "FieldPath", "LangID", "Text"])
        w.writerows(rows)
        open(os.path.join(od, "translations.csv"), "wb").write(buf.getvalue().encode("utf-8"))
        open(os.path.join(od, "NAME.txt"), "w", encoding="utf-8").write(name)
        index[d] = {"module_name": name, "rows": len(rows)}
        print(f"{name}: {len(rows)} rows")
    json.dump(index, open(os.path.join(out, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
