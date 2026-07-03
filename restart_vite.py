import os, subprocess, shutil, time

web_dir = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\web"
vite_cache = os.path.join(web_dir, "node_modules", ".vite")
tmp_dir = os.path.join(web_dir, "node_modules", ".tmp")

print("=== 清理Vite缓存 ===")

# 清除 .vite 缓存
if os.path.exists(vite_cache):
    shutil.rmtree(vite_cache)
    print(f"已清除: {vite_cache}")

# 清除 .tmp 缓存  
if os.path.exists(tmp_dir):
    shutil.rmtree(tmp_dir)
    print(f"已清除: {tmp_dir}")

# 杀旧进程
r = subprocess.run('netstat -ano | findstr ":5173 "', shell=True, capture_output=True, text=True)
for line in r.stdout.strip().split('\n'):
    if 'LISTENING' in line:
        pid = line.strip().split()[-1]
        subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
        print(f"已终止 PID {pid}")

time.sleep(1)

print("\n=== 重启Vite (--force 清除模块缓存) ===")
proc = subprocess.Popen(
    f'start "Vite" cmd /c "cd /d {web_dir} && npx vite --host 127.0.0.1 --port 5173 --force"',
    shell=True
)

# 等待端口
for i in range(15):
    time.sleep(2)
    r = subprocess.run('netstat -ano | findstr ":5173 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        pid = r.stdout.strip().split()[-1]
        print(f"Vite已启动 (PID: {pid}, 端口: 5173)")
        break
    print(f"  等待 {i+1}/15...")
else:
    print("启动超时!")
    exit(1)

# 测试
import urllib.request
try:
    req = urllib.request.Request("http://127.0.0.1:5173")
    resp = urllib.request.urlopen(req, timeout=5)
    body = resp.read().decode('utf-8', errors='replace')
    error_keywords = ['Failed to resolve', 'plugin:vite:import-analysis', 'Error']
    has_error = False
    for kw in error_keywords:
        if kw in body:
            print(f"页面包含错误: {kw}")
            has_error = True
    if not has_error:
        print(f"页面正常 (HTTP {resp.status})")
except Exception as e:
    print(f"连接失败: {e}")
