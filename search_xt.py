# -*- coding: utf-8 -*-
"""搜索 xtquant Python 包"""
import os
import sys
import subprocess

print("当前 Python:", sys.executable)
print("当前 Python 版本:", sys.version)

# 1. pip list
print("\n=== pip list (search xtquant) ===")
r = subprocess.run([sys.executable, "-m", "pip", "list"], capture_output=True, text=True)
for line in r.stdout.splitlines():
    if "xt" in line.lower():
        print("  ", line)
if not any("xt" in l.lower() for l in r.stdout.splitlines()):
    print("  未找到")

# 2. 搜索 common site-packages 路径
print("\n=== 搜索 site-packages 中的 xtquant ===")
search_paths = []
# 当前 Python 的 site-packages
for p in sys.path:
    if "site-packages" in p:
        search_paths.append(p)

# 也检查 D 盘的 Python
for base in ["D:\\Python", "D:\\python", "D:\\Anaconda", "D:\\Program Files\\Python"]:
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        if "site-packages" in dirs and root.count(os.sep) < 4:
            search_paths.append(os.path.join(root, "site-packages"))
        depth = root.replace(base, "").count(os.sep)
        if depth > 3:
            dirs.clear()

for sp in set(search_paths):
    xt_path = os.path.join(sp, "xtquant")
    if os.path.isdir(xt_path):
        print(f"  找到: {xt_path}")
        # 列出内容
        for item in sorted(os.listdir(xt_path))[:10]:
            print(f"    {item}")

# 3. 搜索 dist-info
print("\n=== 搜索 xtquant 的 dist-info/egg-info ===")
for sp in set(search_paths):
    if not os.path.isdir(sp):
        continue
    for item in os.listdir(sp):
        if "xtquant" in item.lower():
            print(f"  {os.path.join(sp, item)}")

# 4. 检查 PYTHONPATH 环境变量
print("\n=== PYTHONPATH ===")
pp = os.environ.get("PYTHONPATH", "")
print(f"  '{pp}'")

# 5. 搜索 xtquant 的 wheel/安装包
print("\n=== 搜索 .whl 包 ===")
for root_name in ["D:\\BaiduNetdiskDownload", "D:\\"]:
    if not os.path.isdir(root_name):
        continue
    try:
        for item in os.listdir(root_name):
            if "xt" in item.lower() and (item.endswith(".whl") or item.endswith(".tar.gz") or item.endswith(".zip")):
                print(f"  {os.path.join(root_name, item)}")
    except:
        pass

print("\n完成")
