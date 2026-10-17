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
# 허용 문자: 한글, ASCII, 라틴 악센트, 일반 문장부호/기호. 그 밖(이모지·키릴·한자·깨진 글자)이 번역에만 있으면 즉시 거부
BAD = re.compile(r"[^\uAC00-\uD7A3\u3131-\u318E\t\n\x20-\x7E\u00A0-\u00FF\u2010-\u2027\u2030-\u203E\u2190-\u2199\u25A0-\u25CF\u2605\u2606\u266A\u3000-\u3003\u300C-\u300F]")


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
        if (set(BAD.findall(llm)) - set(BAD.findall(en))) :
            flags.append("badchar"); risk += 20
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
    rej = [r["en"] for r in rows if "badchar" in r["flags"]]
    json.dump(rej, open(os.path.join(out, "reject_badchar.json"), "w", encoding="utf-8"), ensure_ascii=False)
    top = sorted((r for r in rows if "badchar" not in r["flags"]), key=lambda r: -r["risk"])[:opt["--top"]]
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
    # ---- 최종 채택: 규칙에 걸리지 않은 Qwen 번역만 기존 번역(기계번역)을 덮어쓴다 ----
    META = re.compile(r"참고\s*:|다음과 같|선택하시면|바꾸면|자연스러운 한국어|자연스럽게 유지|표기하여|아래와 같|번역하면|\)\)|▷|\*{3,}|\(\s*\)|원문의|원문을|원문에|원문과|기계번역|고친 번역|고쳤습니다|수정했습니다|어조를|자연스러운 표현|문맥상|번역한 결과|번역 결과")
    BR = re.compile(r"(<Start(?:Check|Action)>)\s*([^\[\]<]{1,60}?)\s*(</Start>)")

    def accept(r):
        en, mt, q = r["en"], r["mt"], r["llm"]
        fl = r["flags"]
        if "badchar" in fl or "repeat" in fl:
            return None, "badchar/repeat"
        if META.search(q) or (" / " in q and " / " not in en and "혹은" in q):
            return None, "meta"
        if set("*()/\\|#~^@$_") & set(q) - set(en):      # 원문에 없는 기호가 번역에만 있으면 깨진 출력
            return None, "symbol"
        if len(q) > 2.5 * len(mt) + 40 and len(q) > 80 and len(q) > 2.0 * len(en):
            return None, "bloat"
        if len(en) > 40 and len(q) < 0.2 * len(en):
            return None, "truncated"
        # 괄호 복구: 원문이 <StartCheck>[Intimidate]</Start> 처럼 [..] 인데 번역이 대괄호를 빠뜨린 경우
        if en.count("[") > q.count("[") and re.search(r"<Start(?:Check|Action)>\s*\[", en):
            q2 = BR.sub(lambda m: m.group(1) + "[" + m.group(2).strip().rstrip(".") + "]" + m.group(3), q, count=1)
            if q2.count("[") == en.count("[") and q2.count("]") == en.count("]"):
                q = q2
            else:
                return None, "bracket"
        return q, ""

    final, why = {}, collections.Counter()
    for r in rows:
        q, w = accept(r)
        if q is None:
            why[w] += 1
        else:
            final[r["en"]] = q
    json.dump(final, open(os.path.join(out, "final.json"), "w", encoding="utf-8"), ensure_ascii=False)
    with open(os.path.join(out, "summary.txt"), "a", encoding="utf-8") as f:
        f.write(f"final accepted {len(final)} / {len(rows)}; rejected: {dict(why)}\n")
    print(open(os.path.join(out, "summary.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
