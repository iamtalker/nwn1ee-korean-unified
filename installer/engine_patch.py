# -*- coding: utf-8 -*-
"""NWN:EE nwmain.exe 한글 지원 바이너리 패처 (8193.37 / 8193.36+ 해시 대상)

원본: wonilclone/nwn_ee_korean (MIT) 의 windows/scripts/install.py 에서
패치 로직만 분리하고, Nuklear UI 글리프 범위 패치를 적용하도록 수정한 것.
게임 파일을 재배포하지 않고, 사용자의 로컬 nwmain.exe 에 패치를 적용한다.
"""
import hashlib
import struct
from pathlib import Path
from typing import List, Optional, Tuple

# ============================================================================
# 원본 바이너리 해시 및 버전별 오프셋
# ============================================================================

# SHA256 해시 - 테스트된 nwmain.exe 버전들
KNOWN_HASHES = {
    # Steam Build 8193.36+ (2025)
    "3b7cb1252e0edb2ce22d7971f333aade027039ae30a45b4bc64732c3e6bec73a": "8193.36+",
}

# 버전별 오프셋 테이블 (모든 값은 파일 오프셋)
# Note: RVA가 아닌 파일 오프셋 사용 (RVA - 0xC00 = file offset for .text section)
VERSION_OFFSETS = {
    "8193.36+": {
        # Phase 1: 경계 체크
        "get_symbol_coords": 0x000eaf20,
        "set_symbol_coords": 0x000ed39f,
        "glyph_padding": 0x000fac80,
        "texture_hook": 0x000fabe7,
        "texture_cave": 0x002de94f,
        "textout": 0x0004be06,
        "textout_next": 0x0004be0b,       # -> mov edx, ebx (single byte path)
        "textout_next_korean": 0x0004be0d, # -> lea r9, ... (skip mov edx,ebx for Korean)
        "textout_cave": 0x01373210,  # .rodata 섹션 끝 여유 공간 (496 bytes)
        # Phase 5: CalculateVisibleStringLengthAndWidth CP949 디코더
        # 폭 계산 루프에서 1바이트씩 읽어 advance를 조회하므로
        # CP949 2바이트 문자가 반으로 쪼개져 폭이 과소 계산됨 → 중앙정렬 깨짐 + 문자 침범
        "calcwidth": 0x0004b640,           # movsxd rdx, ebx (루프 내 바이트 읽기 시작)
        "calcwidth_next": 0x0004b649,      # cmp dil, 0x3C (single byte path)
        "calcwidth_next_korean": 0x0004b717, # lea r9, [rsp+28h] (GetSymbolCoords 파라미터 설정)
        "calcwidth_cave": 0x01373260,      # .rodata cave (textout cave 직후)
        # 섹션별 file_offset → RVA 변환값 (상대 점프 계산용)
        "text_fo2rva": 0xC00,            # .text: RVA = file_offset + 0xC00
        "textout_cave_fo2rva": 0x2FB800, # .rodata: RVA = file_offset + 0x2FB800
        # .rodata PE 섹션 헤더 (code cave 실행 권한)
        "rodata_vsize_offset": 0x300,
        "rodata_chars_offset": 0x31C,
        # Nuklear glyph range (RVA -> file offset, 한글 글리프 로드)
        "nuklear_glyph_range": [
            (0xa70fe3, 0xa703e3, "Main font setup"),
            (0xa82fe8, 0xa823e8, "Secondary font"),
            (0xa8405c, 0xa8345c, "Font config init"),
            (0xa840b0, 0xa834b0, "Glyph range getter"),
        ],
        "korean_range_rva": 0xe8bd48,
    },
}

# 현재 사용할 오프셋 (설치 시 버전에 따라 설정됨)
CURRENT_OFFSETS = None

def calculate_sha256(filepath: Path) -> str:
    """파일의 SHA256 해시 계산"""
    sha256 = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()

def verify_binary(filepath: Path) -> Tuple[bool, str, Optional[str]]:
    """바이너리 해시 검증. (성공여부, 메시지, 버전) 반환"""
    if not filepath.exists():
        return False, "파일이 존재하지 않습니다", None

    file_hash = calculate_sha256(filepath)

    if file_hash in KNOWN_HASHES:
        version = KNOWN_HASHES[file_hash]
        return True, f"검증됨: {version}", version
    else:
        return False, f"알 수 없는 버전 (해시: {file_hash[:16]}...)", None


