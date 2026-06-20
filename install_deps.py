# -*- coding: utf-8 -*-
"""安装网关依赖并检查结果"""
import subprocess
import sys

print("安装 fastapi, uvicorn, pydantic...")
r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "fastapi", "uvicorn", "pydantic"],
    capture_output=True, text=True
)
print("rc:", r.returncode)
if r.stdout:
    print("STDOUT:", r.stdout[-300:])
if r.stderr:
    print("STDERR:", r.stderr[-300:])

print("\n检查安装结果:")
for mod in ["fastapi", "uvicorn", "pydantic"]:
    try:
        __import__(mod)
        print(f"  {mod}: OK")
    except ImportError:
        print(f"  {mod}: FAIL")
