# -*- coding: utf-8 -*-
"""深度搜索 xtquant - .pth文件, 全局Python, 注册表"""
import os
import sys

print("=== 搜索 .pth 文件 ===")
for p in sys.path:
    if not os.path.isdir(p):
        continue
    for f in os.listdir(p):
        if f.endswith('.pth'):
            fpath = os.path.join(p, f)
            try:
                with open(fpath, 'r') as fp:
                    content = fp.read()
                    if 'xt' in content.lower() or 'qmt' in content.lower():
                        print(f"  {fpath}: {content.strip()}")
            except:
                pass

print("\n=== 搜索 C:\\ 盘 Python 安装 ===")
for base in ["C:\\", "C:\\Program Files", "C:\\Users"]:
    try:
        for d in os.listdir(base):
            if "python" in d.lower() or "anaconda" in d.lower() or "miniconda" in d.lower():
                full = os.path.join(base, d)
                if os.path.isdir(full):
                    print(f"  {full}")
    except:
        pass

print("\n=== 检查 .pth 文件指定路径 ===")
# 常见位置
for loc in [
    "C:\\Users\\qqq\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages",
    "C:\\Users\\qqq\\AppData\\Roaming\\Python\\Python311\\site-packages",
    "D:\\BaiduNetdiskDownload\\ai_huahua\\ai_huahua",
]:
    if os.path.isdir(loc):
        for f in os.listdir(loc):
            if f.endswith('.pth'):
                fpath = os.path.join(loc, f)
                try:
                    with open(fpath, 'r') as fp:
                        content = fp.read()
                    print(f"  {fpath}:")
                    print(f"    {content.strip()}")
                except:
                    print(f"  {fpath}: 读取失败")

print("\n完成")
