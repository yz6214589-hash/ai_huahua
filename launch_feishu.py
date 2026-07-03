import os, time, subprocess, sys

# 杀旧进程
r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
for line in r.stdout.strip().split('\n'):
    if 'LISTENING' in line:
        pid = line.strip().split()[-1]
        subprocess.run(f'taskkill /PID {pid} /F', shell=True, capture_output=True)
        print(f"已终止 PID {pid}")
        time.sleep(1)

# 清空日志
log_dir = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\.ai_quant\logs"
for f in ["feishu_bot.log", "feishu_bot_err.log"]:
    open(os.path.join(log_dir, f), 'w').close()

# 使用 os.startfile 启动批处理 - 完全独立的进程
bat_file = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\start_feishu_bot.bat"
print(f"启动: {bat_file}")
os.startfile(bat_file)

# 等待端口
for i in range(15):
    time.sleep(2)
    r = subprocess.run('netstat -ano | findstr ":8501 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        pid = r.stdout.strip().split()[-1]
        print(f"已启动! PID: {pid}, 端口: 8501 ({i*2}s)")
        sys.exit(0)
    print(f"  等待 {i+1}/15...")

print("超时，检查日志...")
for f in ["feishu_bot_err.log"]:
    fp = os.path.join(log_dir, f)
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read()
        if content.strip():
            print(content[-1000:])
