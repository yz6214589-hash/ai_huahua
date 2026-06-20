import os

script_path = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\scripts\start_all.ps1"

# 读取当前内容
with open(script_path, 'rb') as f:
    content = f.read()

# 确认已经移除了BOM
if content.startswith(b'\xef\xbb\xbf'):
    print("已有BOM，无需修改")
else:
    # 添加单个UTF-8 BOM
    print(f"当前开头: {content[:6].hex()}")
    with open(script_path, 'wb') as f:
        f.write(b'\xef\xbb\xbf')  # UTF-8 BOM
        f.write(content)
    print("已添加UTF-8 BOM")

# 验证
with open(script_path, 'rb') as f:
    first_bytes = f.read(10)
print(f"验证前10字节: {first_bytes.hex()}")

# 尝试以UTF-8读前几行看看是否正确
with open(script_path, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()[:5]
for i, line in enumerate(lines):
    print(f"  行{i+1}: {line.rstrip()[:80]}")