def set_offsets_for_version(version: str) -> bool:
    """버전에 맞는 오프셋 설정. 성공 시 True 반환"""
    global CURRENT_OFFSETS
    if version in VERSION_OFFSETS:
        CURRENT_OFFSETS = VERSION_OFFSETS[version]
        return True
    return False


def get_patches_for_version() -> List[dict]:
    """현재 버전에 맞는 패치 목록 반환"""
    if CURRENT_OFFSETS is None:
        raise RuntimeError("오프셋이 설정되지 않았습니다. set_offsets_for_version()을 먼저 호출하세요.")

    return [
        # Phase 1: 경계 체크 패치
        {
            'name': 'GetSymbolCoords boundary check',
            'offset': CURRENT_OFFSETS['get_symbol_coords'],
            'original': bytes([0x81, 0xfa, 0xff, 0x00, 0x00, 0x00]),  # cmp edx, 0xFF
            'patched': bytes([0x81, 0xfa, 0x35, 0x0a, 0x00, 0x00]),   # cmp edx, 0x0A35 (2613)
        },
        {
            'name': 'SetSymbolCoords boundary check',
            'offset': CURRENT_OFFSETS['set_symbol_coords'],
            'original': bytes([0x81, 0xfa, 0xff, 0x00, 0x00, 0x00]),  # cmp edx, 0xFF
            'patched': bytes([0x81, 0xfa, 0x35, 0x0a, 0x00, 0x00]),   # cmp edx, 0x0A35 (2613)
        },
        # Glyph Padding: 3 -> 48 (문자 침범 + 글리프 블리딩 해결, Android와 동일)
        # padding=48 -> 글리프당 24px 여백. 4096x4096 텍스처에 2606자 수용 가능.
        # 고배율 UI에서 인접 글리프 침범/블리딩 해소 (Android에서 검증된 값)
        {
            'name': 'Glyph padding 3 -> 48',
            'offset': CURRENT_OFFSETS['glyph_padding'],
            'original': bytes([0x48, 0xc7, 0x45, 0xbc, 0x03, 0x00, 0x00, 0x00]),
            'patched': bytes([0x48, 0xc7, 0x45, 0xbc, 0x30, 0x00, 0x00, 0x00]),
        },
    ]


# ============================================================================
# 패치 정의
# ============================================================================

# Note: 버전별 오프셋은 VERSION_OFFSETS에서 관리됨
# Nuklear UI: 글리프 범위 패치는 구현됨 (UTF-8 디코딩은 미구현)

# ============================================================================
# 패치 생성 함수
# ============================================================================

def generate_texture_patch():
    """4096x4096 텍스처 코드 생성"""
    if CURRENT_OFFSETS is None:
        raise RuntimeError("오프셋이 설정되지 않았습니다.")

    texture_hook = CURRENT_OFFSETS['texture_hook']
    texture_cave = CURRENT_OFFSETS['texture_cave']

    code = bytearray()
    code += bytes([0xbe, 0x00, 0x10, 0x00, 0x00])  # mov esi, 0x1000 (4096)
    code += bytes([0xbb, 0x00, 0x10, 0x00, 0x00])  # mov ebx, 0x1000 (4096)
    code += bytes([0x44, 0x8b, 0xeb])              # mov r13d, ebx
    code += bytes([0x44, 0x0f, 0xaf, 0xee])        # imul r13d, esi

    # jmp back (오프셋 기반 상대 점프 계산)
    jmp_back_offset = texture_hook + 7
    jmp_from_offset = texture_cave + len(code) + 5
    jmp_rel = jmp_back_offset - jmp_from_offset
    code += bytes([0xe9]) + struct.pack('<i', jmp_rel)

    return code


