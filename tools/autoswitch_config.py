# -*- coding: utf-8 -*-
"""version.dll 의 자동 전환 기능이 읽는 설정 파일(nwn_ko_autoswitch.txt)을 만든다.

usage: py autoswitch_config.py [--out <경로>] [--disable]
  기본 출력: <게임>\\bin\\win32\\nwn_ko_autoswitch.txt
  --disable : enabled=0 으로 써서 기능을 끈다
형식은 hook/autoswitch.c 맨 위 주석을 참고. 번역본이 만들어진(준비됨/적용됨) 캠페인만 포함한다.
"""
import os, sqlite3, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "installer"))
import nwn_ko_installer as m   # noqa: E402


def build_text(enabled=True):
    nws = Path(os.environ.get("NWN_NWSYNC_DIR") or (m.DOCS / "nwsync"))
    db = nws / "nwsyncmeta.sqlite3"
    lines = [f"enabled={1 if enabled else 0}", f"dev={m.DEV}", f"lib={m.DOCS / 'ko_campaigns'}", f"logs={m.DOCS / 'logs'}"]
    n = 0
    if db.exists():
        meta = sqlite3.connect(str(db))
        for it in m.ITEMS.values():
            if isinstance(it, m.CommunityModule) and it.ready and it.built():
                name = (m.HERE / "community" / it.slug / "NAME.txt").read_text(encoding="utf-8").strip()
                row = meta.execute("select manifest_sha1 from manifest_metadata where module_name=?", (name,)).fetchone()
                if row:
                    lines.append(f"map\t{row[0]}\t{it.slug}")
                    n += 1
    return "\n".join(lines) + "\n", n


def main():
    out = m.BIN / "nwn_ko_autoswitch.txt"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    text, n = build_text("--disable" not in sys.argv)
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"{out}: 캠페인 {n}개, enabled={'0' if '--disable' in sys.argv else '1'}")


if __name__ == "__main__":
    main()
