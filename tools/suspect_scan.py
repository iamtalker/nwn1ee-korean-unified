# -*- coding: utf-8 -*-
"""3차 감수용 의심 문장 목록: 지금 배포 중인 번역(감수 통과 Qwen 번역, 없으면 기계번역) 중 규칙으로 걸러지는 것을 모은다.
번역 데이터는 바꾸지 않는다(읽기 전용). 오탐이 거의 없는 규칙만 쓴다(표본 200문장 시험: 정상 125개 중 오탐 1건 이하).

usage: py suspect_scan.py <백업폴더>
입력(<백업폴더>/llm/): review/final.json, review/features.jsonl, claude_review/corr_*.json(이미 고친 문장은 제외)
출력(<백업폴더>/llm/claude_review/): suspects.json ({영문: {ko, why}}), suspects.txt (번호|영문|번역|이유, 읽기용)

규칙:
  meta      번역 대신 설명문이 섞임("번역하였습니다", "문맥을 고려" 등)
  omit      긴 원문에서 번역이 너무 짧거나 문장 수가 2개 이상 모자람(내용 누락)
  rare      코퍼스에서 15번 미만 나온 글자가 들어 있음(깨진 글자·오타: "슧슬롯")
  shape     짧은 이름/제목(문장부호 없음)인데 번역이 "~하세요/~입니다" 같은 문장꼴
"""
import collections, glob, json, os, re, sys

HAN = re.compile(r"[가-힣]")
META = re.compile(r"번역(하였|했습|입니다|합니다|하면|한 결과)|문맥을 고려|설명드|자연스러운 한국어")
SHAPE = re.compile(r"(세요|십시오|합니다|입니다|해요|[다요])\.?$")


def sents(s):
    return len(re.findall(r"[.!?…]+(?:\s|$|\")", s + " "))


def main():
    B = sys.argv[1]
    base = os.path.join(B, "llm")
    final = json.load(open(os.path.join(base, "review", "final.json"), encoding="utf-8"))
    rows = [json.loads(l) for l in open(os.path.join(base, "review", "features.jsonl"), encoding="utf-8")]
    done = set()
    for p in glob.glob(os.path.join(base, "claude_review", "corr_*.json")):
        done |= set(json.load(open(p, encoding="utf-8")))
    syl = collections.Counter(c for v in final.values() for c in v if HAN.match(c))
    out, total = {}, collections.Counter()
    for r in rows:
        en = r["en"]
        if en in done:
            continue
        ko = final.get(en) or r["mt"]
        why = []
        if META.search(ko) and "translat" not in en.lower():
            why.append("meta")
        if len(en) >= 60 and (len(ko) < 0.20 * len(en) or (sents(en) >= 3 and sents(ko) <= sents(en) - 2)):
            why.append("omit")
        if any(syl[c] < 15 for c in ko if HAN.match(c)):
            why.append("rare")
        if len(en.split()) <= 6 and not re.search(r"[.!?\",]", en) and en[:1].isupper() and SHAPE.search(ko.strip()):
            why.append("shape")
        if why:
            out[en] = {"ko": ko, "why": why, "cat": r["cat"]}
            for w in why:
                total[w] += 1
    order = {"meta": 0, "omit": 1, "rare": 2, "shape": 3}
    items = sorted(out.items(), key=lambda kv: (min(order[w] for w in kv[1]["why"]), len(kv[0])))
    dst = os.path.join(base, "claude_review")
    os.makedirs(dst, exist_ok=True)
    json.dump(dict(items), open(os.path.join(dst, "suspects.json"), "w", encoding="utf-8"), ensure_ascii=False)
    with open(os.path.join(dst, "suspects.txt"), "w", encoding="utf-8") as f:
        for i, (en, v) in enumerate(items, 1):
            f.write(f"{i}|{en}|{v['ko']}|{','.join(v['why'])}\n")
    print(f"suspects {len(out)} / {len(rows)}  " + ", ".join(f"{k}={v}" for k, v in total.most_common()))


if __name__ == "__main__":
    main()
