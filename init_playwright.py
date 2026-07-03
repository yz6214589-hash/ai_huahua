import sys, os

# 确保backend在路径中
sys.path.insert(0, r"d:\BaiduNetdiskDownload\ai_huahua\ai_huahua\ai_quant\backend")

from infra.playwright_setup import ensure_playwright_ready, load_config

print("=== 初始化Playwright浏览器 ===")
config = ensure_playwright_ready()
print(f"安装状态: {config.browsers_installed}")
print(f"安装路径: {config.install_path}")
print(f"Chromium: {config.chromium_path}")
print(f"版本: {config.version}")
