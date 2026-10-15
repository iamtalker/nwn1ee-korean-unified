# -*- coding: utf-8 -*-
"""NWN:EE 통합 한글 패치 설치 프로그램

- 게임 파일을 재배포하지 않는다. 사용자의 로컬 게임 파일에 패치를 적용하거나,
  로컬 파일 + 번역 CSV 로 번역본을 새로 만든다.
- 게임 캠페인 선택 화면(공식 / 프리미엄 / 커뮤니티 / 로컬)의 분류를 따른다.
- 덮어쓴 파일은 *.orig 로 백업하고, [원복] 으로 되돌릴 수 있다.

사용:
  py nwn_ko_installer.py             GUI
  py nwn_ko_installer.py --list      상태 출력
  py nwn_ko_installer.py --patch-all / --restore-all
환경변수(선택): NWN_GAME_DIR, NWN_DOCS_DIR, NWN_EXT_KR(외부 확장모듈 한패 zip/폴더)
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = ROOT / "assets"
MODBUILD = HERE / "modbuild"

sys.path.insert(0, str(HERE))
import engine_patch  # noqa: E402

ORIGINAL_ENGINE_SHA = engine_patch.ORIGINAL_SHA256
EXT_WORKSHOP_ID = "3437559043"          # Steam 창작마당: nwn1ee_dod_kr (4개 확장 모듈 한글)
EXT_GDRIVE_ID = "1ru5f-Fy_vbS4vXIqIwP4SgIagmOlqrtw"   # 제작자가 직접 공개한 배포 파일
EXT_MARK = "kr_nwm/Neverwinter Nights - Doom of Icewind Dale.nwm"
REPO = "iamtalker/nwn1ee-korean-unified"
CACHE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "nwn1ee-korean"


# ----------------------------------------------------------------- 경로 탐색
def find_game() -> Path:
    env = os.environ.get("NWN_GAME_DIR")
    if env:
        return Path(env)
    cands = []
    try:                                   # 이전에 사용자가 직접 지정한 경로
        saved = (CACHE / "game_dir.txt").read_text(encoding="utf-8").strip()
        if saved:
            cands.append(Path(saved))
    except OSError:
        pass
    steam_roots = [Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam")]
    for root in steam_roots:
        cands.append(root / "steamapps" / "common" / "Neverwinter Nights")
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            try:
                for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
                    cands.append(Path(m.group(1).replace("\\\\", "\\")) / "steamapps" / "common" / "Neverwinter Nights")
            except OSError:
                pass
    for drive in "DEFG":
        cands += [Path(f"{drive}:\\SteamLibrary\\steamapps\\common\\Neverwinter Nights"),
                  Path(f"{drive}:\\Steam\\steamapps\\common\\Neverwinter Nights")]
    for c in cands:
        if (c / "bin" / "win32" / "nwmain.exe").exists():
            return c
    return cands[0]


def find_docs() -> Path:
    """게임이 실제로 쓰는 사용자 폴더 (nwn.ini 가 있는 'Neverwinter Nights*' 폴더).

    EE 는 '문서\\Neverwinter Nights' 가 이미 있고 nwn.ini 가 없으면 구형 NWN 폴더로
    보고 'Neverwinter Nights.0' 처럼 새 폴더를 만든다. 따라서 nwn.ini 기준으로 찾는다.
    """
    env = os.environ.get("NWN_DOCS_DIR")
    if env:
        return Path(env)
    base = None
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-c", '[Environment]::GetFolderPath("MyDocuments")'],
            capture_output=True, text=True, timeout=8)
        if r.stdout.strip():
            base = Path(r.stdout.strip())
    except Exception:
        pass
    base = base or Path.home() / "Documents"
    found = [p for p in base.glob("Neverwinter Nights*") if (p / "nwn.ini").exists()]
    if found:
        return max(found, key=lambda p: (p / "nwn.ini").stat().st_mtime)
    return base / "Neverwinter Nights"


GAME = find_game()
DOCS = find_docs()
DOCS_READY = (DOCS / "nwn.ini").exists() or bool(os.environ.get("NWN_DOCS_DIR"))
BIN = GAME / "bin" / "win32"
NWM = GAME / "data" / "nwm"
MODDIR = GAME / "data" / "mod"
OVR = DOCS / "override"
HAK = DOCS / "hak"
FONT_SRC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "malgun.ttf"
FONT_NAMES = ["fnt_default.ttf", "fnt_default_hr.ttf", "fnt_maintext.ttf"]


# ----------------------------------------------------------------- 파일 유틸
def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def bak_of(p: Path) -> Path:
    return p.with_name(p.name + ".orig")


def _backup_if_foreign(dst: Path, new_sha: str):
    bak = bak_of(dst)
    if dst.exists() and not bak.exists() and sha_file(dst) != new_sha:
        shutil.copy2(dst, bak)


def put_file(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    _backup_if_foreign(dst, sha_file(src))
    shutil.copy2(src, dst)


def put_bytes(data: bytes, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    _backup_if_foreign(dst, sha_bytes(data))
    dst.write_bytes(data)


def unput(dst: Path):
    bak = bak_of(dst)
    if bak.exists():
        shutil.copy2(bak, dst)
        bak.unlink()
    elif dst.exists():
        dst.unlink()


def need_docs():
    if not DOCS_READY:
        raise RuntimeError(
            "문서 폴더에 게임 설정(nwn.ini)이 아직 없습니다.\n"
            "게임을 한 번 실행했다가 종료한 뒤 다시 패치하세요.\n"
            "(먼저 폴더를 만들어 두면 게임이 다른 이름의 폴더를 새로 만들어 한글이 적용되지 않습니다.)")



# ----------------------------------------------------------------- 자동 다운로드
def download(url: str, dest: Path, what: str = "파일") -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "nwn1ee-korean-installer"})
    print(f"다운로드: {what} ...", flush=True)
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    tmp.replace(dest)
    return dest


def ensure_assets():
    """assets/version.dll, assets/dialog.tlk 가 없으면(소스 저장소로 실행한 경우) 최신 릴리스에서 받는다."""
    need = [n for n in ("version.dll", "dialog.tlk") if not (ASSETS / n).exists()]
    if not need:
        return
    import json
    api = f"https://api.github.com/repos/{REPO}/releases/latest"
    req = urllib.request.Request(api, headers={"User-Agent": "nwn1ee-korean-installer"})
    with urllib.request.urlopen(req, timeout=30) as r:
        rel = json.load(r)
    asset = next((a for a in rel.get("assets", []) if a["name"].endswith(".zip")), None)
    if not asset:
        raise RuntimeError("릴리스에서 assets 를 찾지 못했습니다.")
    with tempfile.TemporaryDirectory() as t:
        z = download(asset["browser_download_url"], Path(t) / asset["name"], "필수 리소스(version.dll, dialog.tlk)")
        with zipfile.ZipFile(z) as zf:
            for n in need:
                ASSETS.mkdir(exist_ok=True)
                (ASSETS / n).write_bytes(zf.read("assets/" + n))


def download_ext() -> "Path | None":
    """확장 모듈 한글패치(nwn1ee_dod_kr.zip)를 제작자가 공개한 Google Drive 링크에서 받는다."""
    dest = CACHE / "nwn1ee_dod_kr.zip"
    base = "https://drive.usercontent.google.com/download?id=%s&export=download&confirm=t" % EXT_GDRIVE_ID
    try:
        download(base, dest, "확장 모듈 한글패치 nwn1ee_dod_kr.zip (약 60MB)")
        with zipfile.ZipFile(dest) as z:
            z.getinfo(EXT_MARK)
        return dest
    except Exception:
        try:
            dest.unlink()
        except OSError:
            pass
        return None

# ----------------------------------------------------------------- 외부 확장모듈 한패
class ExtSource:
    """nwn1ee_dod_kr (Steam 창작마당) 한패를 zip 또는 압축 해제된 폴더로 읽는다."""

    def __init__(self, path: Path):
        self.path = path
        self.zip = zipfile.ZipFile(path) if path.is_file() else None

    def read(self, member: str) -> bytes:
        if self.zip:
            return self.zip.read(member)
        return (self.path / member).read_bytes()

    def size(self, member: str) -> int:
        if self.zip:
            return self.zip.getinfo(member).file_size
        return (self.path / member).stat().st_size

    def has(self, member: str) -> bool:
        try:
            self.size(member)
            return True
        except (KeyError, OSError):
            return False


_ext_cache = {}


def find_ext(prompt=False):
    if "src" in _ext_cache:
        return _ext_cache["src"]
    cands = []
    if os.environ.get("NWN_EXT_KR"):
        cands.append(Path(os.environ["NWN_EXT_KR"]))
    cfg = HERE / "external_patch.txt"
    if cfg.exists():
        cands.append(Path(cfg.read_text(encoding="utf-8").strip()))
    cands += [
        GAME.parent.parent / "workshop" / "content" / "704450" / EXT_WORKSHOP_ID,
        CACHE / "nwn1ee_dod_kr.zip",
        Path.home() / "Downloads" / "nwn1ee_dod_kr.zip",
        ROOT.parent / "네윈나1 확장캠페인 한글화" / "nwn1ee_dod_kr.zip",
    ]
    for c in cands:
        try:
            if c.exists():
                s = ExtSource(c)
                if s.has("kr_nwm/Neverwinter Nights - Doom of Icewind Dale.nwm"):
                    _ext_cache["src"] = s
                    return s
        except (OSError, zipfile.BadZipFile):
            continue
    if prompt:
        ok = True
        try:
            from tkinter import messagebox
            msg = chr(10).join([
                "프리미엄 4종(DoD/ToTM/PotSC/DoIWD)의 한글은 제작자가 따로 배포한",
                "nwn1ee_dod_kr 패치를 사용합니다. 컴퓨터에서 찾지 못했습니다.",
                "",
                "제작자가 공개한 링크에서 지금 받을까요? (약 60MB)"])
            ok = messagebox.askyesno("확장 모듈 한글패치 필요", msg)
        except Exception:
            pass
        if ok:
            z = download_ext()
            if z:
                _ext_cache["src"] = ExtSource(z)
                return _ext_cache["src"]
        try:
            from tkinter import filedialog
            f = filedialog.askopenfilename(
                title="nwn1ee_dod_kr.zip 파일을 직접 선택하세요 (취소하면 건너뜀)",
                filetypes=[("zip", "*.zip"), ("all", "*.*")])
            if f:
                s = ExtSource(Path(f))
                if s.has(EXT_MARK):
                    (HERE / "external_patch.txt").write_text(f, encoding="utf-8")
                    _ext_cache["src"] = s
                    return s
        except Exception:
            pass
    return None


# ----------------------------------------------------------------- 항목 동작
class Item:
    def __init__(self, id_, name, desc="", ready=False):
        self.id, self.name, self.desc, self.ready = id_, name, desc, ready

    def applied(self) -> bool:
        return False

    def patch(self):
        raise NotImplementedError

    def restore(self):
        raise NotImplementedError


class Todo(Item):
    def __init__(self, id_, name):
        super().__init__(id_, name, "", False)


class Engine(Item):
    def __init__(self):
        super().__init__("engine", "엔진·UI 한글 지원 (필수)", "nwmain.exe 패치 + version.dll + 폰트", True)

    def applied(self):
        exe, orig, dll = BIN / "nwmain.exe", bak_of(BIN / "nwmain.exe"), BIN / "version.dll"
        a = ASSETS / "version.dll"
        return (exe.exists() and orig.exists() and dll.exists() and a.exists()
                and sha_file(dll) == sha_file(a) and sha_file(exe) != sha_file(orig))

    def patch(self):
        need_docs()
        exe = BIN / "nwmain.exe"
        orig = bak_of(exe)
        if not exe.exists():
            raise RuntimeError(f"nwmain.exe 를 찾을 수 없습니다:\n{exe}")
        if not (ASSETS / "version.dll").exists():
            raise RuntimeError("assets\\version.dll 이 없습니다 (릴리스 zip 으로 설치하세요).")
        if not FONT_SRC.exists():
            raise RuntimeError(f"한글 폰트를 찾을 수 없습니다: {FONT_SRC}")
        src = orig if orig.exists() else exe
        data = src.read_bytes()
        if sha_bytes(data) != ORIGINAL_ENGINE_SHA:
            raise RuntimeError(
                "nwmain.exe 가 지원 빌드(8193.37 원본)와 다릅니다.\n"
                "Steam 에서 '게임 파일 무결성 검사' 후 다시 시도하세요.")
        out, _log = engine_patch.patch_bytes(data)
        if not orig.exists():
            shutil.copy2(exe, orig)
        exe.write_bytes(out)
        put_file(ASSETS / "version.dll", BIN / "version.dll")
        for n in FONT_NAMES:
            put_file(FONT_SRC, OVR / n)

    def restore(self):
        exe, orig = BIN / "nwmain.exe", bak_of(BIN / "nwmain.exe")
        if orig.exists():
            shutil.copy2(orig, exe)
            orig.unlink()
        unput(BIN / "version.dll")
        for n in FONT_NAMES:
            unput(OVR / n)


class BaseTlk(Item):
    """본편 번역 (dialog.tlk). OC / SoU / HotU 가 같은 파일을 공유한다."""

    def applied(self):
        a, d = ASSETS / "dialog.tlk", OVR / "dialog.tlk"
        return a.exists() and d.exists() and sha_file(a) == sha_file(d)

    def patch(self):
        need_docs()
        if not (ASSETS / "dialog.tlk").exists():
            raise RuntimeError("assets\\dialog.tlk 이 없습니다 (릴리스 zip 으로 설치하세요).")
        put_file(ASSETS / "dialog.tlk", OVR / "dialog.tlk")

    def restore(self):
        unput(OVR / "dialog.tlk")


class ExtModule(Item):
    """Steam 창작마당 nwn1ee_dod_kr 에 들어 있는 확장 모듈 한글 파일을 설치한다."""

    def __init__(self, id_, name, nwm_name, tlk=None, hak=None):
        super().__init__(id_, name, "외부 한패(nwn1ee_dod_kr) 필요", True)
        self.files = [(f"kr_nwm/Neverwinter Nights - {nwm_name}.nwm",
                       NWM / f"Neverwinter Nights - {nwm_name}.nwm")]
        if tlk:
            self.files.append((f"override/{tlk}", OVR / tlk))
        if hak:
            self.files.append((f"hak/{hak}", HAK / hak))

    def applied(self):
        s = find_ext()
        if not s:
            return False
        try:
            return all(d.exists() and d.stat().st_size == s.size(m) for m, d in self.files)
        except (KeyError, OSError):
            return False

    def patch(self):
        need_docs()
        s = find_ext(prompt=True)
        if not s:
            raise RuntimeError(
                "확장 모듈 한글패치 파일을 찾지 못했습니다.\n"
                "Steam 창작마당 'nwn1ee_dod_kr' (id 3437559043)를 받아 zip 위치를 지정하세요.")
        for m, d in self.files:
            put_bytes(s.read(m), d)

    def restore(self):
        for _m, d in self.files:
            unput(d)


class BuiltMod(Item):
    """게임의 .mod 원본 + 번역 CSV 로 번역본 모듈을 만들어 설치한다."""

    def __init__(self, id_, name, short, filename, nwm=False):
        super().__init__(id_, name, "번역 CSV로 로컬 모듈에서 생성", True)
        self.short, self.filename, self.nwm = short, filename, nwm
        self.dst = (NWM if nwm else MODDIR) / filename

    def applied(self):
        b = bak_of(self.dst)
        return self.dst.exists() and b.exists() and sha_file(self.dst) != sha_file(b)

    def patch(self):
        src = bak_of(self.dst) if bak_of(self.dst).exists() else self.dst
        if not src.exists():
            raise RuntimeError(f"원본 모듈을 찾을 수 없습니다:\n{self.dst}")
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            sub = "nwm" if self.nwm else "mod"
            (tmp / "base" / "data" / sub).mkdir(parents=True)
            shutil.copy2(src, tmp / "base" / "data" / sub / self.filename)
            env = dict(os.environ, NWN_BASE=str(tmp / "base"), NWN_BUILD_DIR=str(tmp / "out"),
                       PYTHONIOENCODING="utf-8")
            r = subprocess.run(
                [sys.executable, str(MODBUILD / "premium" / "build_premium.py"), self.short],
                cwd=str(MODBUILD), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
            out = tmp / "out" / self.short / self.filename
            if r.returncode != 0 or not out.exists():
                raise RuntimeError("모듈 빌드 실패:\n" + (r.stdout + r.stderr)[-800:])
            put_file(out, self.dst)

    def restore(self):
        unput(self.dst)


ITEMS = {i.id: i for i in [
    Engine(),
    BaseTlk("oc", "The Wailing Death (오리지널 캠페인)", "본편 번역 (dialog.tlk 공용)", True),
    BaseTlk("sou", "Shadows of Undrentide", "본편 번역 (dialog.tlk 공용)", True),
    BaseTlk("hotu", "Hordes of the Underdark", "본편 번역 (dialog.tlk 공용)", True),
    BuiltMod("km", "Kingmaker", "kingmaker", "Kingmaker.mod"),
    BuiltMod("sg", "ShadowGuard", "shadowguard", "ShadowGuard.mod"),
    BuiltMod("ww", "Witch's Wake", "witchswake", "Witch's Wake.mod"),
    BuiltMod("coc", "Contest of Champions", "coc", "Contest Of Champions 0492.mod"),
    BuiltMod("darkranger", "The Dark Ranger's Treasure", "darkranger", "The Dark Ranger's Treasure.mod"),
    BuiltMod("eremor", "The Winds of Eremor", "eremor", "The Winds of Eremor.mod"),
    BuiltMod("toheir", "To Heir is Human", "toheirishuman", "To Heir is Human.mod"),
    BuiltMod("chess", "Neverwinter Chess", "chess", "Neverwinter Chess.mod"),
    ExtModule("doiwd", "Doom of Icewind Dale", "Doom of Icewind Dale", tlk="doiwd.tlk", hak="doiwd_hak.hak"),
    ExtModule("totms", "Tyrants of the Moonsea", "Tyrants of the Moonsea", tlk="tyrants.tlk"),
    ExtModule("dod", "Darkness over Daggerford", "Darkness over Daggerford", tlk="ossian.tlk"),
    BuiltMod("ddf", "Dark Dreams of Furiae", "ddf", "Neverwinter Nights - Dark Dreams of Furiae.nwm", nwm=True),
    ExtModule("potsc", "Pirates of the Sword Coast", "Pirates of the Sword Coast", tlk="potsc.tlk", hak="potsc_tkr.hak"),
    BuiltMod("wcoc", "Wyvern Crown of Cormyr", "wcoc", "Neverwinter Nights - Wyvern Crown of Cormyr.nwm", nwm=True),
    BuiltMod("id", "Infinite Dungeons", "id", "Neverwinter Nights - Infinite Dungeons.nwm", nwm=True),
    Todo("c_hunt", "A Hunt Through The Dark"),
    Todo("c_eotb", "Eye of the Beholder"),
    Todo("c_aielund", "Aielund Saga"),
    Todo("c_auren", "Auren Saga"),
    Todo("c_tethyr", "Crimson Tides of Tethyr"),
    Todo("c_shadowdale", "Siege of Shadowdale"),
    Todo("c_reptile", "Cult of the Reptile God"),
]}

# 게임 캠페인 선택 화면 분류/순서
LAYOUT = [
    ("#", "공통 (필수)"), "engine",
    ("#", "공식 - Classic Campaigns"), "oc", "sou", "hotu",
    ("#", "공식 - Extra Content"), "km", "sg", "ww", "coc", "darkranger", "eremor", "toheir", "chess",
    ("#", "프리미엄"), "doiwd", "totms", "dod", "ddf", "potsc", "wcoc", "id",
    ("#", "커뮤니티  (모듈 파일 확보 후 번역 가능)"),
    "c_hunt", "c_eotb", "c_aielund", "c_auren", "c_tethyr", "c_shadowdale", "c_reptile",
    ("#", "로컬  (직접 설치한 모듈 - 번역 대상 아님)"),
]


# ----------------------------------------------------------------- GUI
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    # 게임 폴더를 자동으로 못 찾았으면 폴더 선택 창을 띄우고, 고른 경로를 기억한 뒤 다시 시작한다.
    if not (GAME / "bin" / "win32" / "nwmain.exe").exists():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "게임 폴더 선택",
            "Neverwinter Nights 설치 폴더를 자동으로 찾지 못했습니다." + chr(10) +
            "nwmain.exe 가 들어 있는 게임 폴더(Neverwinter Nights)를 선택해 주세요.")
        chosen = filedialog.askdirectory(title="Neverwinter Nights 게임 폴더 선택")
        root.destroy()
        if chosen:
            p = Path(chosen)
            for cand in (p, p.parent.parent if p.name.lower() == "win32" else p):
                if (cand / "bin" / "win32" / "nwmain.exe").exists():
                    CACHE.mkdir(parents=True, exist_ok=True)
                    (CACHE / "game_dir.txt").write_text(str(cand), encoding="utf-8")
                    os.execv(sys.executable, [sys.executable] + sys.argv)   # 새 경로로 재시작
            r2 = tk.Tk()
            r2.withdraw()
            messagebox.showerror("경로 오류", "선택한 폴더에서 bin\\win32\\nwmain.exe 를 찾지 못했습니다.")
            r2.destroy()
        return

    try:
        ensure_assets()
    except Exception as e:  # noqa: BLE001
        print("리소스 자동 다운로드 실패:", e)

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("네버윈터 나이츠 EE 통합 한글 패치")
            self.geometry("880x700")
            self.minsize(740, 420)
            self.rows = {}

            head = ttk.Frame(self, padding=(10, 10, 10, 4))
            head.pack(fill="x")
            ttk.Label(head, text=f"게임 경로: {GAME}", foreground="#666").pack(anchor="w")
            ttk.Label(head, text=f"문서 경로: {DOCS}", foreground="#666").pack(anchor="w")

            bar = ttk.Frame(self, padding=10)
            bar.pack(side="bottom", fill="x")
            ttk.Button(bar, text="전체 일괄 패치", command=self.all_patch).pack(side="left", padx=4)
            ttk.Button(bar, text="전체 원복", command=self.all_restore).pack(side="left", padx=4)

            wrap = ttk.Frame(self)
            wrap.pack(fill="both", expand=True, padx=10)
            canvas = tk.Canvas(wrap, highlightthickness=0)
            vbar = ttk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=vbar.set)
            vbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            top = ttk.Frame(canvas)
            win = canvas.create_window((0, 0), window=top, anchor="nw")
            top.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
            self.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

            for ent in LAYOUT:
                if isinstance(ent, tuple):
                    ttk.Label(top, text=ent[1], font=("", 10, "bold")).pack(anchor="w", pady=(10, 2))
                    continue
                it = ITEMS[ent]
                r = ttk.Frame(top)
                r.pack(fill="x", pady=1)
                ttk.Label(r, text=it.name, width=36).pack(side="left", padx=(12, 0))
                lab = ttk.Label(r, width=8)
                lab.pack(side="left")
                b1 = ttk.Button(r, text="패치", width=6, command=lambda i=it: self.act(i, True))
                b1.pack(side="left", padx=2)
                b2 = ttk.Button(r, text="원복", width=6, command=lambda i=it: self.act(i, False))
                b2.pack(side="left", padx=2)
                ttk.Label(r, text=it.desc, foreground="#666").pack(side="left", padx=6)
                self.rows[it.id] = (lab, b1, b2)
            self.refresh()

        def refresh(self):
            for id_, (lab, b1, b2) in self.rows.items():
                it = ITEMS[id_]
                if not it.ready:
                    lab.config(text="미구현", foreground="#b00")
                    b1.state(["disabled"])
                    b2.state(["disabled"])
                else:
                    try:
                        on = it.applied()
                    except Exception:
                        on = False
                    lab.config(text="적용됨" if on else "미적용", foreground="#080" if on else "#333")

        def act(self, it, do_patch):
            try:
                (it.patch if do_patch else it.restore)()
            except PermissionError as e:
                messagebox.showerror("권한 오류", f"{e}\n게임을 종료하고 다시 시도하세요.")
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("오류", f"{it.name}\n\n{e}")
                return False
            self.refresh()
            return True

        def _each(self, patch):
            order = ["engine"] + [i for i in ITEMS if i != "engine"]
            for id_ in order:
                it = ITEMS[id_]
                if it.ready and not self.act(it, patch):
                    break

        def all_patch(self):
            self._each(True)

        def all_restore(self):
            self._each(False)

    App().mainloop()


def main():
    if "--list" in sys.argv:
        print("GAME:", GAME, "\nDOCS:", DOCS)
        for ent in LAYOUT:
            if isinstance(ent, tuple):
                print(f"[{ent[1]}]")
                continue
            it = ITEMS[ent]
            st = ("적용됨" if it.applied() else "미적용") if it.ready else "미구현"
            print(f"  {it.name:<40} {st}")
        return
    if "--patch-all" in sys.argv or "--restore-all" in sys.argv:
        patch = "--patch-all" in sys.argv
        if patch:
            ensure_assets()
        for id_ in ["engine"] + [i for i in ITEMS if i != "engine"]:
            it = ITEMS[id_]
            if not it.ready:
                continue
            try:
                if patch and isinstance(it, ExtModule) and not find_ext():
                    if not download_ext():
                        raise RuntimeError("확장 모듈 한글패치를 받지 못했습니다.")
                    _ext_cache.clear()
                (it.patch if patch else it.restore)()
                print("OK  ", it.name)
            except Exception as e:  # noqa: BLE001
                print("FAIL", it.name, "-", str(e).splitlines()[0])
        return
    run_gui()


if __name__ == "__main__":
    main()
