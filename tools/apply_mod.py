# -*- coding: utf-8 -*-
"""usage: py apply_mod.py <short> [corrections.json]  -> pub/installer/modbuild/premium/<short>"""
import csv, glob, io, json, os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
short = sys.argv[1]
SRC = os.path.join(HERE, "..", "repo", "premium", short)
DST = os.path.join(HERE, "..", "pub", "installer", "modbuild", "premium", short)
mt = json.load(open(os.path.join(HERE, f"{short}_all.json"), encoding="utf-8"))
corr = {}
if len(sys.argv) > 2 and os.path.exists(sys.argv[2]):
    corr = json.load(open(sys.argv[2], encoding="utf-8"))
REPL = [("챔피언스", "챔피언"), ("화살표", "화살"), ("클래스", "직업"), ("아이템 비용", "아이템 가격"),
        ("물품 비용", "아이템 가격"), ("항목 비용", "아이템 가격"), ("배틀 마스터", "배틀마스터")]
def clean(ko):
    ko = ko.replace(" ⁇ ", " ").replace("⁇", "")
    for a, b in REPL:
        ko = ko.replace(a, b)
    return re.sub(r"  +", " ", ko).strip()
TOK = re.compile(r"<[^<>]{1,40}>")
final, flagged = {}, []
for en, ko in mt.items():
    out = corr.get(en) or clean(ko)
    if re.fullmatch(r"[\d\s.,:+\-/%]*", en.strip()):
        out = en
    if sorted(TOK.findall(en)) != sorted(TOK.findall(out)):
        flagged.append((en, out))
    final[en] = out
os.makedirs(os.path.join(DST, "inline"), exist_ok=True)
shutil.copy(os.path.join(SRC, "config.py"), os.path.join(DST, "config.py"))
n = 0
for p in sorted(glob.glob(os.path.join(SRC, "inline", "*.csv"))):
    rows = list(csv.DictReader(io.StringIO(open(p, "rb").read().decode("utf-8-sig"))))
    if not rows:
        continue
    cols = [c for c in rows[0].keys() if c != "TextEng"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        en = (r.get("TextEng") or "").strip()
        r["Text"] = final.get(en, r.get("Text", "")) if en else r.get("Text", "")
        w.writerow(r); n += 1
    open(os.path.join(DST, "inline", os.path.basename(p)), "wb").write(buf.getvalue().encode("utf-8"))
print(short, "rows", n, "corrections", len(corr), "token-mismatch", len(flagged))
for en, out in flagged[:15]:
    print("  MISMATCH:", en[:70].replace("\n", " "), "=>", out[:70].replace("\n", " "))
