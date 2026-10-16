# -*- coding: utf-8 -*-
"""로컬 LLM(llama.cpp 서버) 후편집: 기계번역을 다듬고 게이트 v2 를 통과한 것만 all.llm.json 에 저장한다.

usage: py llm_postedit.py <백업폴더> [--cats ui,names,dialog,long] [--limit N] [--par 4] [--url http://127.0.0.1:8080]
  <백업폴더>: mt/*_all.json, community/*/all.json, ncs/glossary.json, mt/corr_global.json 이 있는 폴더 (원본은 수정하지 않음)
출력(<백업폴더>/llm/):
  all.llm.json      게이트 v2 통과분만 {영문: 한글}
  llm_status.jsonl  처리한 모든 문장 {en, status, why} (이어하기용, 실패 포함)

게이트 v2: ① <...> 토큰·닫는 태그 일치 ② 한자/가나/⁇ 없음 ③ 출력 영어 단어 ⊆ 기존 번역 영어 단어
          ④ 식별자형 원문(_, CamelCase, 전부 대문자)과 한 단어 원문은 LLM 제외 ⑤ 기존 번역과 같으면 'same'
"""
import collections, concurrent.futures as cf, glob, json, os, re, sys, time, urllib.request

TOK = re.compile(r"<[^<>]{1,40}>")
CJK = re.compile(r"[぀-ヿ㐀-鿿豈-﫿]")
REPL = [("챔피언스", "챔피언"), ("화살표", "화살"), ("클래스", "직업"), ("배틀 마스터", "배틀마스터")]
SYSTEM = ("당신은 판타지 롤플레잉 게임 Neverwinter Nights 의 한국어 번역 감수자입니다. "
          "영어 원문과 기계번역이 주어지면, 원문의 뜻을 정확히 살리면서 자연스러운 한국어로 고쳐 쓰세요. "
          "규칙: (1) NPC 대사는 존댓말로 통일하되 원문이 거친 말투면 그 어조를 살림 (2) <...> 토큰과 숫자는 그대로 유지 "
          "(3) 용어 힌트가 있으면 반드시 그 표기 사용 (4) 한자와 영어 단어를 섞지 말고 고유명사는 한글로 표기 "
          "(5) 기계번역이 이미 정확하면 그대로 출력 (6) 설명 없이 고친 번역문만 출력.")


def clean(ko):
    ko = ko.replace(" ⁇ ", " ").replace("⁇", "")
    for a, b in REPL:
        ko = ko.replace(a, b)
    return re.sub(r"  +", " ", ko).strip()


def latin(s):
    return {w.lower() for w in re.findall(r"[A-Za-z]{2,}", TOK.sub(" ", s))}


def ident(en):
    e = en.strip()
    return bool(re.fullmatch(r"[A-Za-z0-9_\-\.]+", e)) and ("_" in e or bool(re.search(r"[a-z][A-Z]", e)) or e.isupper())


def gate(en, mt, llm):
    """-> (통과 여부, 사유)"""
    if sorted(TOK.findall(en)) != sorted(TOK.findall(llm)):
        return False, "token"
    if CJK.search(llm) or "⁇" in llm or re.search(r"#{5,}", llm):
        return False, "cjk"
    if not latin(llm) <= latin(mt):
        return False, "latin"
    if not re.search(r"[가-힣]", llm) and re.search(r"[A-Za-z]{3,}", en):
        return False, "nohangul"
    return True, ""


