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
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import threading
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
try:
    VERSION = (HERE / "VERSION.txt").read_text(encoding="utf-8").strip() or "개발판"
except OSError:
    VERSION = "개발판"
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
    for up in (ROOT.parent, ROOT.parent.parent):   # 패치 폴더가 게임 폴더 옆/안에 있는 경우
        cands += [up / "Neverwinter Nights", up]
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
# 문서\development: 리소스 검색 경로의 최상단 (override 는 HAK/모듈/NWSync 같은 ERF 컨테이너보다 아래라서
# 모듈 안의 리소스를 덮지 못한다). 커뮤니티 캠페인 번역은 여기에 설치한다.
DEV = DOCS / "development"
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


def put_dev(data: bytes, dst: Path):
    # development 폴더는 원래 비어 있는 우리 전용 폴더다. 다른 캠페인 파일을 '백업(.orig)'으로 남기면 원복 때 오염되므로 백업 없이 쓴다.
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)


def unput_dev(dst: Path):
    for f in (dst, bak_of(dst)):               # 예전 버전이 남긴 .orig 도 함께 정리
        try:
            if f.exists():
                f.unlink()
        except OSError:
            pass


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
            ok = _ui_call(lambda: messagebox.askyesno("확장 모듈 한글패치 필요", msg))
        except Exception:
            pass
        if ok:
            z = download_ext()
            if z:
                _ext_cache["src"] = ExtSource(z)
                return _ext_cache["src"]
        try:
            from tkinter import filedialog
            f = _ui_call(lambda: filedialog.askopenfilename(
                title="nwn1ee_dod_kr.zip 파일을 직접 선택하세요 (취소하면 건너뜀)",
                filetypes=[("zip", "*.zip"), ("all", "*.*")]))
            if f:
                s = ExtSource(Path(f))
                if s.has(EXT_MARK):
                    (HERE / "external_patch.txt").write_text(f, encoding="utf-8")
                    _ext_cache["src"] = s
                    return s
        except Exception:
            pass
    return None


# GUI 가 작업 스레드에서 대화상자를 띄울 때 메인 스레드로 넘기는 훅 (CLI 에서는 그대로 호출)
_ui_call = lambda fn: fn()  # noqa: E731
_UI_DEFAULT = _ui_call                       # GUI 가 아니면(CLI/시험) 이 값 그대로 -> 대화상자를 띄우지 않는다


# ----------------------------------------------------------------- 항목 동작
class Item:
    na_text = "미구현"                      # ready 가 False 일 때 목록에 보이는 문구

    def __init__(self, id_, name, desc="", ready=False):
        self.id, self.name, self.desc, self.ready = id_, name, desc, ready

    def applied(self) -> bool:
        return False

    def patch(self):
        raise NotImplementedError

    def restore(self):
        raise NotImplementedError


class _Call:
    """일괄 작업용: 이름과 동작 하나만 가진 작업 항목."""

    def __init__(self, name, fn):
        self.name = name
        self.patch = self.restore = fn


class Todo(Item):
    def __init__(self, id_, name):
        super().__init__(id_, name, "", False)