def generate_textout_patch():
    """CP949 2-byte lookahead 디코더 생성

    원본 코드 흐름:
        0x4CA06: movzx ebx, byte [r12]   ; hook point
        0x4CA0B: mov   edx, ebx          ; textout_next (edx = glyph for GetSymbolCoords)
        0x4CA0D: lea   r9, [rbp-0x71]    ; textout_next_korean (skip mov edx,ebx)
        ...
        0x4CA19: call  GetSymbolCoords
        0x4CA1E: cmp   bl, 0x3c          ; '<' 색상코드 체크

    버그 수정 (v2): 한글 글리프 인덱스(256+)의 하위 8비트가 0x3C('<')와
    일치하면 색상코드 파서로 잘못 진입하여 크래시 발생.
    한글 경로에서는 edx에 직접 글리프를 넣고 ebx=0으로 설정하여
    cmp bl, 0x3c를 안전하게 통과시킴.
    """
    if CURRENT_OFFSETS is None:
        raise RuntimeError("오프셋이 설정되지 않았습니다.")

    textout_cave = CURRENT_OFFSETS['textout_cave']
    textout_next = CURRENT_OFFSETS['textout_next']
    textout_next_korean = CURRENT_OFFSETS['textout_next_korean']

    # 섹션 간 상대 점프를 위한 RVA 변환 (.text ↔ .rodata)
    text_fo2rva = CURRENT_OFFSETS['text_fo2rva']
    cave_fo2rva = CURRENT_OFFSETS['textout_cave_fo2rva']
    cave_rva = textout_cave + cave_fo2rva
    textout_next_rva = textout_next + text_fo2rva
    textout_next_korean_rva = textout_next_korean + text_fo2rva

    code = bytearray()

    # 1. Original instruction: movzx ebx, byte [r12]
    code += bytes([0x41, 0x0f, 0xb6, 0x1c, 0x24])  # 5 bytes

    # 2. Check if current byte is lead (0xB0-0xC8)
    code += bytes([0x80, 0xfb, 0xb0])  # cmp bl, 0xB0
    jb_exit = len(code)
    code += bytes([0x72, 0x00])  # jb .exit (not a lead)

    code += bytes([0x80, 0xfb, 0xc8])  # cmp bl, 0xC8
    ja_exit = len(code)
    code += bytes([0x77, 0x00])  # ja .exit (not a lead)

    # 3. Lead byte confirmed. Read next byte into eax
    code += bytes([0x41, 0x0f, 0xb6, 0x44, 0x24, 0x01])  # movzx eax, byte [r12+1]

    # 4. Check if next byte is trail (0xA1-0xFE)
    code += bytes([0x3c, 0xa1])  # cmp al, 0xA1
    jb_exit2 = len(code)
    code += bytes([0x72, 0x00])  # jb .exit (not a valid trail)

    code += bytes([0x3c, 0xfe])  # cmp al, 0xFE
    ja_exit2 = len(code)
    code += bytes([0x77, 0x00])  # ja .exit (not a valid trail)

    # 5. Valid CP949 pair! Calculate glyph index
    # Formula: 256 + (lead - 0xB0) * 94 + (trail - 0xA1)

    # Save trail to ecx
    code += bytes([0x89, 0xc1])  # mov ecx, eax (trail)

    # ebx = lead - 0xB0
    code += bytes([0x81, 0xeb, 0xb0, 0x00, 0x00, 0x00])  # sub ebx, 0xB0

    # ebx = (lead - 0xB0) * 94
    code += bytes([0x6b, 0xdb, 0x5e])  # imul ebx, ebx, 94

    # ecx = trail - 0xA1
    code += bytes([0x81, 0xe9, 0xa1, 0x00, 0x00, 0x00])  # sub ecx, 0xA1

    # ebx = (lead - 0xB0) * 94 + (trail - 0xA1)
    code += bytes([0x01, 0xcb])  # add ebx, ecx

    # ebx = 256 + result (glyph index)
    code += bytes([0x81, 0xc3, 0x00, 0x01, 0x00, 0x00])  # add ebx, 256

    # 6. Korean path: set edx = glyph, ebx = 0 (safe for cmp bl, 0x3c)
    code += bytes([0x8b, 0xd3])  # mov edx, ebx (edx = glyph index)
    code += bytes([0x31, 0xdb])  # xor ebx, ebx (ebx = 0, bl != 0x3c)

    # 7. Increment edi to skip the trail byte
    code += bytes([0xff, 0xc7])  # inc edi

    # 8. Korean exit: jump past 'mov edx, ebx' to lea r9, ... (RVA 기반)
    korean_exit_offset = len(code)
    jmp_from_rva = cave_rva + len(code) + 5
    jmp_rel = textout_next_korean_rva - jmp_from_rva
    code += bytes([0xe9])
    code += struct.pack('<i', jmp_rel)

    # 9. Single-byte exit: jump to 'mov edx, ebx' (original flow, RVA 기반)
    exit_offset = len(code)
    jmp_from_rva = cave_rva + len(code) + 5
    jmp_rel = textout_next_rva - jmp_from_rva
    code += bytes([0xe9])
    code += struct.pack('<i', jmp_rel)

    # Patch conditional jump offsets (all jump to single-byte exit)
    code[jb_exit + 1] = (exit_offset - (jb_exit + 2)) & 0xFF
    code[ja_exit + 1] = (exit_offset - (ja_exit + 2)) & 0xFF
    code[jb_exit2 + 1] = (exit_offset - (jb_exit2 + 2)) & 0xFF
    code[ja_exit2 + 1] = (exit_offset - (ja_exit2 + 2)) & 0xFF

    return code


