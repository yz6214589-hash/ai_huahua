import subprocess, os, time, sys

python_exe = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\venv\Scripts\python.exe"
bot_script = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\backend\feishu\bot.py"
project_root = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant"

# 加载env
env_file = os.path.join(project_root, ".env")
env_vars = os.environ.copy()
with open(env_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            env_vars[key.strip()] = val.strip().strip('"')

# 确保日志目录
log_dir = os.path.join(project_root, ".ai_quant", "logs")
os.makedirs(log_dir, exist_ok=True)

# 杀旧进程
r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
for line in r.stdout.strip().split('\n'):
    if 'LISTENING' in line:
        pid = line.strip().split()[-1]
        subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
        print(f"已终止 PID {pid}")
        time.sleep(1)

print(f"FEISHU_APP_ID: {env_vars.get('FEISHU_APP_ID', 'NOT SET')[:20]}...")

# DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP: 脱离父进程+禁止Ctrl+C
flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

proc = subprocess.Popen(
    [python_exe, bot_script],
    cwd=project_root,
    env=env_vars,
    creationflags=flags,
)

print(f"启动 PID: {proc.pid}")

# 等待连接
for i in range(15):
    time.sleep(2)
    if proc.poll() is not None:
        print(f"进程已退出 (code: {proc.poll()})")
        err_log = os.path.join(log_dir, "feishu_bot_err.log")
        if os.path.exists(err_log):
            with open(err_log, 'r', encoding='utf-8', errors='replace') as f:
                err = f.read()
            print(err[-1000:])
        sys.exit(1)
    
    r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        print(f"已启动! 端口8501监听中 ({i*2}s)")
        sys.exit(0)
    print(f"  等待 {i+1}/15...")

print("超时")
