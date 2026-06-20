# -*- coding: utf-8 -*-
"""简单测试 - 直接打印到文件"""
import sys

with open(r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\test_output.txt", "w", encoding="utf-8") as f:
    # 1. 检查端口
    import subprocess
    result = subprocess.run("netstat -ano | findstr :8001", shell=True, capture_output=True, text=True)
    f.write(f"端口8001状态:\n{result.stdout}\n")
    
    # 2. 测试health
    import urllib.request
    try:
        req = urllib.request.Request("http://127.0.0.1:8001/health")
        resp = urllib.request.urlopen(req, timeout=5)
        f.write(f"Health: {resp.status}\n")
    except Exception as e:
        f.write(f"Health异常: {e}\n")
    
    # 3. 测试connect (30秒超时)
    import json
    try:
        data = json.dumps({}).encode("utf-8")
        req = urllib.request.Request("http://127.0.0.1:8001/api/trading/connect", 
                                      data=data, 
                                      headers={"Content-Type": "application/json"},
                                      method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        f.write(f"Connect状态码: {resp.status}\n")
        f.write(f"Connect响应: {resp.read().decode('utf-8')}\n")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if e.fp else "(无)"
        f.write(f"Connect HTTP错误 {e.code}: {body}\n")
    except Exception as e:
        f.write(f"Connect异常: {e}\n")
    
    f.write("完成\n")

print("结果已写入 test_output.txt")