def generate_calcwidth_patch():
    """CalculateVisibleStringLengthAndWidth CP949 2-byte 디코더 생성

    원본 코드 흐름 (RVA):
        0x4C240: movsxd rdx, ebx          ; 루프 인덱스 확장
        0x4C243: add    rdx, r12           ; 문자열 base + index
        0x4C246: movzx  edi, byte [rdx]    ; ← 1바이트만 읽음 (문제의 원인)
        0x4C249: cmp    dil, 0x3C          ; '<' 색상코드 체크
        ...
        0x4C313: movzx  edx, dil           ; ← 하위 8비트만 GetSymbolCoords에 전달
        0x4C317: lea    r9, [rsp+28h]      ; GetSymbolCoords 파라미터 설정 시작
        ...
        0x4C343: call   GetSymbolCoords

    한글 경로: CP949 디코딩 후 edx에 글리프 인덱스를 직접 넣고
    movzx edx, dil (8비트 절삭)과 문자 타입 체크를 건너뛰어
    GetSymbolCoords 파라미터 설정(0x4C317)으로 직행.
    edi=0으로 설정하여 후속 newline/space 체크 안전 통과.
    """
    if CURRENT_OFFSETS is None:
        raise RuntimeError("오프셋이 설정되지 않았습니다.")

    calcwidth_cave = CURRENT_OFFSETS['calcwidth_cave']
    calcwidth_next = CURRENT_OFFSETS['calcwidth_next']
    calcwidth_next_korean = CURRENT_OFFSETS['calcwidth_next_korean']

    # 섹션 간 상대 점프를 위한 RVA 변환
    text_fo2rva = CURRENT_OFFSETS['text_fo2rva']
    cave_fo2rva = CURRENT_OFFSETS['textout_cave_fo2rva']  # 같은 .rodata 섹션
    cave_rva = calcwidth_cave + cave_fo2rva
    calcwidth_next_rva = calcwidth_next + text_fo2rva
    calcwidth_next_korean_rva = calcwidth_next_korean + text_fo2rva

    code = bytearray()

    # 1. Replaced instructions
    code += bytes([0x48, 0x63, 0xd3])              # movsxd rdx, ebx
    code += bytes([0x49, 0x03, 0xd4])              # add rdx, r12
    code += bytes([0x0f, 0xb6, 0x3a])              # movzx edi, byte [rdx]

    # 2. Check if lead byte (0xB0-0xC8)
    code += bytes([0x40, 0x80, 0xff, 0xb0])        # cmp dil, 0xB0
    jb_exit = len(code)
    code += bytes([0x72, 0x00])                     # jb .not_korean

    code += bytes([0x40, 0x80, 0xff, 0xc8])        # cmp dil, 0xC8
    ja_exit = len(code)
    code += bytes([0x77, 0x00])                     # ja .not_korean

    # 3. Read trail byte
    code += bytes([0x0f, 0xb6, 0x42, 0x01])        # movzx eax, byte [rdx+1]

    # 4. Check trail byte (0xA1-0xFE)
    code += bytes([0x3c, 0xa1])                     # cmp al, 0xA1
    jb_exit2 = len(code)
    code += bytes([0x72, 0x00])                     # jb .not_korean

    code += bytes([0x3c, 0xfe])                     # cmp al, 0xFE
    ja_exit2 = len(code)
    code += bytes([0x77, 0x00])                     # ja .not_korean

    # 5. Compute glyph index: 256 + (lead - 0xB0) * 94 + (trail - 0xA1)
    code += bytes([0x89, 0xc1])                     # mov ecx, eax (save trail)
    code += bytes([0x81, 0xef, 0xb0, 0x00, 0x00, 0x00])  # sub edi, 0xB0
    code += bytes([0x6b, 0xff, 0x5e])               # imul edi, edi, 94
    code += bytes([0x81, 0xe9, 0xa1, 0x00, 0x00, 0x00])  # sub ecx, 0xA1
    code += bytes([0x01, 0xcf])                     # add edi, ecx
    code += bytes([0x81, 0xc7, 0x00, 0x01, 0x00, 0x00])  # add edi, 256

    # 6. Korean path: edx=glyph, rcx=font, edi=0(safe), inc ebx
    code += bytes([0x8b, 0xd7])                     # mov edx, edi
    code += bytes([0x48, 0x8b, 0x4d, 0x28])         # mov rcx, [rbp+28h]
    code += bytes([0x31, 0xff])                     # xor edi, edi
    code += bytes([0xff, 0xc3])                     # inc ebx

    # 7. Korean exit: jump to lea r9, [rsp+28h] (GetSymbolCoords 파라미터 설정)
    jmp_from_rva = cave_rva + len(code) + 5
    jmp_rel = calcwidth_next_korean_rva - jmp_from_rva
    code += bytes([0xe9])
    code += struct.pack('<i', jmp_rel)

    # 8. Non-Korean exit: jump back to cmp dil, 0x3C
    exit_offset = len(code)
    jmp_from_rva = cave_rva + len(code) + 5
    jmp_rel = calcwidth_next_rva - jmp_from_rva
    code += bytes([0xe9])
    code += struct.pack('<i', jmp_rel)

    # Patch conditional jump offsets
    code[jb_exit + 1] = (exit_offset - (jb_exit + 2)) & 0xFF
    code[ja_exit + 1] = (exit_offset - (ja_exit + 2)) & 0xFF
    code[jb_exit2 + 1] = (exit_offset - (jb_exit2 + 2)) & 0xFF
    code[ja_exit2 + 1] = (exit_offset - (ja_exit2 + 2)) & 0xFF

    return code


