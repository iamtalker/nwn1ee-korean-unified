# -*- coding: utf-8 -*-
"""ncs_extract.py 결과 + 기계번역(all.json) -> premium/<short>/ncs/ncs.csv (한국어만, 영어 원문 없음)

usage: py ncs_pack.py <ncs_src.csv> <all.json> [--glossary glossary.json] [--corr corr.json ...]
열: Resource,Index,Check,Text
적용 순서: 교정(corr) > 용어집 정확 일치 > 기계번역(청소 후)
버리는 경우: 번역 없음 / 한글 없음 / 토큰(<..>)·서식(%s 등) 불일치 / CP949 로 인코딩 불가
"""
import csv, io, json, os, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PREM = ROOT / "installer" / "modbuild" / "premium"
TOK = re.compile(r"<[^<>]{1,40}>|%[sdif]|\{[^{}]{0,20}\}")
REPL = [("챔피언스", "챔피언"), ("화살표", "화살"), ("클래스", "직업"), ("아이템 비용", "아이템 가격"),
        ("물품 비용", "아이템 가격"), ("항목 비용", "아이템 가격"), ("배틀 마스터", "배틀마스터")]
HAN = re.compile(r"[가-힣]")


def clean(ko):
    ko = ko.replace(" ⁇ ", " ").replace("⁇", "")
    for a, b in REPL:
        ko = ko.replace(a, b)
    return re.sub(r"  +", " ", ko).strip()


def cp949_ok(s):
    try:
        s.encode("cp949")
        return True
    except UnicodeEncodeError:
        return False


def main(argv):
    src, allj = argv[0], argv[1]
    gloss = {}
    corr = {}
    i = 2
    while i < len(argv):
        if argv[i] == "--glossary":
            gloss = json.load(open(argv[i + 1], encoding="utf-8"))["exact"]
            i += 2
        elif argv[i] == "--corr":
            corr.update(json.load(open(argv[i + 1], encoding="utf-8")))
            i += 2
        else:
            i += 1
    mt = json.load(open(allj, encoding="utf-8"))
    out = {}
    stat = {}
    with open(src, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            en = r["TextEng"]
            core = en.strip()
            lead, trail = en[:len(en) - len(en.lstrip())], en[len(en.rstrip()):]
            ko = corr.get(core) or gloss.get(core) or clean(mt.get(en.strip(), "") or mt.get(en, ""))
            ok = bool(ko) and HAN.search(ko) and cp949_ok(ko) and \
                sorted(TOK.findall(core)) == sorted(TOK.findall(ko))
            st = stat.setdefault(r["Short"], [0, 0])
            st[1] += 1
            if not ok:
                continue
            st[0] += 1
            out.setdefault(r["Short"], []).append((r["Resource"].lower(), r["Index"], r["Check"], lead + ko + trail))
    for short, rows in out.items():
        d = PREM / short / "ncs"
        d.mkdir(parents=True, exist_ok=True)
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["Resource", "Index", "Check", "Text"])
        w.writerows(rows)
        (d / "ncs.csv").write_bytes(buf.getvalue().encode("utf-8"))
    for short, (a, b) in sorted(stat.items()):
        print(f"{short}: {a}/{b} strings packed")


if __name__ == "__main__":
    main(sys.argv[1:])