class UnsupportedModule(Item):
    """게임이 내려받았지만 한글 번역이 아직 없는 커뮤니티 캠페인 (목록에 안내만 표시)."""
    na_text = "번역 없음"

    def __init__(self, id_, name):
        super().__init__(id_, name, "게임에서 내려받았지만 한글 번역이 아직 없습니다 (개발자에게 이름을 알려 주세요)", False)


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

    def _marker(self):
        return CACHE / f"built_{self.id}.json"

    def applied(self):
        b = bak_of(self.dst)
        mod_ok = self.dst.exists() and b.exists() and sha_file(self.dst) != sha_file(b)
        hak_ok = False
        try:                               # 번역된 HAK 가 실제로 설치되어 있어야 함
            haks = json.loads(self._marker().read_text(encoding="utf-8")).get("haks", [])
            hak_ok = bool(haks) and all(Path(h).exists() for h in haks)
        except Exception:
            pass
        return mod_ok or hak_ok

    def _stamp(self, src):
        """번역 입력(CSV·NCS·빌더 코드)과 원본 모듈 파일이 그대로면 같은 값 -> 다시 만들 필요 없음."""
        h = hashlib.sha256()
        files = [f for f in sorted((MODBUILD / "premium" / self.short).rglob("*")) if f.is_file()]
        files += sorted((MODBUILD / "premium").glob("*.py")) + sorted(MODBUILD.glob("*.py"))
        for f in files:
            h.update(f.name.encode("utf-8"))
            h.update(f.read_bytes())
        st = src.stat()
        h.update(f"{src.name}:{st.st_size}:{int(st.st_mtime)}".encode("utf-8"))
        return h.hexdigest()

    def patch(self):
        need_docs()
        src = bak_of(self.dst) if bak_of(self.dst).exists() else self.dst
        if not src.exists():
            raise RuntimeError(f"원본 모듈을 찾을 수 없습니다:\n{self.dst}")
        stamp = self._stamp(src)
        try:
            if self.applied() and json.loads(self._marker().read_text(encoding="utf-8")).get("stamp") == stamp:
                print("건너뜀(변경 없음):", self.name)
                return
        except Exception:
            pass
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            sub = "nwm" if self.nwm else "mod"
            (tmp / "base" / "data" / sub).mkdir(parents=True)
            shutil.copy2(src, tmp / "base" / "data" / sub / self.filename)
            env = dict(os.environ, NWN_BASE=str(tmp / "base"), NWN_BUILD_DIR=str(tmp / "out"),
                       NWN_HAK_DIR=str(GAME / "data" / "hk"), PYTHONIOENCODING="utf-8")
            r = subprocess.run(
                [sys.executable, str(MODBUILD / "premium" / "build_premium.py"), self.short],
                cwd=str(MODBUILD), env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
            outdir = tmp / "out" / self.short
            out = outdir / self.filename
            haks = sorted(outdir.glob("*.hak")) if outdir.exists() else []
            if r.returncode != 0 or not (out.exists() or haks):
                raise RuntimeError("모듈 빌드 실패:\n" + (r.stdout + r.stderr)[-800:])
            if out.exists():
                put_file(out, self.dst)
            placed = []
            for h in haks:                       # 번역된 HAK 는 문서 폴더의 hak 에 설치(게임 원본보다 우선)
                dst = HAK / h.name
                # 문서\hak 에는 원래 이 이름의 HAK 가 없다(우리가 만든 번역본뿐) -> 백업(.orig) 없이 덮어쓴다.
                # (.orig 를 만들면 다음 원복 때 순정이 아니라 이전 번역본이 되살아난다)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(h, dst)
                if bak_of(dst).exists():
                    bak_of(dst).unlink()
                placed.append(str(dst))
            CACHE.mkdir(parents=True, exist_ok=True)
            self._marker().write_text(json.dumps({"haks": placed, "stamp": stamp}, ensure_ascii=False), encoding="utf-8")

    def restore(self):
        unput(self.dst)
        try:
            for f in json.loads(self._marker().read_text(encoding="utf-8")).get("haks", []):
                unput_dev(Path(f))             # 번역 HAK 와 예전 .orig 를 함께 삭제
            self._marker().unlink()
        except Exception:
            pass


# ----------------------------------------------------------------- 커뮤니티 캠페인 (NWSync)
_GFF_EXT = {"dlg": 2029, "utc": 2027, "uti": 2025, "utp": 2044, "utd": 2042, "utm": 2051,
            "ute": 2040, "uts": 2035, "utt": 2032, "jrl": 2056, "are": 2012}


def _zstd_decompress():
    """zstd 해제 함수를 돌려준다 (Python 3.14 표준 / zstandard 패키지 / 자동 설치 순)."""
    try:
        from compression import zstd as _z          # Python 3.14+
        return lambda b: _z.decompress(b)
    except Exception:
        pass
    try:
        import zstandard as _zs
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q", "zstandard"], check=False)
        import importlib
        importlib.invalidate_caches()
        import zstandard as _zs
    d = _zs.ZstdDecompressor()
    return lambda b: d.decompress(b, max_output_size=64_000_000)


_progress = None            # GUI 가 설정: 현재 항목 안에서의 진행률(0~1)을 받는 함수


def report(frac):
    if _progress:
        try:
            _progress(max(0.0, min(1.0, frac)))
        except Exception:
            pass


class CommunityModule(Item):
    """NWSync 로 내려받은 커뮤니티 캠페인의 텍스트를 번역해 캠페인별 폴더에 보관하고, 플레이할 캠페인만 development 에 연결한다.

    게임이 내려받은 캐시(문서/nwsync)의 리소스 + translations.csv(한국어만) 로 번역본 GFF 를 만든다.
    같은 리소스 이름(module.ifo 등)을 여러 캠페인이 공유하고 게임은 development 폴더 하나만 읽으므로,
    번역본은 문서/ko_campaigns/<캠페인>/ 에 각각 만들어 두고 [패치]=그 캠페인으로 전환(다른 캠페인은 자동 해제)한다.
    """

    def __init__(self, id_, name, slug):
        super().__init__(id_, name, "내려받은 캠페인 번역 (자동 전환을 켜면 열 때 자동 적용 / 끄면 [패치]로 직접 연결)", True)
        self.slug = slug
        self.csv = HERE / "community" / slug / "translations.csv"
        self.ready = self.csv.exists()          # 번역 파일이 아직 없으면 "미구현"
        self.marker = CACHE / f"community_{id_}.json"

    def _nwsync(self):
        return Path(os.environ.get("NWN_NWSYNC_DIR") or (DOCS / "nwsync"))

    def lib(self):
        return DOCS / "ko_campaigns" / self.slug

    def built(self):
        return (self.lib() / "_complete.json").exists()

    def applied(self):
        try:
            m = json.loads(self.marker.read_text(encoding="utf-8"))
            files = m["files"]
            # v0.1.10 까지는 override 에 설치했으나 모듈 리소스를 덮지 못해 동작하지 않았다 -> 미적용으로 취급
            return m.get("dir") == "development" and bool(files) and Path(files[0]).exists()
        except Exception:
            return False

    def _inputs_stamp(self):
        h = hashlib.sha256()
        for f in (self.csv, HERE / "community" / self.slug / "ncs.csv"):
            if f.exists():
                h.update(f.read_bytes())
        return h.hexdigest()

    def prepare(self):
        """일괄 패치용: 게임에서 내려받은 캠페인이면 번역본을 미리 만들어 두고(활성화는 안 함), 아니면 조용히 건너뛴다."""
        self.build(skip_missing=True)

    def patch(self):
        need_docs()
        self.build()                              # 실패해도 지금 적용된 캠페인은 건드리지 않는다
        if autoswitch_enabled():
            # 자동 전환 사용 중: 번역본만 준비하고, 게임에서 캠페인을 열 때 version.dll 이 연결한다
            write_autoswitch_config(True)
            if _ui_call is not _UI_DEFAULT:
                from tkinter import messagebox as _mb
                _ui_call(lambda: _mb.showinfo("자동 전환 사용 중", f"'{self.name}' 번역본을 준비했습니다.\n\n자동 전환을 쓰는 중이라 [패치]로 직접 연결하지 않습니다. 게임에서 이 캠페인을 열면 자동으로 적용됩니다."))
            return
        others = [it for it in ITEMS.values() if isinstance(it, CommunityModule) and it is not self and it.applied()]
        for it in others:
            it.restore()
        if others:
            print("전환:", ", ".join(it.name for it in others), "->", self.name)
        self.restore()
        written = []
        for f in sorted(self.lib().iterdir()):
            if f.name == "_complete.json":                 # 내부 표식 파일만 제외 (게임 파일 중에도 '_' 로 시작하는 이름이 많다)
                continue
            dst = DEV / f.name
            put_dev(f.read_bytes(), dst)
            written.append(str(dst))
        CACHE.mkdir(parents=True, exist_ok=True)
        self.marker.write_text(json.dumps({"module": self.name, "dir": "development", "files": written}, ensure_ascii=False),
                               encoding="utf-8")

    def build(self, skip_missing=False):
        import csv
        import io
        import sqlite3
        if not self.csv.exists():
            raise RuntimeError("이 캠페인의 번역 파일이 아직 없습니다 (translations.csv).")
        nws = self._nwsync()
        mdb, ddb = nws / "nwsyncmeta.sqlite3", nws / "nwsyncdata_0.sqlite3"
        if not (mdb.exists() and ddb.exists()):
            if skip_missing:
                return False
            raise RuntimeError(
                "NWSync 캐시를 찾지 못했습니다.\n게임의 커뮤니티 탭에서 이 캠페인을 먼저 내려받으세요.\n" + str(nws))
        name = (HERE / "community" / self.slug / "NAME.txt").read_text(encoding="utf-8").strip()
        meta = sqlite3.connect(str(mdb))
        data = sqlite3.connect(str(ddb))
        row = meta.execute("select manifest_sha1 from manifest_metadata where module_name=?", (name,)).fetchone()
        if not row:
            if skip_missing:
                return False
            raise RuntimeError(f"'{name}' 캠페인이 내려받아져 있지 않습니다.\n게임의 커뮤니티 탭에서 먼저 내려받으세요.")
        manifest = row[0]
        stamp = {"manifest": manifest, "inputs": self._inputs_stamp()}
        try:
            if json.loads((self.lib() / "_complete.json").read_text(encoding="utf-8")).get("stamp") == stamp:
                return True                 # 이미 만들어 둔 번역본이 최신
        except Exception:
            pass
        out = self.lib().with_name(self.slug + ".tmp")
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        sys.path.insert(0, str(MODBUILD))
        from gff_tool import GffFile, CEXOLOCSTRING, STRUCT, LIST, CExoLocString  # noqa: E402
        decompress = _zstd_decompress()

        def set_text(st, path, lang, text):
            cur = st
            parts = path.split("/")
            for part in parts[:-1]:
                if part.isdigit():
                    i = int(part)
                    if isinstance(cur, list) and i < len(cur):
                        cur = cur[i]
                    else:
                        return False
                else:
                    if part not in cur:
                        return False
                    ft, val = cur.fields[part]
                    if ft not in (STRUCT, LIST):
                        return False
                    cur = val
            if parts[-1] not in cur:
                return False
            ft, val = cur.fields[parts[-1]]
            if ft != CEXOLOCSTRING or not isinstance(val, CExoLocString):
                return False
            val.set_text(text, lang)
            return True

        groups = {}
        with open(self.csv, "rb") as f:
            for r in csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))):
                groups.setdefault((r["Resource"], r["ResType"]), []).append((r["FieldPath"], int(r["LangID"]), r["Text"]))
        written = []
        for gi, ((resref, ext), items) in enumerate(groups.items()):
            report(0.7 * gi / max(1, len(groups)))
            rtype = _GFF_EXT.get(ext)
            if not rtype:
                continue
            q = meta.execute(
                "select resref_sha1 from manifest_resrefs where manifest_sha1=? and lower(resref)=? and restype=?",
                (manifest, resref, rtype)).fetchone()
            if not q:
                continue
            b = data.execute("select data from resrefs where sha1=?", (q[0],)).fetchone()
            if not b:
                continue
            blob = b[0]
            i = blob.find(b"\x28\xb5\x2f\xfd")
            try:
                gff = GffFile.from_bytes(decompress(blob[i:]))
            except Exception:
                continue
            n = sum(1 for p, lang, t in items if set_text(gff.root, p, lang, t))
            if n:
                dst = out / f"{resref}.{ext}"
                dst.write_bytes(gff.to_bytes())
                written.append(str(dst))
        # 컴파일된 스크립트(NCS) 안의 문장 (NPC 말풍선, 시스템 메시지): ncs.csv = Resource,Index,Check,Text
        ncs_csv = HERE / "community" / self.slug / "ncs.csv"
        if ncs_csv.exists():
            import zlib
            import ncs_tool  # noqa: E402
            ncs = {}
            with open(ncs_csv, "rb") as f:
                for r in csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))):
                    ncs.setdefault(r["Resource"].lower(), {})[int(r["Index"])] = (int(r["Check"]), r["Text"])
            for ni, (resref, items) in enumerate(ncs.items()):
                report(0.7 + 0.3 * ni / max(1, len(ncs)))
                q = meta.execute(
                    "select resref_sha1 from manifest_resrefs where manifest_sha1=? and lower(resref)=? and restype=2010",
                    (manifest, resref)).fetchone()
                b = data.execute("select data from resrefs where sha1=?", (q[0],)).fetchone() if q else None
                if not b:
                    continue
                blob = b[0]
                i = blob.find(b"\x28\xb5\x2f\xfd")
                try:
                    raw = decompress(blob[i:]) if i >= 0 else blob
                    idx = dict(ncs_tool.indexed_strings(raw))
                    repl = {k: t for k, (crc, t) in items.items()
                            if k in idx and zlib.crc32(idx[k].encode("latin-1")) == crc}
                    if repl:
                        dst = out / f"{resref}.ncs"
                        dst.write_bytes(ncs_tool.rebuild(raw, repl, by_index=True))
                        written.append(str(dst))
                except Exception:
                    continue
        report(1.0)
        if not written:
            shutil.rmtree(out, ignore_errors=True)
            if skip_missing:
                return False
            raise RuntimeError("적용된 리소스가 없습니다 (캠페인 버전이 다를 수 있습니다).")
        (out / "_complete.json").write_text(json.dumps({"stamp": stamp, "module": name, "files": len(written)}), encoding="utf-8")
        shutil.rmtree(self.lib(), ignore_errors=True)
        out.rename(self.lib())
        return True

    def restore(self):
        try:
            files = json.loads(self.marker.read_text(encoding="utf-8"))["files"]
        except Exception:
            return
        for f in files:
            unput_dev(Path(f))
        self.marker.unlink()

    def purge(self):
        """완전 원복: 적용 해제 + 캠페인별 번역본 폴더 삭제."""
        self.restore()
        shutil.rmtree(self.lib(), ignore_errors=True)


