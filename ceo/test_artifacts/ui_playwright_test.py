import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE = "http://127.0.0.1:7865"
OUT_DIR = Path(__file__).resolve().parent / "ui_screens"
PW_HOME = Path(__file__).resolve().parent / "pw_home"


def _save(page, name: str):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT_DIR / f"{name}.png"), full_page=True)


def run():
    results = []
    bugs = []

    with sync_playwright() as p:
        PW_HOME.mkdir(parents=True, exist_ok=True)
        (PW_HOME / "cache").mkdir(parents=True, exist_ok=True)
        (PW_HOME / "config").mkdir(parents=True, exist_ok=True)

        browser = p.chromium.launch(
            headless=False,
            slow_mo=250,
            args=["--disable-crashpad", "--disable-breakpad"],
            env={
                "HOME": str(PW_HOME),
                "XDG_CACHE_HOME": str(PW_HOME / "cache"),
                "XDG_CONFIG_HOME": str(PW_HOME / "config"),
            },
        )
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        def step(step_id: str, title: str, fn):
            started = time.time()
            try:
                fn()
                results.append(
                    {
                        "id": step_id,
                        "title": title,
                        "passed": True,
                        "elapsed_ms": int((time.time() - started) * 1000),
                    }
                )
            except Exception as e:
                try:
                    _save(page, f"FAIL_{step_id}")
                except Exception:
                    pass
                results.append(
                    {
                        "id": step_id,
                        "title": title,
                        "passed": False,
                        "elapsed_ms": int((time.time() - started) * 1000),
                        "error": str(e),
                    }
                )
                bugs.append(
                    {
                        "id": f"BUG-{step_id}",
                        "source_case": step_id,
                        "title": f"UI 步骤失败：{title}",
                        "evidence": str(e),
                    }
                )

        step(
            "UI-01",
            "打开首页并重定向到 /live/sim",
            lambda: (
                page.goto(BASE + "/", wait_until="domcontentloaded", timeout=45000),
                page.wait_for_url("**/live/sim", timeout=45000),
                page.locator("nav.app-nav").wait_for(timeout=15000),
                page.locator(".card-title", has_text="实时持仓").first.wait_for(timeout=15000),
                _save(page, "01_live_sim"),
            ),
        )

        step(
            "UI-02",
            "导航到 系统状态 并触发健康检查",
            lambda: (
                page.locator("nav.app-nav a", has_text="系统状态").click(timeout=15000),
                page.wait_for_url("**/system", timeout=45000),
                page.get_by_role("button", name="健康检查").click(timeout=15000),
                page.locator("table.app-table tbody tr").first.wait_for(timeout=15000),
                _save(page, "02_system_health"),
            ),
        )

        step(
            "UI-03",
            "导航到 回测 并验证空参数错误提示",
            lambda: (
                page.locator("nav.app-nav a", has_text="回测").click(timeout=15000),
                page.wait_for_url("**/backtest", timeout=45000),
                page.get_by_role("button", name="运行回测").click(timeout=15000),
                page.locator("div.bg-rose-50").wait_for(timeout=15000),
                _save(page, "03_backtest_validation"),
            ),
        )

        step(
            "UI-04",
            "导航到 晨会分析 并尝试加载缓存",
            lambda: (
                page.locator("nav.app-nav a", has_text="晨会分析").click(timeout=15000),
                page.wait_for_url("**/morning", timeout=45000),
                page.get_by_role("button", name="用最近缓存").click(timeout=15000),
                page.wait_for_timeout(1200),
                _save(page, "04_morning_cache"),
            ),
        )

        step(
            "UI-05",
            "导航到 投研对话 并确认 iframe 存在",
            lambda: (
                page.locator("nav.app-nav a", has_text="投研对话").click(timeout=15000),
                page.wait_for_url("**/chat", timeout=45000),
                page.locator("iframe").first.wait_for(timeout=15000),
                _save(page, "05_chat_iframe"),
            ),
        )

        step(
            "UI-06",
            "返回 实盘监控 并打开使用说明弹窗",
            lambda: (
                page.locator("nav.app-nav a", has_text="实盘监控").click(timeout=15000),
                page.wait_for_url("**/live/sim", timeout=45000),
                page.get_by_role("button", name="?").first.click(timeout=15000),
                page.get_by_text("实盘监控 -- 使用说明").wait_for(timeout=15000),
                _save(page, "06_live_help"),
            ),
        )

        context.close()
        browser.close()

    print(
        json.dumps(
            {
                "base": BASE,
                "screens": str(OUT_DIR),
                "results": results,
                "bugs": bugs,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    os.environ.setdefault("PWDEBUG", "0")
    run()
