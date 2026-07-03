import os, subprocess, sys

python_exe = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\venv\Scripts\python.exe"
bot_script = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\backend\feishu\bot.py"
project_root = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant"

print(f"Python存在: {os.path.exists(python_exe)}")
print(f"Bot脚本存在: {os.path.exists(bot_script)}")

# 加载env后直接启动脚本（内联执行，看输出）
env_file = os.path.join(project_root, ".env")
env_vars = os.environ.copy()
with open(env_file, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            env_vars[key.strip()] = val.strip().strip('"')

out_file = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\feishu_output.txt"

# 直接用 cmd start 启动
cmd = f'start "" /B "{python_exe}" "{bot_script}"'
print(f"命令: {cmd}")

proc = subprocess.Popen(
    cmd,
    shell=True,
    cwd=project_root,
    env=env_vars,
    stdout=open(out_file, "w"),
    stderr=subprocess.STDOUT,
)
print(f"父进程PID: {proc.pid}")

# 用timeout子进程等待
import time
time.sleep(5)

# 检查
r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
if 'LISTENING' in r.stdout:
    print(f"端口8501已监听!")
else:
    print("端口8501无监听")

# 读取输出
if os.path.exists(out_file):
    with open(out_file, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    print(f"输出 ({len(content)} chars):")
    print(content[-2000:])