# ----------------------------------------------------------------- 자동 전환 (커뮤니티 캠페인, 선택)
AUTOSWITCH_CFG = BIN / "nwn_ko_autoswitch.txt"      # version.dll 이 게임 시작 때 읽는 설정 (hook/autoswitch.c 참고)
AUTOSWITCH_NOTICE = (
    "커뮤니티 캠페인 자동 전환(실험)을 켭니다.\n\n"
    "이 기능은 게임이 켜져 있는 동안 한글패치 version.dll 이 다음 일을 합니다.\n"
    " - 게임을 켤 때 문서\\development 폴더에 번역 파일 링크(약 2만 개, 복사가 아닌 하드링크)를 만듭니다.\n"
    " - 캠페인을 열면 그 캠페인의 번역만 남기고 나머지는 지웁니다. 공식 캠페인이면 전부 지웁니다.\n"
    " - 게임을 끄면 만든 파일을 모두 지웁니다. 비정상 종료로 남았다면 다음 실행 때 지웁니다.\n\n"
    "설치되는 파일\n"
    " - 이 기능은 [엔진·UI 한글 지원] 이 게임 폴더(Neverwinter Nights\\bin\\win32)에 설치하는 version.dll 안에 들어 있습니다.\n"
    "   원래 게임에는 이 파일이 없으며, 엔진을 [패치]하면 설치(교체)되고 [원복]하면 지워집니다. nwmain.exe 도 이미 한글 엔진 패치 대상입니다.\n"
    " - 이 기능의 설정 파일(nwn_ko_autoswitch.txt)이 같은 폴더에 만들어집니다.\n\n"
    "알아 둘 점\n"
    " - 게임을 켤 때 5~10초 늦게 시작될 수 있습니다.\n"
    " - 자동 전환 기능 자체는 nwmain.exe 와 캠페인 파일을 바꾸지 않고, development 폴더의 파일 링크만 만들고 지웁니다.\n"
    " - 지금 번역본이 없는 캠페인 20개의 번역본을 미리 만드느라 처음에는 10~20분이 걸릴 수 있습니다.\n"
    " - 끄려면 이 항목의 [원복]을 누르세요. 그러면 캠페인마다 [패치]를 눌러 쓰는 방식으로 돌아갑니다.\n\n"
    "계속할까요?")


