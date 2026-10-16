# -*- coding: utf-8 -*-
"""릴리스 zip 생성: python tools/build_release.py <버전>  (assets/ 에 version.dll, dialog.tlk 필요)"""
import sys
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
ver = sys.argv[1] if len(sys.argv) > 1 else "dev"
out = root / "dist" / f"nwn1ee-korean-unified-{ver}.zip"
out.parent.mkdir(exist_ok=True)
(root / "installer" / "VERSION.txt").write_text(ver, encoding="utf-8")

include = ["README.md", "LICENSE", "NOTICE.md", "run_installer.bat", "installer", "hook", "assets"]
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name in include:
        p = root / name
        files = [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
        for f in files:
            if "__pycache__" in f.parts or f.suffix == ".pyc" or f.name == "external_patch.txt":
                continue
            z.write(f, f.relative_to(root).as_posix())
print(out, out.stat().st_size)
