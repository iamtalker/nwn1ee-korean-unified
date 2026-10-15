# -*- coding: utf-8 -*-
"""용어집(build_glossary.py 결과)을 기계번역 결과(all.json)에 적용한다. 토큰 비용 없음.

usage: py apply_glossary.py <glossary.json> <all.json> [...] [--retranslate] [--dry]
  1) 정확 일치: 문장 전체가 용어와 같으면 용어집 한글로 교체
  2) --retranslate: 문장 안에 고유명사형 용어가 있는데 번역에 빠졌으면, 용어를 자리표시자로 바꿔 다시 번역한 뒤 복원
     (고유명사형 = 모든 단어가 대문자로 시작, of/the/and 등 허용, 2~5단어, 문장부호 없음)
환경변수 NWN_MT_DIR: model/ 과 pylib/ 가 있는 폴더 (기본: 이 스크립트 폴더)
원본은 <all.json>.bak 으로 한 번만 보관한다.
"""
import json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MT = os.environ.get("NWN_MT_DIR") or HERE
TOK = re.compile(r"<[^<>]{1,40}>")
SMALL = {"of", "the", "and", "in", "to", "for", "a", "on", "at", "de", "von", "van"}
STANDIN = [("Aldo", "알도"), ("Bera", "베라"), ("Cosa", "코사")]
# 흔한 일반 표현은 용어에서 제외 (대문자 시작이어도 문장 조각일 뿐인 것)
GENERIC = {"to", "you", "me", "him", "her", "them", "it", "here", "there", "now", "back", "up", "down", "out", "off", "away", "about"}
STOP = {"Thank You", "You Hear", "Good Bye", "Good Morning", "Good Evening", "Yes Sir", "No Sir"}


def proper(term):
    ws = term.split()
    if not 2 <= len(ws) <= 5 or re.search(r"[.!?,;:\"“”()0-9]", term):
        return False
    if term in STOP or len(term) < 8 or ws[-1] in SMALL or ws[-1].lower() in GENERIC:
        return False
    return all(w[0].isupper() or w in SMALL for w in ws) and ws[0][0].isupper()


def has_batchim(ch):
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0


def josa_fix(s, term_ko):
    """용어 바로 뒤 조사를 받침에 맞춘다."""
    last = term_ko[-1]
    b = has_batchim(last)
    rieul = "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 == 8
    pairs = [("은", "는"), ("이", "가"), ("을", "를"), ("과", "와")]
    i = s.find(term_ko)
    while i >= 0:
        j = i + len(term_ko)
        if j < len(s):
            for withb, nob in pairs:
                if s[j] in (withb, nob):
                    # '이'/'가' 는 뒤 글자로 단어 여부를 단순 판별 (공백/문장부호/끝일 때만)
                    nxt = s[j + 1] if j + 1 < len(s) else " "
                    if nxt in " .,!?\"'”’)…" or nxt == "\n":
                        s = s[:j] + (withb if b else nob) + s[j + 1:]
        i = s.find(term_ko, i + 1)
    return s


def load_model():
    sys.path.insert(0, os.path.join(MT, "pylib"))
    import ctranslate2, sentencepiece as spm
    model = os.path.join(MT, "model")
    sp = spm.SentencePieceProcessor(model_file=os.path.join(model, "sentencepiece.bpe.model"))
    tr = ctranslate2.Translator(model, device="cpu", compute_type="int8", inter_threads=1,
                                intra_threads=int(os.environ.get("NWN_MT_THREADS", "3")))
    return sp, tr


def translate(sp, tr, text):
    src = [["eng_Latn"] + sp.encode(text, out_type=str) + ["</s>"]]
    r = tr.translate_batch(src, target_prefix=[["kor_Hang"]], beam_size=4, max_decoding_length=300,
                           repetition_penalty=1.3, no_repeat_ngram_size=3)[0]
    t = r.hypotheses[0]
    t = t[1:] if t and t[0] == "kor_Hang" else t
    return sp.decode(t)


def main(argv):
    flags = [a for a in argv if a.startswith("--")]
    args = [a for a in argv if not a.startswith("--")]
    gloss = json.load(open(args[0], encoding="utf-8"))
    exact = gloss["exact"]
    exact_l = {k.lower(): v for k, v in exact.items()}
    terms = sorted((t for t in gloss["terms"] if proper(t)), key=len, reverse=True)
    rx = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in terms) + r")(?![A-Za-z])") if terms else None
    retr = "--retranslate" in flags
    sp = tr = None
    for path in args[1:]:
        d = json.load(open(path, encoding="utf-8"))
        n_ex = n_tr = n_fail = 0
        for en, ko in list(d.items()):
            key = en.strip()
            v = exact.get(key) or exact_l.get(key.lower())
            if v:
                if v != ko.strip():
                    d[en] = v
                    n_ex += 1
                continue
            if not (retr and rx):
                continue
            ms = rx.findall(en)
            miss = []
            for m in ms:
                if m not in miss and gloss["terms"][m] not in ko:
                    miss.append(m)
            if not miss or len(miss) > 3 or sorted(TOK.findall(en)) != sorted(TOK.findall(ko)):
                continue
            if sp is None:
                sp, tr = load_model()
            body = en
            for i, m in enumerate(miss):
                body = body.replace(m, STANDIN[i][0])
            new = translate(sp, tr, body)
            ok = True
            for i, m in enumerate(miss):
                ph, kor = STANDIN[i]
                tko = gloss["terms"][m]
                if ph in new:
                    new = new.replace(ph, tko)
                elif kor in new:
                    new = new.replace(kor, tko)
                else:
                    ok = False
                    break
                new = josa_fix(new, tko)
            if ok and new.strip() and sorted(TOK.findall(en)) == sorted(TOK.findall(new)):
                if "--dry" in flags and n_tr < 12:
                    print("  ", en[:80], "|", ko[:50], "->", new.strip()[:70])
                d[en] = new.strip()
                n_tr += 1
            else:
                n_fail += 1
        print(f"{path}: exact {n_ex}, retranslated {n_tr}, skipped {n_fail}")
        if "--dry" not in flags:
            if not os.path.exists(path + ".bak"):
                shutil.copy2(path, path + ".bak")
            json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[1:])