def autoswitch_enabled() -> bool:
    try:
        return "enabled=1" in AUTOSWITCH_CFG.read_text(encoding="utf-8").split()
    except OSError:
        return False


def write_autoswitch_config(enabled=True) -> int:
    """설정 파일을 쓴다. 번역본이 만들어진 커뮤니티 캠페인만 포함. 반환: 포함한 캠페인 수"""
    import sqlite3
    nws = Path(os.environ.get("NWN_NWSYNC_DIR") or (DOCS / "nwsync"))
    db = nws / "nwsyncmeta.sqlite3"
    lines = [f"enabled={1 if enabled else 0}", f"dev={DEV}", f"lib={DOCS / 'ko_campaigns'}", f"logs={DOCS / 'logs'}"]
    n = 0
    if db.exists():
        meta = sqlite3.connect(str(db))
        for it in ITEMS.values():
            if isinstance(it, CommunityModule) and it.ready and it.built():
                name = (HERE / "community" / it.slug / "NAME.txt").read_text(encoding="utf-8").strip()
                row = meta.execute("select manifest_sha1 from manifest_metadata where module_name=?", (name,)).fetchone()
                if row:
                    lines.append(f"map\t{row[0]}\t{it.slug}")
                    n += 1
    AUTOSWITCH_CFG.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return n


