# -*- coding: utf-8 -*-
"""在QMT目录中搜索xtquant Python模块"""
import os

qmt_dirs = [
    r"D:\国金QMT交易端模拟",
    r"D:\光大证券金阳光QMT实盘",
]

for qmt_dir in qmt_dirs:
    print(f"\n=== {qmt_dir} ===")
    
    # 1. 查找 bin.x64 目录中的pyd文件
    bin_dir = os.path.join(qmt_dir, "bin.x64")
    if os.path.exists(bin_dir):
        print(f"\n  bin.x64 中的Python相关文件:")
        for f in os.listdir(bin_dir):
            fl = f.lower()
            if any(ext in fl for ext in ['.pyd', '.py', 'python', '_qmt', 'xtquant']):
                full = os.path.join(bin_dir, f)
                size = os.path.getsize(full)
                print(f"    {f} ({size} bytes)")
    
    # 2. 查找Lib/site-packages
    lib_dir = os.path.join(qmt_dir, "Lib", "site-packages")
    if os.path.exists(lib_dir):
        print(f"\n  Lib/site-packages:")
        for item in os.listdir(lib_dir):
            print(f"    {item}")
            full = os.path.join(lib_dir, item)
            if os.path.isdir(full) and ('xt' in item.lower() or 'qmt' in item.lower()):
                for sub in os.listdir(full):
                    print(f"      {sub}")
    
    # 3. 查找其他Python目录
    for sub in ['python', 'Python', 'python36', 'Python36', 'Lib']:
        sub_dir = os.path.join(qmt_dir, sub)
        if os.path.exists(sub_dir):
            print(f"\n  {sub}/:")
            try:
                items = os.listdir(sub_dir)[:30]
                for item in items:
                    full = os.path.join(sub_dir, item)
                    if os.path.isdir(full):
                        print(f"    {item}/")
                    else:
                        sz = os.path.getsize(full)
                        print(f"    {item} ({sz} bytes)")
            except:
                print(f"    无法列出")

# 4. 搜索整个QMT目录的.pyd文件
print("\n\n=== 搜索所有.pyd文件 (仅xtquant相关) ===")
for qmt_dir in qmt_dirs:
    if not os.path.exists(qmt_dir):
        continue
    for root, dirs, files in os.walk(qmt_dir):
        for f in files:
            if f.lower().endswith('.pyd') and 'xt' in f.lower():
                print(f"  {os.path.join(root, f)}")
        # 限制深度
        if root.replace(qmt_dir, "").count(os.sep) > 6:
            dirs.clear()

# 5. 查找 xtquant 目录
print("\n\n=== 搜索 xtquant 目录 ===")
for qmt_dir in qmt_dirs:
    if not os.path.exists(qmt_dir):
        continue
    for root, dirs, files in os.walk(qmt_dir):
        for d in dirs:
            if d.lower() == 'xtquant':
                full_dir = os.path.join(root, d)
                print(f"\n  找到目录: {full_dir}")
                for item in os.listdir(full_dir):
                    item_full = os.path.join(full_dir, item)
                    if os.path.isdir(item_full):
                        print(f"    {item}/")
                        try:
                            for sub in os.listdir(item_full):
                                print(f"      {sub}")
                        except:
                            pass
                    else:
                        sz = os.path.getsize(item_full)
                        print(f"    {item} ({sz} bytes)")
        if root.replace(qmt_dir, "").count(os.sep) > 6:
            dirs.clear()
