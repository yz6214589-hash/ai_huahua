import subprocess
# 找到 npx.cmd 的完整路径
r = subprocess.run('where npx', shell=True, capture_output=True, text=True)
print(f"npx 路径: {r.stdout.strip()}")
