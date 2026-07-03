import subprocess, time

# 杀旧Vite进程
r = subprocess.run('netstat -ano | findstr ":5173 "', shell=True, capture_output=True, text=True)
for line in r.stdout.strip().split('\n'):
    if 'LISTENING' in line:
        pid = line.strip().split()[-1]
        subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
        print(f"已终止 PID {pid}")

time.sleep(1)

# 重启Vite（使用新的resolve.alias配置）
web_dir = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\web"
subprocess.Popen(
    f'start "Vite" cmd /c "cd /d {web_dir} && npx vite --host 127.0.0.1 --port 5173"',
    shell=True
)

# 等待端口
for i in range(15):
    time.sleep(2)
    r = subprocess.run('netstat -ano | findstr ":5173 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        print(f"Vite已启动 (端口: 5173)")
        break
    print(f"  等待 {i+1}/15...")

# 测试
import urllib.request
try:
    req = urllib.request.Request("http://127.0.0.1:5173/src/main.tsx")
    resp = urllib.request.urlopen(req, timeout=5)
    body = resp.read(3000).decode('utf-8', errors='replace')
    # 检查导入解析是否成功
    if "Failed to resolve" in body or "plugin:vite" in body:
        print(f"仍有错误: {body[:500]}")
    else:
        print(f"模块解析正常 (HTTP {resp.status})")
except Exception as e:
    print(f"连接失败: {e}")
