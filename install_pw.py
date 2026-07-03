import subprocess, os, json, time

# 1. 清除旧配置
config_file = r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\.ai_quant\playwright\config.json"
os.makedirs(os.path.dirname(config_file), exist_ok=True)

# 2. 设置Windows playwright路径
pw_path = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "ms-playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = pw_path

print(f"Playwright路径: {pw_path}")

# 3. 安装chromium (只用chromium)
print("安装Chromium浏览器...")
r = subprocess.run(
    "npx playwright install chromium",
    capture_output=True, text=True, timeout=300,
    cwd=r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\web",
    env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": pw_path},
    shell=True
)

print(f"返回码: {r.returncode}")
if r.stdout:
    print(f"stdout: {r.stdout[-500:]}")
if r.stderr:
    print(f"stderr: {r.stderr[-500:]}")

# 4. 查找chromium路径
chromium_path = ""
for root, dirs, files in os.walk(pw_path):
    if "chrome.exe" in files:
        chromium_path = os.path.join(root, "chrome.exe")
        break

print(f"\nChromium路径: {chromium_path}")

# 5. 保存配置
config = {
    "browsers_installed": bool(chromium_path),
    "install_path": pw_path,
    "chromium_path": chromium_path,
    "firefox_path": "",
    "webkit_path": "",
    "version": "",
    "install_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
}

with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print(f"配置已保存: {config_file}")
