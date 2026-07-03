import subprocess, os, time, sys

# 加载.env
env_file = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\.env"
env_vars = os.environ.copy()
with open(env_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                key, val = line.split('=', 1)
                env_vars[key.strip()] = val.strip().strip('"')

print(f"FEISHU_APP_ID: {env_vars.get('FEISHU_APP_ID', 'NOT SET')}")

python_exe = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\venv\Scripts\python.exe"
bot_script = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\backend\feishu\bot.py"
project_root = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant"
log_dir = os.path.join(project_root, ".ai_quant", "logs")

# 使用CREATE_NEW_PROCESS_GROUP确保分离
proc = subprocess.Popen(
    [python_exe, bot_script],
    cwd=project_root,
    env=env_vars,
    stdout=open(os.path.join(log_dir, "feishu_bot.log"), "w", buffering=1),
    stderr=open(os.path.join(log_dir, "feishu_bot_err.log"), "w", buffering=1),
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)

print(f"启动 PID: {proc.pid}")

# 等待并检查
for i in range(10):
    time.sleep(2)
    if proc.poll() is not None:
        print(f"进程已退出 (code: {proc.poll()})")
        with open(os.path.join(log_dir, "feishu_bot_err.log"), 'r', encoding='utf-8', errors='replace') as f:
            err = f.read()
        print(f"错误日志:\n{err[-2000:]}")
        sys.exit(1)
    
    r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        print(f"飞书机器人已启动 (端口8501监听中, {i*2}s)")
        sys.exit(0)
    print(f"  等待 {i+1}/10... (PID {proc.pid} 运行中)")

print("超时")
