import os, time, subprocess

bat = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\start_frontend.bat"

# 使用 start 命令在独立窗口中启动
subprocess.run(f'start "Vite前端" cmd /c "{bat}"', shell=True)

print("前端已在独立窗口启动，等待就绪...")

# 等待端口
for i in range(15):
    time.sleep(2)
    r = subprocess.run('netstat -ano | findstr ":5173 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        print("前端已就绪! 端口5173正在监听")
        print(r.stdout.strip())
        exit(0)
    print(f"  等待 {i+1}/15...")

print("超时")
exit(1)
