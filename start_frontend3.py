import subprocess, os, sys, time

web_dir = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\web"
nodejs_dir = r"C:\Program Files\nodejs"
node_exe = os.path.join(nodejs_dir, "node.exe")

if not os.path.exists(node_exe):
    print(f"node.exe 未找到: {node_exe}")
    sys.exit(1)

vite_js = os.path.join(web_dir, "node_modules", "vite", "bin", "vite.js")
print(f"vite.js: {vite_js} (存在: {os.path.exists(vite_js)})")

proc = subprocess.Popen(
    [node_exe, vite_js, "--host", "127.0.0.1", "--port", "5173"],
    cwd=web_dir,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)
print(f"Vite 启动 PID: {proc.pid}")

# 等待Vite就绪
for i in range(10):
    time.sleep(2)
    r = subprocess.run('netstat -ano | findstr ":5173 "', shell=True, capture_output=True, text=True)
    if 'LISTENING' in r.stdout:
        print(f"端口5173已监听!")
        print(r.stdout.strip())
        sys.exit(0)
    print(f"  等待 {i+1}/10...")

print("超时")
sys.exit(1)