def autoswitch_cleanup():
    """version.dll 이 깔아 둔 파일(상태 파일에 적힌 이름)을 development 에서 지운다 (비정상 종료 뒤 정리용)."""
    sp = DOCS / "ko_campaigns" / "_dll_seed.txt"
    n = 0
    try:
        for name in sp.read_text(encoding="utf-8").splitlines():
            name = name.strip()
            if name:
                try:
                    (DEV / name).unlink()
                    n += 1
                except OSError:
                    pass
        sp.unlink()
    except OSError:
        pass
    return n


def _game_running() -> bool:
    """nwmain.exe 가 실행 중인지 (실행 중에는 자동 전환이 링크를 직접 관리하므로 건드리지 않는다)."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq nwmain.exe"], capture_output=True, timeout=15).stdout
        return b"nwmain.exe" in out.lower()
    except Exception:  # noqa: BLE001
        return True   # 확인할 수 없으면 안전하게 건드리지 않는다


STALE_CLEANED = 0   # 이번 실행 시작 때 정리한 잔여 링크 수 (GUI 안내용)


def cleanup_stale_autoswitch_links() -> int:
    """자동 전환이 꺼져 있는데 development 에 예전 자동 전환 링크가 남아 있으면 지운다.

    자동 전환을 끄거나 게임이 비정상 종료돼 링크가 남으면(설정 파일이 없어 게임이 켜져도 정리하지 않음)
    같은 이름의 프리미엄 모듈 파일을 덮어써 "모듈 손상" 오류가 난다. 그래서 설치 프로그램을 켤 때마다 점검한다.
    안전장치: ① 자동 전환이 켜져 있으면 DLL 이 관리하므로 건드리지 않고, ② 게임이 실행 중이면 건드리지 않으며,
    ③ 상태 파일(_dll_seed.txt)에 적힌 이름 중 하드링크(링크 수 2 이상)인 것만 지운다(복사본은 지우지 않음).
    """
    sp = DOCS / "ko_campaigns" / "_dll_seed.txt"
    try:
        if autoswitch_enabled() or not sp.exists() or _game_running():
            return 0
        names = [x.strip() for x in sp.read_text(encoding="utf-8").splitlines() if x.strip()]
    except OSError:
        return 0
    n = 0
    for name in names:
        f = DEV / name
        try:
            if f.is_file() and os.stat(f).st_nlink > 1:
                f.unlink()
                n += 1
        except OSError:
            pass
    try:
        sp.unlink()
    except OSError:
        pass
    return n


class AutoSwitch(Item):
    """게임을 켜면 version.dll 이 캠페인을 열 때 그 캠페인의 번역을 자동으로 연결한다 (선택 기능, 사전 고지 후 켠다)."""

    def __init__(self):
        super().__init__("autoswitch", "자동 전환 (커뮤니티 캠페인, 실험)",
                         "캠페인을 열 때 번역을 자동 연결 - 켜기 전에 안내가 나옵니다", True)

    def applied(self):
        return autoswitch_enabled()

    def patch(self):
        need_docs()
        eng = ITEMS.get("engine")
        if eng is None or not eng.applied():
            raise RuntimeError("먼저 '엔진·UI 한글 지원'을 패치하세요 (자동 전환은 그 항목의 version.dll 안에 들어 있습니다).")
        if _ui_call is not _UI_DEFAULT:
            from tkinter import messagebox as _mb
            if not _ui_call(lambda: _mb.askyesno("자동 전환(실험) 사전 안내", AUTOSWITCH_NOTICE)):
                return
        for it in ITEMS.values():                   # 예전 방식(복사 연결)이 남아 있으면 해제
            if isinstance(it, CommunityModule) and it.applied():
                it.restore()
        global _progress
        outer = _progress
        items = [it for it in ITEMS.values() if isinstance(it, CommunityModule) and it.ready]
        for k, it in enumerate(items):
            _progress = (lambda f, k=k: outer((k + f) / len(items))) if outer else None
            try:
                it.prepare()
            except Exception as e:  # noqa: BLE001
                print("번역본 준비 건너뜀:", it.name, "-", e)
        _progress = outer
        n = write_autoswitch_config(True)
        if n == 0:
            AUTOSWITCH_CFG.unlink()
            raise RuntimeError("번역본이 준비된 캠페인이 없습니다. 게임의 커뮤니티 탭에서 캠페인을 먼저 내려받으세요.")

    def restore(self):
        try:
            AUTOSWITCH_CFG.unlink()
        except OSError:
            pass
        autoswitch_cleanup()


ITEMS = {i.id: i for i in [
    Engine(),
    AutoSwitch(),
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
    CommunityModule("c_hunt0", "A Hunt Through The Dark - 캐릭터 생성기", "AHTD_Character_Generator_1_0"),
    CommunityModule("c_hunt1", "A Hunt Through The Dark 1 - The Hunt Begins", "AHTD_1_The_Hunt_begins_4_1"),
    CommunityModule("c_hunt2", "A Hunt Through The Dark 2 - Into The Unknown", "AHTD_2_Into_The_Unknown_4_1"),
    CommunityModule("c_hunt3", "A Hunt Through The Dark 3 - Up to the Light", "AHTD_3_Up_to_the_Light_4_1"),
    CommunityModule("c_hunt4", "A Hunt Through The Dark 4 - Cormanthor", "AHTD_4_Cormanthor_4_1"),
    CommunityModule("c_hunt5", "A Hunt Through The Dark 5 - Acererak", "AHTD_5_Acererak_4_1"),
    CommunityModule("c_hunt6", "A Hunt Through The Dark 6 - Myth Drannor", "AHTD_6_Myth_Drannor_1_1"),
    CommunityModule("c_eotb", "Eye of the Beholder", "Eye_of_the_Beholder"),
    CommunityModule("c_eotb2", "Eye of the Beholder II: Legend of Darkmoon", "Eye_of_the_Beholder_II_Legend_of_Darkmoon"),
    CommunityModule("c_nature", "Nature Abhors a Vacuum", "Nature_Abhors_a_Vacuum"),
    CommunityModule("c_aielund1", "The Fall of Aielund Pt.1", "The_Fall_of_Aielund_Pt_1"),
    CommunityModule("c_aielund2", "The Fall of Aielund Pt.2", "The_Fall_of_Aielund_Pt_2"),
    CommunityModule("c_aielund", "The Fall of Aielund Pt.3", "The_Fall_of_Aielund_Pt_3"),
    CommunityModule("c_defender", "Defender of the Crown", "Defender_of_the_Crown"),
    CommunityModule("c_ironlord", "Return of the Ironlord", "Return_of_the_Ironlord"),
    CommunityModule("c_almraiven", "Almraiven", "Almraiven"),
    CommunityModule("c_shadewood", "Shadewood", "Shadewood"),

    CommunityModule("c_tethyr", "Crimson Tides of Tethyr", "Crimson_Tides_of_Tethyr_Enhanced_Edition"),
    CommunityModule("c_shadowdale", "Siege of Shadowdale", "Siege_of_Shadowdale_Enhanced_Edition"),
    CommunityModule("c_reptile", "Against the Cult of the Reptile God 2.0", "Against_the_Cult_of_the_Reptile_God_2_0"),
]}

def _community_ids():
    """커뮤니티 캠페인 id 를 이름의 알파벳순으로."""
    return [i.id for i in sorted((x for x in ITEMS.values() if isinstance(x, CommunityModule)),
                                 key=lambda x: x.name.lower())]


# 게임 캠페인 선택 화면 분류/순서
LAYOUT = [
    ("#", "공통 (필수)"), "engine",
    ("#", "선택 - 커뮤니티 캠페인 자동 전환 (실험, 켜기 전에 안내가 나옵니다)"), "autoswitch",
    ("#", "공식 - Classic Campaigns"), "oc", "sou", "hotu",
    ("#", "공식 - Extra Content"), "km", "sg", "ww", "coc", "darkranger", "eremor", "toheir", "chess",
    ("#", "프리미엄"), "doiwd", "totms", "dod", "ddf", "potsc", "wcoc", "id",
    ("#", "커뮤니티  (알파벳순 · 위의 [자동 전환]을 켜면 게임에서 캠페인을 열 때 자동으로 적용됩니다 · 끄면 [패치]로 한 번에 하나씩 연결 · [전체 일괄 패치]는 번역본만 미리 만들어 둠)"),
    *_community_ids(),
    ("#", "로컬  (직접 설치한 모듈 - 번역 대상 아님)"),
]


def detect_unsupported():
    """게임이 NWSync 로 내려받은 캠페인 중 이 설치 프로그램에 번역이 없는 것의 이름 목록."""
    db = Path(os.environ.get("NWN_NWSYNC_DIR") or (DOCS / "nwsync")) / "nwsyncmeta.sqlite3"
    if not db.exists():
        return []
    import sqlite3
    known = set()
    for it in ITEMS.values():
        if isinstance(it, CommunityModule):
            try:
                known.add((HERE / "community" / it.slug / "NAME.txt").read_text(encoding="utf-8").strip())
            except OSError:
                pass
    try:
        con = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
        names = [r[0] for r in con.execute("select module_name from manifest_metadata")]
        con.close()
    except Exception:
        return []
    return sorted({n for n in names if n and n not in known}, key=str.lower)


def register_unsupported():
    """번역이 없는 캠페인을 목록의 '번역 없음' 묶음에 추가한다 (GUI / --list 시작 시 한 번)."""
    names = detect_unsupported()
    if not names:
        return
    ids = []
    for n in names:
        i = "x_" + re.sub(r"[^A-Za-z0-9]+", "_", n)
        ITEMS[i] = UnsupportedModule(i, n)
        ids.append(i)
    pos = next(k for k, e in enumerate(LAYOUT) if isinstance(e, tuple) and e[1].startswith("로컬"))
    LAYOUT[pos:pos] = [("#", "커뮤니티 - 번역 없음 (내려받았지만 한글 패치가 없는 캠페인)")] + ids


# ----------------------------------------------------------------- GUI
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    if STALE_CLEANED:
        _r = tk.Tk()
        _r.withdraw()
        messagebox.showinfo("정리했습니다", f"자동 전환이 꺼져 있는데 예전에 만든 링크가 {STALE_CLEANED}개 남아 있어 지웠습니다."+chr(10)+"(남아 있으면 일부 프리미엄 캠페인이 '모듈 손상' 오류를 낼 수 있습니다.)")
        _r.destroy()

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

    register_unsupported()

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title(f"네버윈터 나이츠 EE 통합 한글 패치 {VERSION}")
            self.geometry("880x700")
            self.minsize(740, 420)
            self.rows = {}

            head = ttk.Frame(self, padding=(10, 10, 10, 4))
            head.pack(fill="x")
            ttk.Label(head, text=f"통합 한글패치 {VERSION}", font=("", 11, "bold")).pack(anchor="w")
            ttk.Label(head, text=f"게임 경로: {GAME}", foreground="#666").pack(anchor="w")
            ttk.Label(head, text=f"문서 경로: {DOCS}", foreground="#666").pack(anchor="w")

            bar = ttk.Frame(self, padding=10)
            bar.pack(side="bottom", fill="x")
            self.busy = False
            self.btn_all = ttk.Button(bar, text="전체 일괄 패치", command=self.all_patch)
            self.btn_all.pack(side="left", padx=4)
            self.btn_restore = ttk.Button(bar, text="전체 원복", command=self.all_restore)
            self.btn_restore.pack(side="left", padx=4)
            self.status = ttk.Label(bar, text="", foreground="#06c")
            self.status.pack(side="left", padx=10)
            self.prog = ttk.Progressbar(bar, mode="determinate", length=220, maximum=100)
            self.pct = ttk.Label(bar, text="", width=6)

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
            global _ui_call
            _ui_call = self._call_in_main
            self.refresh()
            self.after(1500, self._check_multi)

        # ---- 무거운 작업(패치/원복/상태 확인)은 작업 스레드에서 실행해 창이 '응답 없음'이 되지 않게 한다 ----
        def _call_in_main(self, fn):
            if threading.current_thread() is threading.main_thread():
                return fn()
            ev, box = threading.Event(), []

            def run():
                try:
                    box.append(fn())
                finally:
                    ev.set()
            self.after(0, run)
            ev.wait()
            return box[0] if box else None

        def _set_busy(self, text):
            self.busy = bool(text)
            st = "disabled" if text else "!disabled"
            for _id, (_lab, b1, b2) in self.rows.items():
                if ITEMS[_id].ready:
                    b1.state([st])
                    b2.state([st])
            for w in (self.btn_all, self.btn_restore):
                w.state([st])
            self.status.config(text=text)
            if text:
                self.prog["value"] = 0
                self.pct.config(text="0%")
                self.pct.pack(side="right")
                self.prog.pack(side="right", padx=6)
            else:
                self.prog.pack_forget()
                self.pct.pack_forget()

        def _set_prog(self, frac):
            self.prog["value"] = frac * 100
            self.pct.config(text=f"{int(frac * 100)}%")

        def refresh(self):
            """상태 확인도 디스크를 읽으므로 스레드에서 계산하고 결과만 메인에서 반영한다."""
            def work():
                res = {}
                for id_ in self.rows:
                    it = ITEMS[id_]
                    if not it.ready:
                        res[id_] = None
                        continue
                    try:
                        res[id_] = bool(it.applied())
                        if not res[id_] and isinstance(it, CommunityModule) and it.built():
                            res[id_] = "ready"
                    except Exception:
                        res[id_] = False
                self.after(0, lambda: self._apply_status(res))
            threading.Thread(target=work, daemon=True).start()

        def _check_multi(self):
            act = [it for it in ITEMS.values() if isinstance(it, CommunityModule) and it.applied()]
            if len(act) > 1 and messagebox.askyesno(
                    "커뮤니티 캠페인이 여러 개 적용돼 있습니다",
                    "커뮤니티 캠페인 " + str(len(act)) + "개가 동시에 적용돼 있습니다. 같은 이름의 파일이 겹쳐 게임이 멈추거나\n모듈이 손상될 수 있습니다.\n\n모두 원복하고, 플레이할 캠페인 하나만 다시 패치할까요?"""):
                self._run_jobs([(it, False) for it in act])

        def _apply_status(self, res):
            for id_, on in res.items():
                lab, b1, b2 = self.rows[id_]
                if on is None:
                    lab.config(text=ITEMS[id_].na_text, foreground="#b00")
                    b1.state(["disabled"])
                    b2.state(["disabled"])
                elif on == "ready":
                    lab.config(text="준비됨", foreground="#06c")
                else:
                    lab.config(text="적용됨" if on else "미적용", foreground="#080" if on else "#333")

        def _run_jobs(self, jobs):
            """jobs: [(item, do_patch)] 를 순서대로 작업 스레드에서 실행."""
            if self.busy:
                return

            def work():
                err = None
                global _progress
                for ji, (it, do_patch) in enumerate(jobs):
                    _progress = lambda f, ji=ji: self.after(0, lambda: self._set_prog((ji + f) / len(jobs)))
                    self.after(0, lambda ji=ji: self._set_prog(ji / len(jobs)))
                    self.after(0, lambda n=it.name, p=do_patch: self.status.config(
                        text=f"{'패치' if p else '원복'} 중: {n} … (잠시 걸릴 수 있습니다)"))
                    try:
                        (it.patch if do_patch else it.restore)()
                    except PermissionError as e:
                        err = ("권한 오류", f"{e}\n게임을 종료하고 다시 시도하세요.")
                        break
                    except Exception as e:  # noqa: BLE001
                        err = ("오류", f"{it.name}\n\n{e}")
                        break
                self.after(0, lambda: self._done(err))
            self._set_busy("작업 중 …")
            threading.Thread(target=work, daemon=True).start()

        def _done(self, err):
            self._set_busy("")
            if err:
                messagebox.showerror(*err)
            self.refresh()

        def act(self, it, do_patch):
            self._run_jobs([(it, do_patch)])

        def _each(self, patch):
            order = ["engine"] + [i for i in ITEMS if i != "engine"]
            # 커뮤니티 캠페인: 일괄 패치 = 번역본을 캠페인별 폴더에 미리 만들어 둠(전환은 각 [패치]), 일괄 원복 = 해제 + 폴더 삭제
            jobs = []
            for i in order:
                it = ITEMS[i]
                if not it.ready or (patch and isinstance(it, AutoSwitch)):
                    continue
                if isinstance(it, CommunityModule):
                    jobs.append((_Call(it.name + " (번역본 준비)", it.prepare) if patch else _Call(it.name, it.purge), patch))
                else:
                    jobs.append((it, patch))
            self._run_jobs([(it, True) if isinstance(it, _Call) else (it, p) for it, p in jobs])

        def all_patch(self):
            self._each(True)

        def all_restore(self):
            self._each(False)

    App().mainloop()


