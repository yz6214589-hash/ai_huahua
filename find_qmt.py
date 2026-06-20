# -*- coding: utf-8 -*-
"""搜索 QMT 目录中可能的 xtquant 安装包"""
import os

qmt_dirs = [
    "D:\\国金QMT交易端模拟",
    "D:\\光大证券金阳光QMT实盘",
]

for qmt_root in qmt_dirs:
    print(f"\n{'='*60}")
    print(f"搜索: {qmt_root}")
    print("="*60)
    
    if not os.path.isdir(qmt_root):
        print("  不存在")
        continue
    
    # 搜索 xtquant 相关的所有文件和目录
    for root, dirs, files in os.walk(qmt_root):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        
        # 搜索文件
        for f in files:
            fl = f.lower()
            if any(kw in fl for kw in ["xtquant", "xtdata", "xttrader", "xtconstant", "xttype"]):
                if fl.endswith((".py", ".pyd", ".whl", ".zip", ".tar.gz", ".egg", ".dll")):
                    print(f"  [F] {os.path.join(root, f)}")
        
        # 搜索目录
        for d in dirs:
            dl = d.lower()
            if dl in ("xtquant", "xtdata", "xttrader", "xtconstant", "xttype"):
                full = os.path.join(root, d)
                print(f"  [D] {full}/")
                # 列出内容
                for item in sorted(os.listdir(full))[:20]:
                    print(f"      {item}")
        
        # 深度控制
        depth = root.replace(qmt_root, "").count(os.sep)
        if depth > 6:
            dirs.clear()

# 3. 专门检查 xtmodel 目录
print(f"\n{'='*60}")
print("检查 光大实盘 xtmodel 目录")
print("="*60)
xtmodel = "D:\\光大证券金阳光QMT实盘\\xtmodel"
if os.path.isdir(xtmodel):
    for item in sorted(os.listdir(xtmodel)):
        print(f"  {item}")
        full = os.path.join(xtmodel, item)
        if os.path.isdir(full):
            for sub in sorted(os.listdir(full))[:10]:
                print(f"    {sub}")

print("\n完成")
