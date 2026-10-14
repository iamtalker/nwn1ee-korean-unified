# -*- coding: utf-8 -*-
"""깨진(자리표시자 붕괴/반복) 기계번역 항목 재번역: <StartCheck>[X]</Start> 접두를 분리해 본문만 번역"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "pylib"))
import ctranslate2, sentencepiece as spm
TAGS = {"Singing":"노래","Success":"성공","Failure":"실패","Lie":"거짓말","Insight":"통찰","Persuade":"설득",
        "Intimidate":"협박","Bluff":"허세","Diplomacy":"외교","Lore":"지식","Spot":"관찰","Search":"수색"}
TOK = re.compile(r"<[^<>]{1,40}>")
PRE = re.compile(r"^<StartCheck>\[([^\]]+)\]</Start>\s*", re.S)
def bad(en, ko):
    if sorted(TOK.findall(en)) != sorted(TOK.findall(ko)): return True
    if "###" in ko: return True
    w = ko.split()
    return len(w) > 8 and len(set(w)) <= 2
def main(short):
    p = os.path.join(HERE, f"{short}_all.json")
    d = json.load(open(p, encoding="utf-8"))
    todo = [k for k, v in d.items() if bad(k, v)]
    print(short, "bad:", len(todo))
    if not todo: return
    model = os.path.join(HERE, "model")
    sp = spm.SentencePieceProcessor(model_file=os.path.join(model, "sentencepiece.bpe.model"))
    tr = ctranslate2.Translator(model, device="cpu", compute_type="int8", inter_threads=1, intra_threads=6)
    for en in todo:
        m = PRE.match(en)
        prefix = f"<StartCheck>[{TAGS.get(m.group(1), m.group(1))}]</Start> " if m else ""
        rest = en[m.end():] if m else en
        names = TOK.findall(rest)
        body = rest
        for i, t in enumerate(names):          # 이름 토큰 -> 고유명사 자리표시자
            body = body.replace(t, ["Aldo", "Bera", "Cosa"][i % 3], 1)
        src = [["eng_Latn"] + sp.encode(body, out_type=str) + ["</s>"]]
        r = tr.translate_batch(src, target_prefix=[["kor_Hang"]], beam_size=4, max_decoding_length=300,
                               repetition_penalty=1.3, no_repeat_ngram_size=3)[0]
        toks = r.hypotheses[0]
        toks = toks[1:] if toks and toks[0] == "kor_Hang" else toks
        ko = sp.decode(toks)
        ok = True
        for i, t in enumerate(names):
            ph = ["Aldo", "Bera", "Cosa"][i % 3]
            kor = {"Aldo": "알도", "Bera": "베라", "Cosa": "코사"}[ph]
            if ph in ko: ko = ko.replace(ph, t, 1)
            elif kor in ko: ko = ko.replace(kor, t, 1)
            else: ok = False
        d[en] = prefix + (ko if ok and ko.strip() else rest)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False)
for s in sys.argv[1:]:
    main(s)
