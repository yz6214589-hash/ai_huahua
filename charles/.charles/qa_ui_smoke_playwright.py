import os
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright


BASE_URL = os.getenv("CHARLES_WEB_BASE", "http://127.0.0.1:5173")
ART_DIR = Path(os.getenv("CHARLES_QA_ART_DIR", ".charles/qa_ui_artifacts")).resolve()
ART_DIR.mkdir(parents=True, exist_ok=True)


def shot(page, name: str):
    ts = datetime.now().strftime("%H%M%S")
    path = ART_DIR / f"{ts}_{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def assert_no_http500(page):
    if page.locator("text=HTTP 500").count() > 0:
        raise AssertionError("Page contains HTTP 500 banner")


def click_nav(page, label: str):
    page.get_by_role("link", name=label).click()
    page.wait_for_load_state("networkidle")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=False, slow_mo=250)
        context = browser.new_context(viewport={"width": 1500, "height": 900})
        page = context.new_page()

        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        shot(page, "home_loaded")
        assert_no_http500(page)

        drawer_iframe = page.locator('iframe[title="assistant-streamlit"]')
        if drawer_iframe.count() == 0:
            shot(page, "drawer_missing")
            raise AssertionError("Assistant drawer iframe not found")
        shot(page, "drawer_expanded")

        toggle = page.locator('button[title="折叠"], button[title="展开"]').first
        toggle.click()
        page.wait_for_timeout(600)
        shot(page, "drawer_collapsed")
        if page.locator('iframe[title="assistant-streamlit"]').count() != 0:
            raise AssertionError("Drawer collapsed but iframe still present")
        toggle.click()
        page.wait_for_timeout(800)
        shot(page, "drawer_expanded_again")
        if page.locator('iframe[title="assistant-streamlit"]').count() == 0:
            raise AssertionError("Drawer expanded but iframe missing")

        click_nav(page, "采集任务")
        shot(page, "jobs")
        assert_no_http500(page)
        page.get_by_text("采集任务").first.wait_for(timeout=5000)

        click_nav(page, "智能研报")
        shot(page, "reports")
        assert_no_http500(page)
        page.get_by_text("智能研报").first.wait_for(timeout=5000)
        page.get_by_text("模型").first.wait_for(timeout=5000)

        click_nav(page, "舆情监控")
        shot(page, "sentiment_watch")
        assert_no_http500(page)
        page.get_by_text("立即扫描自选股").first.wait_for(timeout=5000)
        page.get_by_text("宏观风险").first.click()
        page.wait_for_timeout(1200)
        shot(page, "sentiment_macro")

        click_nav(page, "自选股")
        shot(page, "watchlist")
        assert_no_http500(page)

        page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        shot(page, "streamlit_home")

        browser.close()


if __name__ == "__main__":
    main()
