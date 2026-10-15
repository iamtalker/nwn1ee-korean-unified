# -*- coding: utf-8 -*-
"""build_premium.py 에 HAK 번역 단계를 추가한다 (모듈에 없는 리소스는 config["hak"] 의 HAK 에서 찾아 교체)."""
import os, sys

p = sys.argv[1]
s = open(p, "rb").read().decode("utf-8")

# 1) 모듈에서 못 찾은 리소스를 따로 모은다
a = """        location = resource_index.get((resref, res_ext))
        if location is None:
            # HAK에 있을 수 있으므로 경고만
            print(f"    Note: {resref}.{res_ext} not in module (may be in HAK)")
            failed += len(trans_list)
            continue
"""
b = """        location = resource_index.get((resref, res_ext))
        if location is None:
            missing_in_module[(resref, res_ext)] = trans_list   # HAK 단계에서 처리
            continue
"""
assert a in s
s = s.replace(a, b, 1)

a = """    modified_resources = {}  # (resref, erf_type_id) → modified bytes
    applied = 0
    failed = 0
"""
b = """    modified_resources = {}  # (resref, erf_type_id) → modified bytes
    missing_in_module = {}   # 모듈에 없는 (resref, ext) → 번역 목록 (HAK 에서 찾는다)
    applied = 0
    failed = 0
"""
assert a in s
s = s.replace(a, b, 1)

# 2) 결과 처리부를 HAK 단계 포함으로 교체
a = s[s.index('    print(f"  Applied: {applied} translations to {len(modified_resources)} resources")'):
      s.index("def build_module(module_name: str, release: bool = False):")]
b = '''    print(f"  Applied (module): {applied} translations to {len(modified_resources)} resources")

    # ---- HAK 단계: 모듈에 없던 리소스는 연결된 HAK 에서 찾아 번역본 HAK 를 만든다 ----
    hak_outputs = []
    remaining = dict(missing_in_module)
    for hak_name in config.get("hak", []) or []:
        if not remaining:
            break
        hak_path = HAK_DIR / f"{hak_name}.hak"
        if not hak_path.exists():
            print(f"  HAK not found: {hak_path}")
            continue
        h_type, h_ver, h_entries = read_erf_entries(hak_path)
        if h_type is None:
            continue
        h_index = build_gff_resource_index(hak_path, h_entries)
        h_modified = {}
        h_applied = 0
        for (resref, res_ext), trans_list in list(remaining.items()):
            loc = h_index.get((resref, res_ext))
            if loc is None:
                continue
            erf_type_id, off, size = loc
            try:
                g = GffFile.from_bytes(read_resource_data(hak_path, off, size))
            except Exception:
                continue
            n = 0
            for field_path, lang_id, text in trans_list:
                if set_locstring_in_struct(g.root, field_path, lang_id, text):
                    n += 1
            if n:
                h_modified[(resref, erf_type_id)] = g.to_bytes()
                h_applied += n
            del remaining[(resref, res_ext)]
        print(f"  Applied (hak {hak_name}): {h_applied} translations to {len(h_modified)} resources")
        if h_modified:
            out_hak = output_dir / f"{hak_name}.hak"
            repack_erf(hak_path, out_hak, h_modified)
            hak_outputs.append(out_hak)

    failed += sum(len(v) for v in remaining.values())
    if failed > 0:
        print(f"  Skipped: {failed} (not found in module or HAK, or failed)")

    output_path = None
    if modified_resources:
        # 모듈 재패킹 (mod_output이 있으면 출력 파일명 변경)
        output_name = config.get("mod_output", module_path.name)
        output_path = output_dir / output_name
        repack_erf(module_path, output_path, modified_resources)

    return output_path


'''
s = s.replace(a, b, 1)
open(p, "wb").write(s.encode("utf-8"))
print("patched")
