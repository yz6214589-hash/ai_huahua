import subprocess, os, time, sys

web_dir = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\web"
OUT = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\frontend_start_log.txt"

with open(OUT, 'w') as f:
    f.write("=== 启动前端 ===\n")

# 方案：直接用 node node_modules/.bin/vite
# 找到 node.exe
for node_path in [
    r"C:\Program Files\nodejs\node.exe",
    r"C:\Program Files (x86)\nodejs\node.exe",
]:
    if os.path.exists(node_path):
        with open(OUT, 'a') as f:
            f.write(f"node.exe: {node_path}\n")
        
        # 直接使用 node 调用 vite
        vite_js = os.path.join(web_dir, "node_modules", ".bin", "vite")
        if not os.path.exists(vite_js):
            vite_js = os.path.join(web_dir, "node_modules", "vite", "bin", "vite.js")
        
        with open(OUT, 'a') as f:
            f.write(f"vite: {vite_js} (存在: {os.path.exists(vite_js)})\n")
        
        if os.path.exists(vite_js):
            proc = subprocess.Popen(
                [node_path, vite_js, "--host", "127.0.0.1", "--port", "5173"],
                cwd=web_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            with open(OUT, 'a') as f:
                f.write(f"Vite PID: {proc.pid}\n")
            
            time.sleep(5)
            
            # Check
            import urllib.request
            try:
                req = urllib.request.Request("http://127.0.0.1:5173")
                resp = urllib.request.urlopen(req, timeout=5)
                with open(OUT, 'a') as f:
                    f.write(f"前端响应: HTTP {resp.status}\n")
                sys.exit(0)
            except Exception as e:
                with open(OUT, 'a') as f:
                    f.write(f"前端未响应: {e}\n")
            
            sys.exit(0)

with open(OUT, 'a') as f:
    f.write("未找到 node.exe\n")
