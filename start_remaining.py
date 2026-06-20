# -*- coding: utf-8 -*-
"""手动启动后端和前端服务"""
import subprocess
import sys
import os
import time

proj_root = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant"
venv_python = os.path.join(proj_root, "venv", "Scripts", "python.exe")
backend_dir = os.path.join(proj_root, "backend")
frontend_dir = os.path.join(proj_root, "web")
log_dir = os.path.join(proj_root, ".ai_quant", "logs")
os.makedirs(log_dir, exist_ok=True)

results = {}

# ========== 启动后端 ==========
print("=== 启动后端API (端口8000) ===")
env = os.environ.copy()
env["PYTHONPATH"] = backend_dir

backend_log = open(os.path.join(log_dir, "backend_manual.log"), "w")
backend_err = open(os.path.join(log_dir, "backend_manual_err.log"), "w")

backend_proc = subprocess.Popen(
    [venv_python, "-m", "uvicorn", "backend.app:app",
     "--host", "127.0.0.1", "--port", "8000", "--reload"],
    cwd=proj_root,
    env=env,
    stdout=backend_log,
    stderr=backend_err,
)
time.sleep(5)

# 检查后端是否启动
if backend_proc.poll() is None:
    # 测试连接
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/health")
        resp = urllib.request.urlopen(req, timeout=3)
        print(f"  后端已启动 (PID: {backend_proc.pid}, 状态码: {resp.status})")
        results["backend"] = True
    except Exception as e:
        print(f"  后端端口未响应: {e}")
        results["backend"] = False
else:
    print(f"  后端启动失败 (退出码: {backend_proc.poll()})")
    results["backend"] = False

# ========== 启动前端 ==========
print("\n=== 启动前端 (端口5173) ===")
# 使用 npx vite 或 node_modules/.bin/vite
vite_bin = os.path.join(frontend_dir, "node_modules", ".bin", "vite.cmd")
if not os.path.exists(vite_bin):
    vite_bin = os.path.join(frontend_dir, "node_modules", ".bin", "vite")
if not os.path.exists(vite_bin):
    print(f"  找不到vite: {vite_bin}")
    # 尝试 npx
    frontend_proc = subprocess.Popen(
        ["npx", "vite", "--host", "127.0.0.1", "--port", "5173"],
        cwd=frontend_dir,
        stdout=open(os.path.join(log_dir, "frontend_manual.log"), "w"),
        stderr=open(os.path.join(log_dir, "frontend_manual_err.log"), "w"),
    )
else:
    frontend_proc = subprocess.Popen(
        [vite_bin, "--host", "127.0.0.1", "--port", "5173"],
        cwd=frontend_dir,
        stdout=open(os.path.join(log_dir, "frontend_manual.log"), "w"),
        stderr=open(os.path.join(log_dir, "frontend_manual_err.log"), "w"),
    )

time.sleep(5)

# 检查前端是否启动
if frontend_proc.poll() is None:
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:5173")
        resp = urllib.request.urlopen(req, timeout=3)
        print(f"  前端已启动 (PID: {frontend_proc.pid}, 状态码: {resp.status})")
        results["frontend"] = True
    except Exception as e:
        print(f"  前端端口未响应: {e}")
        results["frontend"] = False
else:
    print(f"  前端启动失败")
    results["frontend"] = False

print("\n=== 启动结果 ===")
for svc, ok in results.items():
    print(f"  {svc}: {'OK' if ok else 'FAIL'}")
