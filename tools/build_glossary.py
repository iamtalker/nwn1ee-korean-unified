# -*- coding: utf-8 -*-
"""본편 dialog.tlk(영문/한글)의 같은 StrRef 쌍에서 용어집을 뽑는다.

usage: py build_glossary.py <영문 dialog.tlk> <한글 dialog.tlk> <출력 glossary.json>

출력: {"exact": {영문: 한글}, "terms": {영문 용어: 한글}}
  exact : 문장 전체가 용어와 같을 때 그대로 치환 (아이템/주문/기술/지명 이름)
  terms : 문장 안에서 쓰이는 용어 (2~4 단어 고유명사 등, 번역 전 보호용)
"""
import json, re, struct, sys


def read_tlk(path, enc="utf-8"):
    b = open(path, "rb").read()
    assert b[:8] == b"TLK V3.0", path
    count, off = struct.unpack_from("<II", b, 12)
    out = {}
    for i in range(count):
        flags, _snd, _v, _p, o, size, _l = struct.unpack_from("<I16sIIIIf", b, 20 + 40 * i)
        if flags & 1 and size:
            out[i] = b[off + o: off + o + size].decode(enc, "replace")
    return out


HAN = re.compile(r"[가-힣]")
NAME = re.compile(r"^[A-Z0-9][A-Za-z0-9'’\- ]{1,38}$")


def main(en_p, ko_p, out_p):
    en, ko = read_tlk(en_p, "cp1252"), read_tlk(ko_p, "cp949")
    exact, terms = {}, {}
    cnt = {}
    for i, e in en.items():
        k = ko.get(i)
        e, k = e.strip(), (k or "").strip()
        if not e or not k or e == k or not HAN.search(k):
            continue
        if "<" in e or "\n" in e or len(e.split()) > 6:
            continue
        # 이름처럼 보이는 것만 (문장부호 없는 짧은 표현)
        if not NAME.match(e) or re.search(r"[.!?,;:]", e):
            continue
        cnt.setdefault(e, {}).setdefault(k, 0)
        cnt[e][k] += 1
    for e, ks in cnt.items():
        k = max(ks, key=ks.get)           # 같은 영문의 한글이 여러 개면 다수결
        exact[e] = k
        if len(e) >= 4:
            terms[e] = k
    json.dump({"exact": exact, "terms": terms}, open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("exact", len(exact), "terms", len(terms))


if __name__ == "__main__":
    main(*sys.argv[1:4])
