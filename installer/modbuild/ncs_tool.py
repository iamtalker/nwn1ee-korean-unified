# -*- coding: utf-8 -*-
"""NCS(컴파일된 NWScript) 문자열 상수 추출/치환.

NCS: 'NCS V1.0' + 0x42 + 총길이(BE u32) + 명령열. 문자열은 CONSTS(0x04, type 0x05, u16 길이, 바이트)로 박혀 있고,
점프(JMP/JSR/JZ/JNZ)·STORE_STATE 는 상대 오프셋을 쓰므로 문자열 길이가 바뀌면 오프셋을 다시 계산해야 한다.
"""
import struct

HEADER = b"NCS V1.0"

# opcode -> 고정 크기(타입 바이트 포함). CONST/EQUAL/NEQ 는 타입에 따라 별도 처리.
_FIXED = {
    0x01: 8, 0x02: 2, 0x03: 8, 0x05: 5,
    0x06: 2, 0x07: 2, 0x08: 2, 0x09: 2, 0x0A: 2,
    0x0D: 2, 0x0E: 2, 0x0F: 2, 0x10: 2, 0x11: 2, 0x12: 2, 0x13: 2,
    0x14: 2, 0x15: 2, 0x16: 2, 0x17: 2, 0x18: 2, 0x19: 2, 0x1A: 2,
    0x1B: 6, 0x1C: 2, 0x1D: 6, 0x1E: 6, 0x1F: 6, 0x20: 2, 0x21: 8, 0x22: 2,
    0x23: 6, 0x24: 6, 0x25: 6, 0x26: 8, 0x27: 8, 0x28: 6, 0x29: 6,
    0x2A: 2, 0x2B: 2, 0x2C: 10, 0x2D: 2,
}
_REL = {0x1D, 0x1E, 0x1F, 0x25}      # JMP, JSR, JZ, JNZ : 4바이트 상대 오프셋 (명령 시작 기준)


class NcsError(Exception):
    pass


def parse(data: bytes):
    """-> [(offset, kind, payload)]  kind: 'str' | 'rel' | 'raw'.
    rel payload = (opcode, type, 상대오프셋) / str payload = bytes / raw payload = 원본 바이트."""
    if data[:8] != HEADER or data[8] != 0x42:
        raise NcsError("not NCS")
    total = struct.unpack(">I", data[9:13])[0]
    if total != len(data):
        raise NcsError("size mismatch")
    out = []
    p = 13
    while p < len(data):
        op = data[p]
        if op == 0x04:                       # CONST
            t = data[p + 1]
            if t == 0x05:
                n = struct.unpack(">H", data[p + 2:p + 4])[0]
                out.append((p, "str", data[p + 4:p + 4 + n]))
                p += 4 + n
                continue
            size = 6
        elif op in (0x0B, 0x0C):              # EQUAL / NEQ
            size = 4 if data[p + 1] == 0x24 else 2
        elif op in _FIXED:
            size = _FIXED[op]
        else:
            raise NcsError(f"unknown opcode {op:#x} at {p}")
        if p + size > len(data):
            raise NcsError("truncated")
        if op in _REL:
            out.append((p, "rel", (op, data[p + 1], struct.unpack(">i", data[p + 2:p + 6])[0])))
        else:
            out.append((p, "raw", data[p:p + size]))
        p += size
    if p != len(data):
        raise NcsError("trailing bytes")
    return out


def strings(data: bytes):
    return [pl.decode("latin-1") for _o, k, pl in parse(data) if k == "str"]


def rebuild(data: bytes, mapping: dict, encoding: str = "cp949", by_index: bool = False) -> bytes:
    """mapping: {원문(latin-1 디코드 문자열): 번역문} 또는 by_index=True 이면 {문자열 순번: 번역문}.
    반환: 치환·오프셋 보정된 NCS."""
    ins = parse(data)
    sidx = -1
    # 1) 새 바이트열 길이 계산 -> 구 오프셋 -> 신 오프셋 지도
    new_bytes = []
    for _o, k, pl in ins:
        if k == "str":
            sidx += 1
            key = sidx if by_index else pl.decode("latin-1")
            if key in mapping:
                try:
                    b = mapping[key].encode(encoding)
                except UnicodeEncodeError:
                    b = pl
                if len(b) > 0xFFFF:
                    b = pl
                pl = b
            new_bytes.append(b"\x04\x05" + struct.pack(">H", len(pl)) + pl)
        elif k == "rel":
            new_bytes.append(None)      # 크기 6 고정, 나중에 채움
        else:
            new_bytes.append(pl)
    newpos, cur = {}, 13
    for (o, k, _pl), nb in zip(ins, new_bytes):
        newpos[o] = cur
        cur += 6 if k == "rel" else len(nb)
    end_old = len(data)
    newpos[end_old] = cur
    out = bytearray()
    for (o, k, pl), nb in zip(ins, new_bytes):
        if k == "rel":
            op, t, rel = pl
            tgt_old = o + rel
            if tgt_old not in newpos:
                raise NcsError(f"jump into the middle of an instruction at {o}")
            out += bytes([op, t]) + struct.pack(">i", newpos[tgt_old] - newpos[o])
        else:
            out += nb
    return HEADER + b"\x42" + struct.pack(">I", 13 + len(out)) + bytes(out)


def is_sentence(s: str) -> bool:
    """사람이 읽는 문장처럼 보이는 문자열인가 (디버그 문구/태그/함수 인자 제외)."""
    import re
    if " " not in s or "_" in s or s.startswith(("***", "os_", "#")):
        return False
    if not re.search(r"[A-Za-z]{3,}", s):
        return False
    w = s.split()
    return len(w) >= 3 or bool(re.search(r"[.!?\"']$", s))


def indexed_strings(data: bytes):
    """-> [(순번, latin-1 문자열)] (문장처럼 보이는 것만)."""
    out, i = [], -1
    for _o, k, pl in parse(data):
        if k == "str":
            i += 1
            t = pl.decode("latin-1")
            if is_sentence(t):
                out.append((i, t))
    return out
