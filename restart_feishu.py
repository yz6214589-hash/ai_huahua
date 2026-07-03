import subprocess, os, time

# 1. 杀旧飞书进程
r = subprocess.run('tasklist | findstr /i "python"', shell=True, capture_output=True, text=True)
# 先找端口8501上的进程
r2 = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
pid = None
for line in r2.stdout.strip().split('\n'):
    if 'LISTENING' in line:
        pid = line.strip().split()[-1]
        break

if pid:
    subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
    print(f"已终止旧飞书进程 PID {pid}")
    time.sleep(2)

# 2. 加载.env
env_file = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\.env"
env_vars = {}
with open(env_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#'):
            if '=' in line:
                key, val = line.split('=', 1)
                env_vars[key.strip()] = val.strip().strip('"')

print(f"FEISHU_APP_ID: {env_vars.get('FEISHU_APP_ID', '未找到')}")
print(f"FEISHU_APP_SECRET: {env_vars.get('FEISHU_APP_SECRET', '未找到')[:4]}...")

# 3. 启动飞书机器人
python_exe = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\venv\Scripts\python.exe"
bot_script = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\backend\feishu\bot.py"
project_root = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant"
log_dir = os.path.join(project_root, ".ai_quant", "logs")

new_env = os.environ.copy()
new_env.update(env_vars)

proc = subprocess.Popen(
    [python_exe, bot_script],
    cwd=project_root,
    env=new_env,
    stdout=open(os.path.join(log_dir, "feishu_bot.log"), "w"),
    stderr=open(os.path.join(log_dir, "feishu_bot_err.log"), "w"),
)
print(f"飞书机器人已启动 PID: {proc.pid}")

# 4. 等待并检查
time.sleep(5)
if proc.poll() is None:
    print("进程仍在运行, 检查启动日志...")
else:
    print(f"进程已退出 (code: {proc.poll()})")
    with open(os.path.join(log_dir, "feishu_bot_err.log"), 'r', encoding='utf-8', errors='replace') as f:
        err = f.read()
    print(f"错误: {err[-1000:]}")
