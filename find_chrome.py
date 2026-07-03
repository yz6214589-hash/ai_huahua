import os

pw_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "ms-playwright")
chrome_dir = os.path.join(pw_path, "chromium-1223")

for item in os.listdir(chrome_dir):
    print(f"  {item}")

# 找chrome.exe
for root, dirs, files in os.walk(chrome_dir):
    for f in files:
        if f.lower() in ("chrome.exe", "chromium.exe"):
            full = os.path.join(root, f)
            print(f"\nchrome.exe: {full}")
            print(f"  存在: {os.path.exists(full)}")
            print(f"  大小: {os.path.getsize(full)} bytes")
