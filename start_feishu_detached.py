import subprocess, os, sys, time

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

print(f"FEISHU_APP_ID: {env_vars.get('FEISHU_APP_ID', 'NOT SET')[:20]}...")

# 关键: 使用 DETACHED_PROCESS 让子进程脱离父进程独立运行
proc = subprocess.Popen(
    [python_exe, bot_script],
    cwd=project_root,
    env=env_vars,
    creationflags=subprocess.DETACHED_PROCESS,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

print(f"子进程PID: {proc.pid}")

# 等待子进程启动（最多20秒）
for i in range(10):
    time.sleep(2)
    # 检查子进程是否还活着
    poll = proc.poll()
    if poll is not None:
        print(f"子进程已退出 (code: {poll})")
        # 检查错误日志
        err_log = os.path.join(project_root, ".ai_quant", "logs", "feishu_bot_err.log")
        if os.path.exists(err_log):
            with open(err_log, 'r', encoding='utf-8', errors='replace') as f:
                err = f.read()
            if err.strip():
                print(f"错误日志: {err[-1000:]}")
                sys.exit(1)
        print("日志为空，进程可能启动失败")
        sys.exit(1)
    
    # 检查端口
    r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        print(f"飞书机器人已启动! 端口8501监听中 ({i*2}s)")
        sys.exit(0)
    print(f"  等待 {i+1}/10... (PID {proc.pid})")

print("\n超时，检查状态...")
time.sleep(5)
# 最后检查
r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
if 'LISTENING' in r.stdout:
    print(f"端口8501已监听!")
else:
    print("端口8501无监听")
    
    # 检查日志
    bot_log = os.path.join(project_root, ".ai_quant", "logs", "feishu_bot.log")
    err_log = os.path.join(project_root, ".ai_quant", "logs", "feishu_bot_err.log")
    for lf in [bot_log, err_log]:
        if os.path.exists(lf):
            with open(lf, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
            print(f"\n{os.path.basename(lf)} ({len(content)} chars):")
            print(content[-2000:])
