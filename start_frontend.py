import subprocess, os, time

web_dir = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\web"

# 先杀掉旧进程
r = subprocess.run('netstat -ano | findstr ":5173 "', shell=True, capture_output=True, text=True)
for line in r.stdout.strip().split('\n'):
    parts = line.strip().split()
    if len(parts) >= 5 and parts[3].endswith(':5173') and parts[1] == '0.0.0.0':
        pass
    # 杀掉LISTENING的进程
    if 'LISTENING' in line:
        pid = parts[-1]
        subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
        print(f"已终止旧进程 PID {pid}")

# 启动Vite
log_out = os.path.join(web_dir, ".ai_quant", "logs", "frontend_manual.log")
log_err = os.path.join(web_dir, ".ai_quant", "logs", "frontend_manual_err.log")
os.makedirs(os.path.dirname(log_out), exist_ok=True)

proc = subprocess.Popen(
    'cmd /c start "" /B npx vite --host 127.0.0.1 --port 5173',
    cwd=web_dir, shell=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

print(f"Vite 已启动 (PID: {proc.pid})")
time.sleep(5)

if proc.poll() is None:
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:5173")
        resp = urllib.request.urlopen(req, timeout=5)
        print(f"前端响应正常 (HTTP {resp.status})")
    except Exception as e:
        print(f"前端未响应: {e}")
        # 检查错误日志
        if os.path.exists(log_err):
            with open(log_err, 'r', encoding='utf-8', errors='replace') as f:
                err = f.read()
            if err.strip():
                print(f"错误日志:\n{err[-1000:]}")
else:
    print(f"前端进程已退出 (code: {proc.poll()})")
    if os.path.exists(log_err):
        with open(log_err, 'r', encoding='utf-8', errors='replace') as f:
            print(f.read()[-2000:])
