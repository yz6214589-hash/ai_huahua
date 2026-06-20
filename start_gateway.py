# -*- coding: utf-8 -*-
"""启动 QMT Gateway 服务器（后台模式）"""
import subprocess
import sys
import os
import time

GATEWAY_DIR = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant_qmt_gateway"

print("启动 QMT Gateway（后台模式）...")
env = os.environ.copy()
env.pop("QMT_API_TOKEN", None)  # 不使用 token，方便测试

os.chdir(GATEWAY_DIR)
proc = subprocess.Popen(
    [sys.executable, "run_server.py"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env=env,
    cwd=GATEWAY_DIR,
)

print(f"进程 PID: {proc.pid}")
print("等待 3 秒...")
time.sleep(3)

# 检查进程是否存活
poll = proc.poll()
if poll is not None:
    print(f"进程已退出，退出码: {poll}")
    out, err = proc.communicate()
    print("STDOUT:", out.decode("utf-8", errors="replace")[-500:])
    print("STDERR:", err.decode("utf-8", errors="replace")[-500:])
else:
    print("进程运行中")
    # 读取一些输出
    print("等待 2 秒后读取日志...")
    time.sleep(2)
    try:
        out, err = proc.communicate(timeout=1)
        print("STDOUT:", out.decode("utf-8", errors="replace")[-500:] if out else "(空)")
        print("STDERR:", err.decode("utf-8", errors="replace")[-500:] if err else "(空)")
    except subprocess.TimeoutExpired:
        print("服务器正在运行（无额外输出）")
        print("PID:", proc.pid)
