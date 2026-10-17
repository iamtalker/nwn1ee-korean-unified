# -*- coding: utf-8 -*-
"""이미 번역이 끝난 확장 모듈(DoD 계열)의 TLK 에서 영어-한국어 쌍을 뽑아, 현재 번역 대상 중 문장이 정확히 같은 것만 정확 일치 번역으로 만든다.

usage: py build_tm_exact.py <백업폴더> <영문 tlk 폴더> <한글 tlk 폴더> [이름 ...]
  영문 tlk 폴더: 게임의 data/tlk,  한글 tlk 폴더: 한글패치가 설치된 문서\\override
  이름 기본값: ossian tyrants   (파일 <이름>.tlk)
출력: <백업폴더>/llm/review/tm_exact.json  {번역 대상 영문 문장: 한국어}
 - 같은 영어가 파일마다 다른 한국어로 번역돼 있으면(모호) 제외
 - 영어와 한국어가 같은 항목(번역 안 된 것)은 제외
apply_review.py 가 이 파일을 다른 모든 감수 결과보다 우선해서 적용한다.
"""
import collections, glob, json, os, re, struct, sys


def read_tlk(path, enc):
    b = open(path, "rb").read()
    assert b[:8] == b"TLK V3.0", path
    count, off = struct.unpack_from("<II", b, 12)
    out = {}
    for i in range(count):
        flags, _snd, _v, _p, o, size, _l = struct.unpack_from("<I16sIIIIf", b, 20 + 40 * i)
        if flags & 1 and size:
            out[i] = b[off + o: off + o + size].decode(enc, "replace")
    return out


def main():
    B, EN, KO = sys.argv[1:4]
    names = sys.argv[4:] or ["ossian", "tyrants"]
    pool = {}
    for p in glob.glob(os.path.join(B, "mt", "*_all.json")) + glob.glob(os.path.join(B, "community", "*", "all.json")):
        for en in json.load(open(p, encoding="utf-8")):
            pool.setdefault(en.strip().lower(), en)
    cand = collections.defaultdict(set)
    for n in names:
        en = read_tlk(os.path.join(EN, n + ".tlk"), "cp1252")
        ko = read_tlk(os.path.join(KO, n + ".tlk"), "cp949")
        for i in ko:
            if i in en and re.search(r"[가-힣]", ko[i]) and en[i].strip() != ko[i].strip():
                cand[en[i].strip().lower()].add(ko[i].strip())
    out, amb = {}, 0
    for key, kos in cand.items():
        if key not in pool:
            continue
        if len(kos) != 1:
            amb += 1
            continue
        out[pool[key]] = next(iter(kos))
    d = os.path.join(B, "llm", "review")
    os.makedirs(d, exist_ok=True)
    json.dump(out, open(os.path.join(d, "tm_exact.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"exact-match TM entries {len(out)} (ambiguous skipped {amb})")


if __name__ == "__main__":
    main()
