# -*- coding: utf-8 -*-
"""고유명사 표기 통일 (GPU/LLM 불필요).

같은 영어 고유명사가 문장마다 다른 한국어 표기로 번역되는 문제(예: Almraiven -> 알브라이벤/알마라이벤)를 찾아,
가장 많이 쓰인 표기(대표)로 비슷한 표기(변형)를 규칙으로 바꾼다.

usage: py name_unify.py <백업폴더> [--apply]
입력(<백업폴더>): mt/*_all.json, community/*/all.json (영문->한글), llm/review/final.json(있으면 우선)
출력(<백업폴더>/llm/names/):
  names_report.txt  이름별 대표 표기·변형·건수(검토용)
  names_map.json    {영문 이름: {"canon": 대표, "variants": [변형,...]}}
  names_fixed.json  (--apply) {영문 문장: 고친 한글}  - 바뀐 문장만. 기존 번역보다 우선 적용할 것
"""
import collections, difflib, glob, json, os, re, sys

TOK = re.compile(r"<[^<>]{1,40}>")
CAP = re.compile(r"(?<![.!?\"“]\s)(?<!^)\b([A-Z][a-z]{3,}(?:'[a-z]+)?)\b")
HAN = re.compile(r"[가-힣]+")
# 조사/어미 (긴 것부터)
PART = sorted("에게서 에서는 에서도 으로는 으로도 이시여 께서는 에게는 에게도 이여 에서 으로 에게 께서 이라 이다 이며 이고 이나 인가 은 는 이 가 을 를 의 에 도 로 와 과 만 님 씨 여 야".split(), key=len, reverse=True)


def split_particle(tok):
    for p in PART:
        if tok.endswith(p) and len(tok) - len(p) >= 2:
            return tok[:-len(p)], p
    return tok, ""


def main():
    argv = sys.argv[1:]
    B = argv[0]
    apply = "--apply" in argv
    out = os.path.join(B, "llm", "names")
    os.makedirs(out, exist_ok=True)
    pool = {}
    for p in glob.glob(os.path.join(B, "mt", "*_all.json")) + glob.glob(os.path.join(B, "community", "*", "all.json")):
        for en, ko in json.load(open(p, encoding="utf-8")).items():
            pool.setdefault(en, ko)
    fp = os.path.join(B, "llm", "review", "final.json")
    final = json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) else {}
    ko_of = {en: final.get(en) or ko for en, ko in pool.items() if "#" not in ko}

    lower = collections.Counter()
    for en in ko_of:
        for w in set(re.findall(r"\b[a-z]{4,}\b", TOK.sub(" ", en))):
            lower[w] += 1
    occ = collections.defaultdict(list)             # 이름 -> [영문 문장]
    for en in ko_of:
        if 12 < len(en) < 400:
            for m in set(CAP.findall(TOK.sub(" ", en))):
                occ[m].append(en)
    core_df = collections.Counter()                  # 한글 핵심어(조사 제거) 문서 빈도
    cores_of = {}
    for en, ko in ko_of.items():
        cs = {split_particle(t)[0] for t in HAN.findall(ko) if len(t) >= 2}
        cores_of[en] = cs
        for c in cs:
            core_df[c] += 1

    gp = os.path.join(B, "ncs", "glossary.json")
    terms = json.load(open(gp, encoding="utf-8")).get("terms", {}) if os.path.exists(gp) else {}
    names_map, lines = {}, []
    for name, sents in occ.items():
        n = len(sents)
        if n < 8 or lower[name.lower()] > 0.3 * n or lower[name.lower()] >= 20:   # 일반 영단어(대문자로 시작한 문장 첫 단어 등) 제외
            continue
        cnt = collections.Counter()
        for en in sents:
            for c in cores_of[en]:
                cnt[c] += 1
        # 이름과 강하게 연결된 핵심어(정밀도>0.5)만
        cand = {c: k for c, k in cnt.items() if k >= 3 and len(c) >= 3 and k / core_df[c] > 0.5}
        if not cand:
            continue
        canon = max(cand, key=lambda c: (cand[c], len(c)))
        official = split_particle(terms[name])[0] if name in terms else None   # 본편 번역(공식)에 있으면 그것이 대표
        if official and (official in cand or core_df[official] >= 3):
            canon = official
            cand.setdefault(official, cnt.get(official, 0))
        if cand[canon] / n >= 0.75 and not official:
            continue                                  # 이미 충분히 일관됨
        variants = [c for c in cand if c != canon and cand[c] >= 3
                    and difflib.SequenceMatcher(None, c, canon).ratio() >= 0.55]
        if not variants:
            continue
        names_map[name] = {"canon": canon, "variants": variants}
        lines.append((n, f"{name} n={n} canon={canon}({cand[canon]}) -> " + ", ".join(f"{v}({cand[v]})" for v in sorted(variants, key=lambda v: -cand[v]))))
    json.dump(names_map, open(os.path.join(out, "names_map.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    lines.sort(reverse=True)
    with open(os.path.join(out, "names_report.txt"), "w", encoding="utf-8") as f:
        f.write(f"names with variants: {len(lines)}\n")
        for _, l in lines:
            f.write(l + "\n")
    print(f"names with variants: {len(lines)}")
    if not apply:
        return
    # 변형 -> 대표 (여러 이름이 같은 변형을 쓰면 충돌이므로 제외)
    vmap = collections.defaultdict(set)
    for name, d in names_map.items():
        for v in d["variants"]:
            vmap[v].add(d["canon"])
    vmap = {v: next(iter(cs)) for v, cs in vmap.items() if len(cs) == 1}
    pat = None
    if vmap:
        pat = re.compile(r"(?<![가-힣])(" + "|".join(sorted(map(re.escape, vmap), key=len, reverse=True)) + r")(?=" +
                         "|".join(["(?:" + "|".join(map(re.escape, PART)) + ")"]) + r"?(?![가-힣]))")
    fixed = {}
    for en, ko in ko_of.items():
        if not pat:
            break
        new = pat.sub(lambda m: vmap[m.group(1)], ko)
        if new != ko:
            fixed[en] = new
    json.dump(fixed, open(os.path.join(out, "names_fixed.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"sentences changed: {len(fixed)} / {len(ko_of)}")


if __name__ == "__main__":
    main()