def main():
    argv = sys.argv[1:]
    B = argv[0]
    opt = {"--cats": "ui,names,dialog,long", "--limit": "0", "--par": "4", "--url": "http://127.0.0.1:8080"}
    for i, a in enumerate(argv):
        if a in opt and i + 1 < len(argv):
            opt[a] = argv[i + 1]
    cats = opt["--cats"].split(",")
    out_dir = os.path.join(B, "llm")
    os.makedirs(out_dir, exist_ok=True)
    gl = json.load(open(os.path.join(B, "ncs", "glossary.json"), encoding="utf-8"))
    exact, terms = gl["exact"], gl["terms"]
    corr = json.load(open(os.path.join(B, "mt", "corr_global.json"), encoding="utf-8"))
    tl = sorted((t for t in terms if len(t) >= 5), key=len, reverse=True)
    rx = re.compile(r"(?<![A-Za-z])(" + "|".join(re.escape(t) for t in tl) + r")(?![A-Za-z])")

    pool, freq = {}, collections.Counter()
    for p in glob.glob(os.path.join(B, "mt", "*_all.json")) + glob.glob(os.path.join(B, "community", "*", "all.json")):
        for en, ko in json.load(open(p, encoding="utf-8")).items():
            freq[en] += 1
            if en not in pool:
                pool[en] = corr.get(en) or exact.get(en.strip()) or clean(ko)

    def cat(en):
        w = len(en.split())
        hits = len(set(rx.findall(en)))
        if hits >= 2 or (hits >= 1 and w <= 14):
            return "names"
        if w <= 4:
            return "ui"
        if 5 <= w <= 14:
            return "dialog"
        if w >= 15:
            return "long"
        return None

    status_path = os.path.join(out_dir, "llm_status.jsonl")
    done = {}
    if os.path.exists(status_path):
        for line in open(status_path, encoding="utf-8"):
            try:
                d = json.loads(line)
                done[d["en"]] = d
            except Exception:
                pass
    good_path = os.path.join(out_dir, "all.llm.json")
    good = json.load(open(good_path, encoding="utf-8")) if os.path.exists(good_path) else {}

    todo = []
    for c in cats:
        items = [en for en in pool if cat(en) == c and en not in done and len(en) <= 450
                 and not re.fullmatch(r"[\d\s.,:+\-/%]*", en.strip()) and not en.startswith("<<") and not ident(en)
                 and len(re.findall(r"[A-Za-z0-9']+", TOK.sub(" ", en))) >= 2]   # 한 단어 문자열은 환각 위험이 커서 제외
        items.sort(key=lambda e: (-freq[e], len(e)))
        todo += items
    if int(opt["--limit"]):
        todo = todo[:int(opt["--limit"])]
    print(f"already {len(done)}, todo {len(todo)} ({', '.join(cats)})", flush=True)

    def ask(en):
        mt = pool[en]
        hints = []
        for m in rx.findall(en):
            if m not in [h[0] for h in hints]:
                hints.append((m, terms[m]))
        hint = ("용어 힌트: " + ", ".join(f"{a}={b}" for a, b in hints[:8]) + "\n") if hints else ""
        body = {"model": "x", "temperature": 0.2, "max_tokens": 900 if len(en) > 200 else 400, "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"{hint}원문: {en}\n기계번역: {mt}\n고친 번역:"}]}
        req = urllib.request.Request(opt["--url"] + "/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        for attempt in range(3):
            try:
                r = json.loads(urllib.request.urlopen(req, timeout=300).read())
                return en, r["choices"][0]["message"]["content"].strip()
            except Exception as e:  # noqa: BLE001
                err = str(e)
                time.sleep(2)
        return en, None

    t0, n, ok, errs = time.time(), 0, 0, 0
    sf = open(status_path, "a", encoding="utf-8")
    with cf.ThreadPoolExecutor(int(opt["--par"])) as ex:
        futs = []
        it = iter(todo)
        pending = set()
        # 동시에 par*3 개만 제출해 메모리/대기열을 제한한다
        def submit_more():
            while len(pending) < int(opt["--par"]) * 3:
                en = next(it, None)
                if en is None:
                    return
                pending.add(ex.submit(ask, en))
        submit_more()
        while pending:
            dn, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for f in dn:
                en, llm = f.result()
                mt = pool[en]
                if llm is None:
                    errs += 1
                    if errs >= 12:
                        print("SERVER ERROR: 연속 실패 12회 - 중단합니다(이어하기 가능)", flush=True)
                        json.dump(good, open(good_path, "w", encoding="utf-8"), ensure_ascii=False)
                        sf.flush()
                        os._exit(2)
                    continue
                errs = 0
                if llm.strip() == mt.strip():
                    rec = {"en": en, "status": "same"}
                else:
                    passed, why = gate(en, mt, llm)
                    rec = {"en": en, "status": "ok" if passed else "rejected", "why": why}
                    if passed:
                        good[en] = llm
                        ok += 1
                sf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
            sf.flush()
            if n % 200 < len(dn):
                json.dump(good, open(good_path, "w", encoding="utf-8"), ensure_ascii=False)
                el = time.time() - t0
                print(f"{n}/{len(todo)} accepted {ok} | {n/el:.2f}/s | eta {(len(todo)-n)/max(n/el,0.01)/3600:.1f}h", flush=True)
            submit_more()
    json.dump(good, open(good_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"DONE {n} processed, {ok} accepted in {(time.time()-t0)/60:.0f} min", flush=True)


if __name__ == "__main__":
    main()
