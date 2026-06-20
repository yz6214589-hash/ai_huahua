import os

script_path = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\scripts\start_all.ps1"

# 读取原始字节
with open(script_path, 'rb') as f:
    raw = f.read()

# 检查BOM
print(f"文件大小: {len(raw)} bytes")
print(f"前20字节(hex): {raw[:20].hex()}")

# 显示前几个字符
for i, b in enumerate(raw[:10]):
    print(f"  byte[{i}]: {b:02x} ({chr(b) if 32 <= b < 127 else '?'})")

# 移除BOM并重新写入
# UTF-8 BOM: EF BB BF
# UTF-16 LE BOM: FF FE
bom_utf8 = b'\xef\xbb\xbf'

cleaned = raw
while cleaned.startswith(bom_utf8):
    cleaned = cleaned[len(bom_utf8):]
    print("移除了 UTF-8 BOM")

# 也检查是否有其他BOM标记 (ef bb bf bf bb ef...)
# 实际上，EF BB BF 是UTF-8 BOM, 如果文件被多次添加BOM
removed = 0
while cleaned[:3] == bom_utf8:
    cleaned = cleaned[3:]
    removed += 1
    
# 再看是否有 \xc3\xaf\xc2\xbb\xc2\xbf (这是UTF-8 BOM被GBK误读后再保存)
# 0xEF,0xBB,0xBF 在UTF-8中是BOM，但在GBK/其他编码下可能变成别的
# 直接检查开头是否有非ASCII的BOM字符
if cleaned and cleaned[0] > 127:
    print(f"开头有非ASCII字节: {cleaned[0]:02x}")
    # 可能还需要继续清理

# 跳过任何前导的非打印/空白BOM字符
start = 0
while start < len(cleaned) and cleaned[start] in (0xEF, 0xBB, 0xBF, 0xC3, 0xAF, 0xC2, 0xBB):
    start += 1
if start > 0:
    print(f"跳过 {start} 个BOM相关字节")
    cleaned = cleaned[start:]

# 确保以 # 开头
if not cleaned.startswith(b'#'):
    # 找第一个 # 位置
    hash_pos = cleaned.find(b'#')
    if hash_pos > 0:
        print(f"跳过前 {hash_pos} 个非#字节")
        cleaned = cleaned[hash_pos:]

print(f"清理后大小: {len(cleaned)} bytes")
print(f"前50字节: {cleaned[:50]}")

# 写回
with open(script_path, 'wb') as f:
    f.write(cleaned)

print("BOM已清除并保存")
