# -*- coding: utf-8 -*-
"""NLLB(CTranslate2) 로 NWN 인라인 텍스트 CSV 를 1차 기계번역한다.

usage: py mt_translate.py <module_inline_dir> <out_json> [limit]
- 게임 토큰(<FirstName> 등)은 번역 전에 자리표시자로 바꿔 보호한다.
- 같은 영어 문장은 한 번만 번역한다.
"""
import csv
import glob
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "pylib"))
import ctranslate2  # noqa: E402
import sentencepiece as spm  # noqa: E402

TOKEN_RE = re.compile(r"<[^<>]{1,40}>")
PH = "#%d#"


def protect(text):
    toks = []

    def sub(m):
        toks.append(m.group(0))
        return PH % (len(toks) - 1)
    return TOKEN_RE.sub(sub, text), toks


def restore(text, toks):
    for i, t in enumerate(toks):
        text = text.replace(PH % i, t)
    return text


def load_rows(d):
    rows = []
    for p in sorted(glob.glob(os.path.join(d, "*.csv"))):
        raw = open(p, "rb").read().decode("utf-8-sig")
        for r in csv.DictReader(io.StringIO(raw)):
            r["_file"] = os.path.basename(p)
            rows.append(r)
    return rows


def main():
    inline_dir, out_json = sys.argv[1], sys.argv[2]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    rows = load_rows(inline_dir)
    uniq = []
    seen = set()
    for r in rows:
        t = (r.get("TextEng") or "").strip()
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    print(f"rows={len(rows)} unique={len(uniq)} chars={sum(len(u) for u in uniq)}")
    if limit:
        uniq = uniq[:limit]

    model = os.path.join(HERE, "model")
    sp = spm.SentencePieceProcessor(model_file=os.path.join(model, "sentencepiece.bpe.model"))
    tr = ctranslate2.Translator(model, device="cpu", compute_type="int8",
                                inter_threads=2, intra_threads=6)

    prot = [protect(u) for u in uniq]
    src = [["eng_Latn"] + sp.encode(p[0], out_type=str) + ["</s>"] for p in prot]
    t0 = time.time()
    out = {}
    B = 32
    for i in range(0, len(src), B):
        res = tr.translate_batch(src[i:i + B], target_prefix=[["kor_Hang"]] * len(src[i:i + B]),
                                 beam_size=2, max_decoding_length=256)
        for j, r in enumerate(res):
            toks = r.hypotheses[0]
            if toks and toks[0] == "kor_Hang":
                toks = toks[1:]
            ko = sp.decode(toks)
            idx = i + j
            out[uniq[idx]] = restore(ko, prot[idx][1])
        if (i // B) % 5 == 0:
            el = time.time() - t0
            print(f"  {i + len(res)}/{len(src)}  {el:.0f}s", flush=True)
    print(f"done {len(out)} in {time.time() - t0:.0f}s")
    json.dump(out, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main()
