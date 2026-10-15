import os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
env = dict(os.environ, PYTHONIOENCODING="utf-8", NWN_MT_THREADS="6")
dirs = sorted(d for d in os.listdir("community") if os.path.isdir(os.path.join("community", d, "inline")))
dirs.sort(key=lambda d: sum(os.path.getsize(os.path.join("community", d, "inline", f)) for f in os.listdir(os.path.join("community", d, "inline"))))
for d in dirs:
    out = os.path.join("community", d, "all.json")
    if os.path.exists(out):
        continue
    with open(os.path.join("community", d, "mt.log"), "a", encoding="utf-8") as lg:
        subprocess.run([sys.executable, "mt_translate.py", os.path.join("community", d, "inline"), out],
                       env=env, stdout=lg, stderr=subprocess.STDOUT)
    print(d, "done", flush=True)
print("COMMUNITY DONE", flush=True)
