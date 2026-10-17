# -*- coding: utf-8 -*-
"""감수 결과(Qwen 채택분 final.json + 고유명사 통일 names_fixed.json)를 배포용 번역 CSV 에 반영한다.

배포용 CSV 에는 영어가 없으므로 '예전 한국어 -> 새 한국어' 로 바꾼다:
  예전 한국어 = 기계번역(all.json)에 용어 정리(clean)·전역 교정을 적용한 값  (번역을 만든 방식과 같게 재현)
  같은 예전 한국어가 서로 다른 영어 둘 이상에서 나오면(모호) 건드리지 않는다.
  토큰(<...>) 이 예전/새 번역에서 다르면 건드리지 않는다.

usage: py apply_review.py <백업폴더> [--write] [--no-names]      (기본은 모의 실행: 파일별 건수만 출력)
대상: installer/modbuild/premium/*/inline/*.csv (열 Text), installer/community/*/translations.csv (열 Text)
"""
import collections, csv, glob, io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOK = re.compile(r"<[^<>]{1,40}>")
REPL = [("챔피언스", "챔피언"), ("화살표", "화살"), ("클래스", "직업"), ("아이템 비용", "아이템 가격"),
        ("물품 비용", "아이템 가격"), ("항목 비용", "아이템 가격"), ("배틀 마스터", "배틀마스터")]


def clean(ko):
    ko = ko.replace(" ⁇ ", " ").replace("⁇", "")
    for a, b in REPL:
        ko = ko.replace(a, b)
    return re.sub(r"  +", " ", ko).strip()


def main():
    argv = sys.argv[1:]
    B = argv[0]
    write = "--write" in argv
    jl = lambda *p: json.load(open(os.path.join(B, *p), encoding="utf-8"))
    corr = jl("mt", "corr_global.json")
    gl = jl("ncs", "glossary.json")
    exact = gl["exact"]
    pool = {}
    for p in sorted(glob.glob(os.path.join(B, "mt", "*_all.json")) + glob.glob(os.path.join(B, "community", "*", "all.json"))):
        for en, ko in json.load(open(p, encoding="utf-8")).items():
            pool.setdefault(en, ko)
    new = {}
    layers = [("llm", "review", "final.json")]
    if "--no-names" not in argv:                     # 고유명사 통일은 별도 단계(기본 포함, --no-names 로 제외)
        layers.append(("llm", "names", "names_fixed.json"))
    layers.append(("llm", "review", "tm_exact.json"))       # 이미 번역된 확장 모듈의 정확 일치 번역: 가장 우선
    for fn in layers:
        p = os.path.join(B, *fn)
        if os.path.exists(p):
            new.update(jl(*fn))                       # 뒤의 것(고유명사 통일)이 앞의 것을 포함·우선
    # 예전 한국어 -> 영어 (여러 후보 허용해서 모호하면 제외)
    rev = collections.defaultdict(set)
    for en, ko in pool.items():
        if en not in new:
            continue
        for old in {clean(corr.get(en) or exact.get(en.strip()) or ko), clean(ko)}:
            if old:
                rev[old].add(en)
    mapping = {}
    for old, ens in rev.items():
        if len(ens) != 1:
            continue
        en = next(iter(ens))
        nw = new[en]
        if nw == old or sorted(TOK.findall(old)) != sorted(TOK.findall(nw)):
            continue
        mapping[old] = nw
    print(f"override candidates {len(new)}, usable old->new {len(mapping)}")
    files = sorted(glob.glob(os.path.join(ROOT, "installer", "modbuild", "premium", "*", "inline", "*.csv")) +
                   glob.glob(os.path.join(ROOT, "installer", "community", "*", "translations.csv")))
    tot_rows = tot_chg = 0
    for f in files:
        raw = open(f, "rb").read()
        text = raw.decode("utf-8-sig")
        bom = raw.startswith(b"\xef\xbb\xbf")
        rows = list(csv.reader(io.StringIO(text)))
        if not rows or "Text" not in rows[0]:
            continue
        ti = rows[0].index("Text")
        chg = 0
        for r in rows[1:]:
            if len(r) > ti and r[ti] in mapping:
                r[ti] = mapping[r[ti]]
                chg += 1
        tot_rows += len(rows) - 1
        tot_chg += chg
        rel = os.path.relpath(f, ROOT)
        print(f"{rel}: rows {len(rows) - 1}, changed {chg}")
        if write and chg:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\n").writerows(rows)
            data = buf.getvalue().encode("utf-8")
            open(f, "wb").write((b"\xef\xbb\xbf" if bom else b"") + data)
    print(f"TOTAL rows {tot_rows}, changed {tot_chg} ({100 * tot_chg / max(1, tot_rows):.1f}%)" + ("  [written]" if write else "  [dry run]"))


if __name__ == "__main__":
    main()
