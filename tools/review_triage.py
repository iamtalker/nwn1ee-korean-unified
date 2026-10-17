# -*- coding: utf-8 -*-
"""2차 감수용 선별: Qwen 보정 결과(all.llm.json) 중 사람이(=Claude) 읽어 볼 만한 것만 골라 낸다. GPU/네트워크 불필요.

usage: py review_triage.py <백업폴더> [--sample 150] [--top 1000]
입력(<백업폴더>): llm/all.llm.json, mt/*_all.json, community/*/all.json, mt/corr_global.json, ncs/glossary.json
출력(<백업폴더>/llm/review/):
  features.jsonl   문장별 특징·위험 점수
  sample.txt       카테고리별 무작위 표본 (기계번역 vs Qwen 승률 재기용, 순서·좌우 무작위)
  risky.txt        위험 점수 상위 (원문 | 기계번역 | Qwen) 한 줄씩
  summary.txt      카테고리별 위험 분포
"""
import collections, difflib, glob, json, os, random, re, sys

TOK = re.compile(r"<[^<>]{1,40}>")
REPL = [("챔피언스", "챔피언"), ("화살표", "화살"), ("클래스", "직업"), ("배틀 마스터", "배틀마스터")]
HAN = re.compile(r"[가-힣]")


def clean(ko):
    ko = ko.replace(" ⁇ ", " ").replace("⁇", "")
    for a, b in REPL:
        ko = ko.replace(a, b)
    return re.sub(r"  +", " ", ko).strip()


def nums(s):
    return sorted(re.findall(r"\d+", TOK.sub(" ", s)))


def repeated(s):
    return bool(re.search(r"(.{2,8}?)\1{3,}", s)) or bool(re.search(r"(\b\S+\b)(\s+\1){2,}", s))


def main():
    argv = sys.argv[1:]
    B = argv[0]
    opt = {"--sample": 150, "--top": 1000}
    for i, a in enumerate(argv):
        if a in opt:
            opt[a] = int(argv[i + 1])
    out = os.path.join(B, "llm", "review")
    os.makedirs(out, exist_ok=True)
    good = json.load(open(os.path.join(B, "llm", "all.llm.json"), encoding="utf-8"))
    gl = json.load(open(os.path.join(B, "ncs", "glossary.json"), encoding="utf-8"))
    exact, terms = gl["exact"], gl["terms"]
    corr = json.load(open(os.path.join(B, "mt", "corr_global.json"), encoding="utf-8"))
    tl = sorted((t for t in terms if len(t) >= 5), key=len, reverse=True)
    rx = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in tl) + r")(?![A-Za-z])")
    pool = {}
    for p in glob.glob(os.path.join(B, "mt", "*_all.json")) + glob.glob(os.path.join(B, "community", "*", "all.json")):
        for en, ko in json.load(open(p, encoding="utf-8")).items():
            if en in good and en not in pool:
                pool[en] = corr.get(en) or exact.get(en.strip()) or clean(ko)

    def cat(en):
        w = len(en.split())
        hits = len(set(rx.findall(en)))
        if hits >= 2 or (hits >= 1 and w <= 14):
            return "names"
        if w <= 4:
            return "ui"
        if w <= 14:
            return "dialog"
        return "long"

    rows = []
    for en, llm in good.items():
        mt = pool.get(en)
        if mt is None:
            continue
        flags, risk = [], 0
        ratio_en = len(llm) / max(1, len(en))
        ratio_mt = len(llm) / max(1, len(mt))
        if len(en) >= 20 and (ratio_en < 0.2 or ratio_en > 1.3):
            flags.append("len_en"); risk += 2
        if len(mt) >= 20 and (ratio_mt < 0.5 or ratio_mt > 1.8):
            flags.append("len_mt"); risk += 2
        if repeated(llm):
            flags.append("repeat"); risk += 4
        if nums(en) != nums(llm):
            flags.append("number"); risk += 3
        if ("?" in en) != ("?" in llm):
            flags.append("qmark"); risk += 1
        if ("!" in en) != ("!" in llm):
            flags.append("excl"); risk += 1
        for t in set(rx.findall(en)):
            if terms[t] not in llm:
                flags.append("term:" + t[:20]); risk += 2
                break
        a, b = mt[:300], llm[:300]
        sim = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if len(a) * len(b) < 90000 else 0.5
        if sim < 0.35:
            flags.append("bigedit"); risk += 2
        elif sim < 0.55:
            risk += 1
        if len(HAN.findall(llm)) < max(1, int(len(llm) * 0.3)) and len(en) > 10:
            flags.append("fewhangul"); risk += 2
        rows.append({"en": en, "mt": mt, "llm": llm, "cat": cat(en), "risk": risk, "flags": flags, "sim": round(sim, 2)})

    with open(os.path.join(out, "features.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    def short(s, n=110):
        s = s.replace("\n", " / ")
        return s if len(s) <= n else s[:n] + "…"

    rnd = random.Random(20261017)
    by = collections.defaultdict(list)
    for i, r in enumerate(rows):
        r["id"] = i
        by[r["cat"]].append(r)
    per = max(1, opt["--sample"] // max(1, len(by)))
    with open(os.path.join(out, "sample.txt"), "w", encoding="utf-8") as f, \
            open(os.path.join(out, "sample_key.json"), "w", encoding="utf-8") as k:
        key = {}
        for c, lst in sorted(by.items()):
            for r in rnd.sample(lst, min(per, len(lst))):
                left_is_mt = rnd.random() < 0.5
                a, b = (r["mt"], r["llm"]) if left_is_mt else (r["llm"], r["mt"])
                key[r["id"]] = {"cat": c, "A": "M" if left_is_mt else "Q"}
                f.write(f"#{r['id']}\nEN: {short(r['en'])}\nA: {short(a)}\nB: {short(b)}\n")
        json.dump(key, k)
    top = sorted(rows, key=lambda r: -r["risk"])[:opt["--top"]]
    with open(os.path.join(out, "risky.txt"), "w", encoding="utf-8") as f:
        for r in top:
            f.write(f"#{r['id']} [{','.join(r['flags'])}]\nEN: {short(r['en'])}\nM: {short(r['mt'])}\nQ: {short(r['llm'])}\n")
    with open(os.path.join(out, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(f"rows {len(rows)}\n")
        for c, lst in sorted(by.items()):
            h = sum(1 for r in lst if r["risk"] >= 4)
            f.write(f"{c}: {len(lst)} rows, risk>=4: {h} ({100*h/len(lst):.1f}%), risk>=2: {sum(1 for r in lst if r['risk']>=2)}\n")
        fc = collections.Counter(fl.split(":")[0] for r in rows for fl in r["flags"])
        f.write("flags: " + ", ".join(f"{k}={v}" for k, v in fc.most_common()) + "\n")
    print(open(os.path.join(out, "summary.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
