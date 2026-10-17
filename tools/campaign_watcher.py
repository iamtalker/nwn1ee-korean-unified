# -*- coding: utf-8 -*-
"""(실험) 게임이 커뮤니티 캠페인을 열 때 번역 폴더를 자동으로 전환하는 감시 프로그램. 게임 프로그램은 건드리지 않는다.

게임은 캠페인을 열 때 로그(문서\\logs\\nwclientLog1.txt)에 'Loading Module: <manifest 해시>' 를 남긴다.
이 줄을 읽어 해시 -> 캠페인을 찾아 그 캠페인의 번역본을 development 에 연결한다.
번역본에 없는 모듈(공식 캠페인 등)이면 연결돼 있던 커뮤니티 번역을 해제해 충돌을 막는다.

조건: 게임이 development 폴더를 모듈 로드 중에 다시 읽어야 한다(실험으로 확인할 것). 안 되면 이 방식은 쓸 수 없다.

usage: py campaign_watcher.py [--prepare]   (--prepare: 시작할 때 내려받은 캠페인의 번역본을 모두 미리 만든다)
환경변수 NWN_DOCS_DIR / NWN_GAME_DIR / NWN_NWSYNC_DIR 는 설치 프로그램과 같다.
"""
import os, re, sqlite3, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "installer"))
import nwn_ko_installer as m   # noqa: E402

LOAD = re.compile(r"Loading Module:\s*(\S+)")


def build_map():
    """manifest 해시 -> CommunityModule"""
    nws = Path(os.environ.get("NWN_NWSYNC_DIR") or (m.DOCS / "nwsync"))
    db = nws / "nwsyncmeta.sqlite3"
    out = {}
    if not db.exists():
        return out
    meta = sqlite3.connect(str(db))
    for it in m.ITEMS.values():
        if isinstance(it, m.CommunityModule) and it.ready:
            name = (m.HERE / "community" / it.slug / "NAME.txt").read_text(encoding="utf-8").strip()
            row = meta.execute("select manifest_sha1 from manifest_metadata where module_name=?", (name,)).fetchone()
            if row:
                out[row[0]] = it
    return out


def newest_log():
    logs = m.DOCS / "logs"
    c = sorted(logs.glob("nwclientLog*.txt"), key=lambda p: p.stat().st_mtime, reverse=True) if logs.exists() else []
    return c[0] if c else None


def main():
    if "--prepare" in sys.argv:
        for it in m.ITEMS.values():
            if isinstance(it, m.CommunityModule) and it.ready:
                try:
                    print("준비:", it.name, flush=True)
                    it.prepare()
                except Exception as e:  # noqa: BLE001
                    print("  건너뜀:", e)
    hmap = build_map()
    print(f"감시 시작: 캠페인 {len(hmap)}개 인식. 게임에서 캠페인을 열면 자동 전환합니다. (Ctrl+C 로 종료)", flush=True)
    path, pos = None, 0
    while True:
        p = newest_log()
        if p != path:
            path, pos = p, (p.stat().st_size if p else 0)        # 새 로그 파일이면 지금 위치부터
        if path and path.exists():
            size = path.stat().st_size
            if size < pos:
                pos = 0
            if size > pos:
                with open(path, "rb") as f:
                    f.seek(pos)
                    chunk = f.read()
                pos = size
                for mm in LOAD.finditer(chunk.decode("utf-8", "replace")):
                    sha = mm.group(1)
                    it = hmap.get(sha)
                    t = time.time()
                    if it is not None:
                        if it.applied():
                            print(f"[{time.strftime('%H:%M:%S')}] {it.name}: 이미 연결됨", flush=True)
                        else:
                            it.patch()
                            print(f"[{time.strftime('%H:%M:%S')}] {it.name}: 전환 완료 ({time.time() - t:.1f}초)", flush=True)
                    else:
                        act = [x for x in m.ITEMS.values() if isinstance(x, m.CommunityModule) and x.applied()]
                        for x in act:
                            x.restore()
                        print(f"[{time.strftime('%H:%M:%S')}] 번역본에 없는 모듈({sha[:12]}): 연결 해제 {len(act)}개", flush=True)
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
