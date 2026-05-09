#!/usr/bin/env python3
"""使用 Playwright 截取 AI 量化系统各页面截图"""

import os
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = "/Users/apple/Desktop/ai_huahua/ai_quant/docs/screenshots"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        
        screenshots = []
        
        pages_to_capture = [
            ("01-home", "http://localhost:5173/"),
            ("02-reports", "http://localhost:5173/reports"),
            ("03-jobs", "http://localhost:5173/jobs"),
            ("04-data", "http://localhost:5173/data"),
            ("05-watchlist", "http://localhost:5173/watchlist"),
            ("06-sentiment", "http://localhost:5173/sentiment"),
            ("07-morning", "http://localhost:5173/morning"),
            ("08-execution", "http://localhost:5173/execution"),
            ("09-risk", "http://localhost:5173/risk"),
            ("10-chat", "http://localhost:5173/chat"),
            ("11-strategy", "http://localhost:5173/strategy"),
        ]
        
        for name, url in pages_to_capture:
            print(f"正在截取 {name}...")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                filepath = f"{SCREENSHOTS_DIR}/{name}.png"
                page.screenshot(path=filepath, full_page=True)
                screenshots.append(name)
                print(f"  已保存: {name}.png")
            except Exception as e:
                print(f"  截图失败: {e}")
        
        browser.close()
        
        print("\n========================================")
        print(f"截图完成！共截取 {len(screenshots)} 张图片")
        print(f"保存路径: {SCREENSHOTS_DIR}")
        print("========================================")
        for s in screenshots:
            print(f"  - {s}.png")

if __name__ == "__main__":
    main()