def apply_nuklear_glyph_range_patch(data: bytearray) -> int:
    """Nuklear UI: 한글 글리프 범위 패치

    Nuklear UI (모듈 선택, 설정 등)에서 한글 글리프를 로드하도록 패치.

    Windows 바이너리에는 두 가지 glyph range가 정의되어 있음:
    - ASCII only (0x20-0xFF): RVA 0xe8bce0
    - Korean (0x20-0xFF, 0x3131-0x3163, 0xAC00-0xD79D): RVA 0xe8bd48

    기본적으로 ASCII only range를 사용하는 4개 위치를 Korean range로 변경.

    Returns: 패치 적용된 개수
    """
    if CURRENT_OFFSETS is None:
        raise RuntimeError("오프셋이 설정되지 않았습니다.")

    patches = CURRENT_OFFSETS['nuklear_glyph_range']
    korean_range_rva = CURRENT_OFFSETS['korean_range_rva']
    patched_count = 0

    for rva, file_offset, desc in patches:
        # 원본 바이트 검증 (lea reg, [rip+disp])
        original = bytes(data[file_offset:file_offset+7])

        # 처음 2바이트는 lea 명령어 prefix (0x48 0x8d)
        if original[0:2] != bytes([0x48, 0x8d]):
            print(f"  [!] {desc}: 예상치 못한 opcode, 건너뜀")
            continue

        # 새 displacement 계산: korean_range_rva - (rva + 7)
        new_disp = korean_range_rva - (rva + 7)
        new_bytes = original[0:3] + struct.pack('<i', new_disp)

        data[file_offset:file_offset+7] = new_bytes
        print(f"  [OK] {desc}")
        patched_count += 1

    return patched_count



