import subprocess, os

OUT = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\npx_path.txt"

r = subprocess.run('where npx 2>&1', shell=True, capture_output=True, text=True)
with open(OUT, 'w') as f:
    f.write(f"returncode={r.returncode}\n")
    f.write(f"stdout={r.stdout}\n")
    f.write(f"stderr={r.stderr}\n")

# Also check npm
r2 = subprocess.run('where npm 2>&1', shell=True, capture_output=True, text=True)
with open(OUT, 'a') as f:
    f.write(f"\nnpm returncode={r2.returncode}\n")
    f.write(f"npm stdout={r2.stdout}\n")
    f.write(f"npm stderr={r2.stderr}\n")

# Check node
r3 = subprocess.run('where node 2>&1', shell=True, capture_output=True, text=True)
with open(OUT, 'a') as f:
    f.write(f"\nnode returncode={r3.returncode}\n")
    f.write(f"node stdout={r3.stdout}\n")
    f.write(f"node stderr={r3.stderr}\n")
