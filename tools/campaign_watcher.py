# -*- coding: utf-8 -*-
"""(시제품) 커뮤니티 캠페인 번역 자동 전환. 게임 프로그램은 건드리지 않고 문서\\development 폴더만 다룬다.

원리 (2026-10-17 실험으로 확인):
  - 게임은 development 의 '파일 이름 목록'을 시작할 때 정한다 -> 게임을 켜기 전에 모든 캠페인의 파일 이름을 미리 깔아 둔다(seed).
  - 파일 '내용'은 열 때마다 읽는다. 지우면 모듈 안의 원본으로 돌아가고, 다시 넣으면 다시 읽는다.
  - 게임은 캠페인을 열 때 로그(문서\\logs\\nwclientLog1.txt)에 'Loading Module: <manifest 해시>' 를 남긴다.
  => 그 줄을 읽어 해당 캠페인의 번역본만 development 에 남기고(하드링크, 복사 없음) 나머지 이름은 지운다.
  번역본에 없는 모듈(공식 캠페인 등)이면 전부 지워서 영향을 없앤다.

주의: seed 상태에서는 게임을 이 프로그램이 실행 중일 때만 쓸 것(꺼지면 다른 캠페인과 이름이 겹쳐 오작동할 수 있다).
      종료하면 자동으로 정리하며, 비정상 종료 후에는 `--cleanup` 으로 정리한다.

usage:
  py campaign_watcher.py            seed -> 감시 (게임이 꺼지면 자동 정리·종료, 게임은 seed 후에 켜야 함)
  py campaign_watcher.py --cleanup  seed 로 깐 파일을 모두 지운다
  py campaign_watcher.py --prepare  (위와 같고, 시작할 때 내려받은 캠페인의 번역본을 모두 미리 만든다)
환경변수 NWN_DOCS_DIR / NWN_GAME_DIR / NWN_NWSYNC_DIR 는 설치 프로그램과 같다.
"""
import json, os, re, sqlite3, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "installer"))
import nwn_ko_installer as m   # noqa: E402

LOAD = re.compile(r"Loading Module:\s*(\S+)")
STATE = m.CACHE / "seed_state.json"          # {파일이름(소문자): 현재 소유 캠페인 slug 또는 null}


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


def lib_files(it):
    return {f.name.lower(): f for f in it.lib().iterdir() if f.name != "_complete.json"}


def link(src, dst):
    try:
        os.link(src, dst)                 # 하드링크: 복사 없이 즉시
    except OSError:
        import shutil
        shutil.copyfile(src, dst)


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(st):
    m.CACHE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st), encoding="utf-8")


def cleanup():
    st = load_state()
    n = 0
    for name in st:
        p = m.DEV / name
        try:
            if p.exists():
                p.unlink()
                n += 1
        except OSError:
            pass
    if STATE.exists():
        STATE.unlink()
    print(f"정리: {n}개 삭제", flush=True)


class Seeder:
    def __init__(self, items):
        self.items = items                                    # slug -> CommunityModule (번역본 있는 것만)
        self.files = {s: lib_files(it) for s, it in items.items()}
        self.names = sorted({n for fs in self.files.values() for n in fs})
        self.state = {}

    def seed(self):
        """모든 이름을 깐다 (게임 시작 전). 이름마다 소유 캠페인 하나를 정해 링크한다."""
        for it in m.ITEMS.values():                           # 이전 방식(복사 연결)이 남아 있으면 해제
            if isinstance(it, m.CommunityModule) and it.applied():
                it.restore()
        cleanup()
        m.DEV.mkdir(parents=True, exist_ok=True)
        t = time.time()
        for n in self.names:
            owner = next(s for s, fs in self.files.items() if n in fs)
            dst = m.DEV / self.files[owner][n].name
            if dst.exists():
                dst.unlink()
            link(self.files[owner][n], dst)
            self.state[n] = owner
        save_state(self.state)
        print(f"seed: 이름 {len(self.names)}개 ({time.time() - t:.1f}초). 이제 게임을 켜세요.", flush=True)

    def activate(self, slug):
        """slug 캠페인의 번역본만 남기고 나머지는 지운다. slug=None 이면 전부 지운다."""
        t = time.time()
        want = self.files.get(slug, {}) if slug else {}
        add = rem = 0
        for n in self.names:
            cur = self.state.get(n)
            if n in want:
                if cur != slug:
                    dst = m.DEV / want[n].name
                    if dst.exists():
                        dst.unlink()
                    link(want[n], dst)
                    self.state[n] = slug
                    add += 1
            elif cur is not None:
                p = m.DEV / self.files[cur][n].name
                if p.exists():
                    p.unlink()
                self.state[n] = None
                rem += 1
        save_state(self.state)
        return add, rem, time.time() - t


def newest_log():
    logs = m.DOCS / "logs"
    c = sorted(logs.glob("nwclientLog*.txt"), key=lambda p: p.stat().st_mtime, reverse=True) if logs.exists() else []
    return c[0] if c else None


def game_running():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq nwmain.exe"], capture_output=True, text=True)
    return "nwmain.exe" in r.stdout


def main():
    if "--cleanup" in sys.argv:
        cleanup()
        return
    if "--prepare" in sys.argv:
        for it in m.ITEMS.values():
            if isinstance(it, m.CommunityModule) and it.ready:
                try:
                    print("준비:", it.name, flush=True)
                    it.prepare()
                except Exception as e:  # noqa: BLE001
                    print("  건너뜀:", e)
    hmap = build_map()
    items = {it.slug: it for it in hmap.values() if it.built()}
    if game_running():
        print("게임이 이미 켜져 있습니다. 게임을 끄고 다시 실행하세요(이름 목록은 게임 시작 때 정해집니다).")
        return
    sd = Seeder(items)
    sd.seed()
    print(f"감시 시작: 캠페인 {len(items)}개. 게임에서 캠페인을 열면 자동 전환합니다. 게임을 끄면 자동으로 정리하고 종료합니다.", flush=True)
    path, pos, seen_game = None, 0, False
    try:
        while True:
            p = newest_log()
            if p != path:
                path, pos = p, (p.stat().st_size if p else 0)
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
                        slug = it.slug if it is not None and it.slug in items else None
                        add, rem, sec = sd.activate(slug)
                        who = it.name if slug else f"번역본에 없는 모듈({sha[:12]})"
                        print(f"[{time.strftime('%H:%M:%S')}] {who}: 연결 +{add} / 해제 -{rem} ({sec:.1f}초)", flush=True)
            g = game_running()
            if g:
                seen_game = True
            elif seen_game:
                print("게임이 종료되어 정리합니다.", flush=True)
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