# ============================================================================
# 공개 API
# ============================================================================

def patch_bytes(data: bytes):
    """원본 nwmain.exe 바이트를 받아 패치된 바이트와 로그 목록을 반환한다.

    지원하지 않는 빌드이면 ValueError.
    """
    log = []
    h = hashlib.sha256(data).hexdigest()
    if h not in KNOWN_HASHES:
        raise ValueError("지원하지 않는 nwmain.exe 빌드입니다 (sha256 %s...)" % h[:16])
    set_offsets_for_version(KNOWN_HASHES[h])
    buf = bytearray(data)

    for patch in get_patches_for_version():
        off = patch['offset']
        n = len(patch['original'])
        cur = bytes(buf[off:off + n])
        if cur == patch['original']:
            buf[off:off + n] = patch['patched']
            log.append("OK  " + patch['name'])
        elif cur == patch['patched']:
            log.append("이미 적용됨 " + patch['name'])
        else:
            raise ValueError("패치 위치 값이 예상과 다릅니다: " + patch['name'])

    # 텍스처 4096x4096
    tex_hook = CURRENT_OFFSETS['texture_hook']
    tex_cave = CURRENT_OFFSETS['texture_cave']
    code = generate_texture_patch()
    buf[tex_cave:tex_cave + len(code)] = code
    buf[tex_hook:tex_hook + 7] = bytes([0xe9]) + struct.pack('<i', tex_cave - (tex_hook + 5)) + bytes([0x90, 0x90])
    log.append("OK  Texture 4096x4096")

    # .rodata 섹션 헤더 (실행 권한)
    vs_off = CURRENT_OFFSETS['rodata_vsize_offset']
    ch_off = CURRENT_OFFSETS['rodata_chars_offset']
    vs = struct.unpack('<I', buf[vs_off:vs_off + 4])[0]
    if vs == 0x00000A10:
        buf[vs_off:vs_off + 4] = struct.pack('<I', 0x00000C00)
    ch = struct.unpack('<I', buf[ch_off:ch_off + 4])[0]
    if ch == 0x40000040:
        buf[ch_off:ch_off + 4] = struct.pack('<I', 0x60000060)
    log.append("OK  .rodata 실행 권한")

    text_fo2rva = CURRENT_OFFSETS['text_fo2rva']
    cave_fo2rva = CURRENT_OFFSETS['textout_cave_fo2rva']

    # TextOut CP949 디코더
    to_off = CURRENT_OFFSETS['textout']
    to_cave = CURRENT_OFFSETS['textout_cave']
    code = generate_textout_patch()
    buf[to_cave:to_cave + len(code)] = code
    jmp = (to_cave + cave_fo2rva) - ((to_off + text_fo2rva) + 5)
    buf[to_off:to_off + 5] = bytes([0xe9]) + struct.pack('<i', jmp)
    log.append("OK  CP949 TextOut")

    # CalcWidth CP949 디코더
    cw_off = CURRENT_OFFSETS['calcwidth']
    cw_cave = CURRENT_OFFSETS['calcwidth_cave']
    code = generate_calcwidth_patch()
    buf[cw_cave:cw_cave + len(code)] = code
    jmp = (cw_cave + cave_fo2rva) - ((cw_off + text_fo2rva) + 5)
    buf[cw_off:cw_off + 9] = bytes([0xe9]) + struct.pack('<i', jmp) + bytes([0x90] * 4)
    log.append("OK  CP949 CalcWidth")

    # Nuklear UI 한글 글리프 범위
    n = apply_nuklear_glyph_range_patch(buf)
    log.append("OK  Nuklear 글리프 범위 (%d/4)" % n)
    if n != 4:
        raise ValueError("Nuklear 글리프 범위 패치가 일부만 적용되었습니다")

    return bytes(buf), log


ORIGINAL_SHA256 = "3b7cb1252e0edb2ce22d7971f333aade027039ae30a45b4bc64732c3e6bec73a"
