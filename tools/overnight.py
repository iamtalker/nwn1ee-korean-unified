# -*- coding: utf-8 -*-
"""남은 모듈을 순서대로 기계번역 -> 깨진 항목 재번역 -> 전역 용어 교정 적용. 낮은 우선순위/적은 스레드로 실행."""
import os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
env = dict(os.environ, PYTHONIOENCODING="utf-8", NWN_MT_THREADS="6")
LOW = 0  # 일반 우선순위(출근 중이라 팬 소음 무관)
ORDER = ["witchswake", "shadowguard", "kingmaker", "id", "wcoc"]
def run(args, log):
    with open(log, "a", encoding="utf-8") as f:
        return subprocess.run([sys.executable] + args, env=env, stdout=f, stderr=subprocess.STDOUT, creationflags=LOW).returncode
for m in ORDER:
    t = time.time()
    out = f"{m}_all.json"
    if not os.path.exists(out):
        rc = run(["mt_translate.py", f"../repo/premium/{m}/inline", out], f"overnight_{m}.log")
        if rc != 0 or not os.path.exists(out):
            print(m, "MT failed", rc, flush=True); continue
    run(["mt_fix.py", m], f"overnight_{m}.log")
    run(["apply_mod.py", m, "corr_global.json"], f"overnight_{m}.log")
    print(m, "done", int(time.time() - t), "s", flush=True)
print("ALL DONE", flush=True)
