import subprocess, sys

r = subprocess.run(
    [sys.executable, "-m", "pip", "install", "playwright"],
    capture_output=True, text=True, timeout=60
)
print(f"退出码: {r.returncode}")
if r.stdout:
    print(r.stdout[-300:])
if r.stderr:
    print(r.stderr[-300:])

# 验证
try:
    from playwright.sync_api import sync_playwright
    print("Playwright导入成功!")
except ImportError as e:
    print(f"导入失败: {e}")