def main():
    global STALE_CLEANED
    STALE_CLEANED = cleanup_stale_autoswitch_links()
    if STALE_CLEANED:
        print(f"[정리] 남아 있던 자동 전환 링크 {STALE_CLEANED}개를 지웠습니다.")
    if "--list" in sys.argv:
        register_unsupported()
        print("GAME:", GAME, "\nDOCS:", DOCS)
        for ent in LAYOUT:
            if isinstance(ent, tuple):
                print(f"[{ent[1]}]")
                continue
            it = ITEMS[ent]
            st = ("적용됨" if it.applied() else ("준비됨" if isinstance(it, CommunityModule) and it.built() else "미적용")) if it.ready else it.na_text
            print(f"  {it.name:<40} {st}")
        return
    if "--restore-community" in sys.argv:
        for it in ITEMS.values():
            if isinstance(it, CommunityModule) and it.applied():
                it.restore()
                print("원복", it.name)
        return
    if "--patch-all" in sys.argv or "--restore-all" in sys.argv:
        patch = "--patch-all" in sys.argv
        if patch:
            ensure_assets()
        for id_ in ["engine"] + [i for i in ITEMS if i != "engine"]:
            it = ITEMS[id_]
            if not it.ready or (patch and isinstance(it, AutoSwitch)):
                continue
            try:
                if patch and isinstance(it, ExtModule) and not find_ext():
                    if not download_ext():
                        raise RuntimeError("확장 모듈 한글패치를 받지 못했습니다.")
                    _ext_cache.clear()
                if isinstance(it, CommunityModule):
                    (it.prepare if patch else it.purge)()
                else:
                    (it.patch if patch else it.restore)()
                print("OK  ", it.name)
            except Exception as e:  # noqa: BLE001
                print("FAIL", it.name, "-", str(e).splitlines()[0])
        return
    run_gui()


if __name__ == "__main__":
    main()
