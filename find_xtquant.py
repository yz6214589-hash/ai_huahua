# -*- coding: utf-8 -*-
"""搜索QMT安装目录中的xtquant模块"""
import os
import sys
import glob as glob_module

# QMT可能的安装位置
qmt_dirs = [
    r"D:\国金QMT交易端模拟",
    r"D:\光大证券金阳光QMT实盘",
]

for qmt_dir in qmt_dirs:
    print(f"\n=== 搜索 {qmt_dir} ===")
    if not os.path.exists(qmt_dir):
        print("  目录不存在!")
        continue
    
    # 搜索所有目录
    for root, dirs, files in os.walk(qmt_dir):
        # 跳过一些无关目录
        if any(skip in root for skip in ['.git', '__pycache__', 'node_modules']):
            continue
        
        # 查找 xtquant 相关的 .pyd, .so, .dll, .py 文件
        for f in files:
            if 'xtquant' in f.lower() or 'xt' in f.lower():
                full = os.path.join(root, f)
                print(f"  找到: {full}")
        
        # 查找包含 xtquant 的目录
        for d in dirs:
            if 'xtquant' in d.lower():
                full = os.path.join(root, d)
                print(f"  目录: {full}")
                # 列出该目录内容
                try:
                    for item in os.listdir(full):
                        item_full = os.path.join(full, item)
                        print(f"    {item_full}")
                except:
                    pass
        
        # 限制深度
        depth = root.replace(qmt_dir, "").count(os.sep)
        if depth > 5:
            dirs.clear()

# 检查是否有pip可安装的xtquant
print("\n\n=== 检查pip xtquant ===")
import subprocess
result = subprocess.run([sys.executable, "-m", "pip", "search", "xtquant"], capture_output=True, text=True)
print(result.stdout[:500] if result.stdout else "无结果")
print(result.stderr[:500] if result.stderr else "")

# 检查site-packages
print("\n=== site-packages中搜索 ===")
for p in sys.path:
    if 'site-packages' in p and os.path.exists(p):
        for item in os.listdir(p):
            if 'xt' in item.lower():
                full = os.path.join(p, item)
                print(f"  {full}")

print("\n=== 当前Python路径 ===")
print(sys.executable)
