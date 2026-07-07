"""
Playwright 浏览器自动化配置管理模块

本模块提供 Playwright 浏览器环境的持久化配置管理，确保所有浏览器自动化操作
统一使用 Playwright 作为主要控制程序（MCP），避免每次执行自动化任务时重新安装浏览器。

功能包括：
- 首次运行时检查 Playwright 浏览器是否已安装
- 如未安装，自动执行安装程序并指定明确的安装目录
- 将已安装的浏览器路径持久化保存到系统配置中
- 后续所有自动化任务使用已配置的浏览器路径，禁止重复安装
- 提供浏览器路径的环境变量导出，确保系统环境可访问
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


@dataclass
class PlaywrightConfig:
    """
    Playwright 浏览器配置数据类

    存储 Playwright 浏览器的安装路径和相关配置信息，用于持久化记录
    浏览器安装状态，避免重复安装。

    Attributes:
        browsers_installed: 浏览器是否已安装
        install_path: Playwright 浏览器安装根目录
        chromium_path: Chromium 浏览器可执行文件路径
        firefox_path: Firefox 浏览器可执行文件路径
        webkit_path: WebKit 浏览器可执行文件路径
        version: Playwright 版本号
        install_timestamp: 安装时间戳
    """
    browsers_installed: bool = False
    install_path: str = ""
    chromium_path: str = ""
    firefox_path: str = ""
    webkit_path: str = ""
    version: str = ""
    install_timestamp: str = ""


def _project_root() -> Path:
    """
    获取项目根目录路径

    Returns:
        Path: 项目根目录的 Path 对象
    """
    return Path(__file__).resolve().parents[2]


def _config_dir() -> Path:
    """
    获取 Playwright 配置存储目录

    在 .ai_quant 目录下创建 playwright 子目录用于存储配置信息

    Returns:
        Path: 配置目录路径
    """
    config_path = _project_root() / ".ai_quant" / "playwright"
    config_path.mkdir(parents=True, exist_ok=True)
    return config_path


def _config_file_path() -> Path:
    """
    获取 Playwright 配置文件路径

    Returns:
        Path: 配置文件的完整路径
    """
    return _config_dir() / "config.json"


def _get_default_playwright_browsers_path() -> Path:
    """
    获取 Playwright 浏览器默认安装路径

    根据操作系统确定 Playwright 浏览器的默认安装目录：
    - macOS: ~/Library/Caches/ms-playwright
    - Linux: ~/.cache/ms-playwright
    - Windows: %USERPROFILE%\\AppData\\Local\\ms-playwright

    Returns:
        Path: 默认的 Playwright 浏览器安装目录
    """
    home = Path.home()
    if sys.platform == "darwin":
        return home / "Library" / "Caches" / "ms-playwright"
    elif sys.platform == "win32":
        return Path(os.environ.get("USERPROFILE", str(home))) / "AppData" / "Local" / "ms-playwright"
    else:
        return home / ".cache" / "ms-playwright"


def _get_playwright_version() -> str:
    """
    获取当前安装的 Playwright 版本

    尝试通过 pip show 命令获取 Playwright 的版本信息

    Returns:
        str: Playwright 版本号，如果获取失败返回空字符串
    """
    try:
        import playwright
        return getattr(playwright, "__version__", "")
    except ImportError:
        pass
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "playwright"],
            capture_output=True, text=True, timeout=30
        )
        for line in result.stdout.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return ""


def _find_chromium_path(browsers_path: Path) -> Optional[str]:
    """
    在 Playwright 浏览器目录中查找 Chromium 浏览器可执行文件

    遍历 ms-playwright 目录下的 chromium 相关子目录，查找可执行文件

    Args:
        browsers_path: Playwright 浏览器安装根目录

    Returns:
        Optional[str]: Chromium 浏览器可执行文件路径，未找到则返回 None
    """
    if not browsers_path.exists():
        return None
    for item in browsers_path.iterdir():
        if not item.is_dir():
            continue
        name_lower = item.name.lower()
        if "chromium" in name_lower:
            chrome_path = _find_chrome_app_in_dir(item)
            if chrome_path:
                return chrome_path
    return None


def _find_firefox_path(browsers_path: Path) -> Optional[str]:
    """
    在 Playwright 浏览器目录中查找 Firefox 浏览器可执行文件

    Args:
        browsers_path: Playwright 浏览器安装根目录

    Returns:
        Optional[str]: Firefox 浏览器可执行文件路径，未找到则返回 None
    """
    if not browsers_path.exists():
        return None
    for item in browsers_path.iterdir():
        if not item.is_dir():
            continue
        name_lower = item.name.lower()
        if "firefox" in name_lower:
            if sys.platform == "darwin":
                ff_path = item / "firefox" / "firefox"
                if ff_path.exists():
                    return str(ff_path)
            else:
                ff_path = item / "firefox"
                if ff_path.exists():
                    return str(ff_path)
    return None


def _find_webkit_path(browsers_path: Path) -> Optional[str]:
    """
    在 Playwright 浏览器目录中查找 WebKit 浏览器可执行文件

    Args:
        browsers_path: Playwright 浏览器安装根目录

    Returns:
        Optional[str]: WebKit 浏览器可执行文件路径，未找到则返回 None
    """
    if not browsers_path.exists():
        return None
    for item in browsers_path.iterdir():
        if not item.is_dir():
            continue
        name_lower = item.name.lower()
        if "webkit" in name_lower:
            if sys.platform == "darwin":
                wk_path = item / "pw_run.sh"
                if not wk_path.exists():
                    wk_path = item / "Playwright.app" / "Contents" / "MacOS" / "Playwright"
                if wk_path.exists():
                    return str(wk_path)
            else:
                wk_path = item / "pw_run.sh"
                if wk_path.exists():
                    return str(wk_path)
    return None


def _find_chrome_app_in_dir(directory: Path) -> Optional[str]:
    """
    在指定目录中查找 Chrome/Chromium 可执行文件

    根据操作系统类型查找对应的可执行文件路径

    Args:
        directory: 要搜索的目录

    Returns:
        Optional[str]: Chrome 可执行文件路径，未找到则返回 None
    """
    if sys.platform == "darwin":
        chrome_app = directory / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        if chrome_app.exists():
            return str(chrome_app)
        chrome_app = directory / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        if chrome_app.exists():
            return str(chrome_app)
        chrome_app = directory / "chrome" / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        if chrome_app.exists():
            return str(chrome_app)
    elif sys.platform == "win32":
        chrome_exe = directory / "chrome" / "win32" / "chrome.exe"
        if chrome_exe.exists():
            return str(chrome_exe)
        chrome_exe = directory / "chrome-win" / "chrome.exe"
        if chrome_exe.exists():
            return str(chrome_exe)
    else:
        chrome_bin = directory / "chrome" / "linux" / "chrome"
        if chrome_bin.exists():
            return str(chrome_bin)
        chrome_bin = directory / "chrome-linux" / "chrome"
        if chrome_bin.exists():
            return str(chrome_bin)
    return None


def check_browsers_installed(browsers_path: Optional[Path] = None) -> bool:
    """
    检查 Playwright 浏览器是否已安装

    通过检查默认安装目录是否存在且包含浏览器文件来判断

    Args:
        browsers_path: Playwright 浏览器安装路径，如果为 None 则使用默认路径

    Returns:
        bool: 浏览器是否已安装
    """
    if browsers_path is None:
        browsers_path = _get_default_playwright_browsers_path()
    if not browsers_path.exists():
        return False
    has_browsers = False
    for item in browsers_path.iterdir():
        if item.is_dir():
            has_browsers = True
            break
    return has_browsers


def install_browsers(install_path: Optional[Path] = None) -> bool:
    """
    安装 Playwright 浏览器

    如果浏览器尚未安装，自动执行 Playwright 的浏览器安装程序。
    支持指定安装目录，安装完成后会更新持久化配置。

    Args:
        install_path: 浏览器安装路径，如果为 None 则使用默认路径

    Returns:
        bool: 安装是否成功

    Raises:
        RuntimeError: 当安装过程中发生错误时抛出
    """
    try:
        logger = _get_logger()
        logger("正在检查 Playwright 浏览器安装状态...")
    except Exception:
        pass

    if check_browsers_installed(install_path):
        try:
            logger = _get_logger()
            logger("Playwright 浏览器已安装，跳过安装步骤")
        except Exception:
            pass
        return True

    browsers_path = install_path if install_path else _get_default_playwright_browsers_path()
    browsers_path.mkdir(parents=True, exist_ok=True)

    try:
        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)

        try:
            logger = _get_logger()
            logger(f"正在安装 Playwright 浏览器到: {browsers_path}")
        except Exception:
            pass
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--with-deps"],
            capture_output=True, text=True, timeout=600,
            env=env
        )
        if result.returncode != 0:
            error_msg = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f"Playwright 浏览器安装失败: {error_msg}")

        try:
            logger = _get_logger()
            logger("Playwright 浏览器安装完成")
        except Exception:
            pass

        _save_config(browsers_path)
        return True

    except subprocess.TimeoutExpired:
        raise RuntimeError("Playwright 浏览器安装超时（600秒）")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Playwright 浏览器安装过程发生异常: {e}")


def _save_config(browsers_path: Path) -> None:
    """
    保存 Playwright 浏览器配置到持久化文件

    自动检测已安装的浏览器路径并保存到配置文件中，
    同时记录 Playwright 版本和安装时间信息。

    Args:
        browsers_path: Playwright 浏览器安装根目录
    """
    from datetime import datetime
    config = PlaywrightConfig(
        browsers_installed=True,
        install_path=str(browsers_path),
        chromium_path=_find_chromium_path(browsers_path) or "",
        firefox_path=_find_firefox_path(browsers_path) or "",
        webkit_path=_find_webkit_path(browsers_path) or "",
        version=_get_playwright_version(),
        install_timestamp=datetime.now().isoformat()
    )
    config_file = _config_file_path()
    config_file.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> PlaywrightConfig:
    """
    加载 Playwright 浏览器配置

    从持久化配置文件中读取浏览器安装信息。
    如果配置文件不存在或已损坏，返回默认配置。

    Returns:
        PlaywrightConfig: Playwright 浏览器配置对象
    """
    config_file = _config_file_path()
    if not config_file.exists():
        return PlaywrightConfig()
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
        return PlaywrightConfig(**data)
    except (json.JSONDecodeError, TypeError, KeyError):
        return PlaywrightConfig()


def get_browser_executable_path(browser_type: str = "chromium") -> Optional[str]:
    """
    获取指定类型浏览器的可执行文件路径

    从持久化配置中读取浏览器路径。如果尚未安装，会自动触发安装流程。
    支持三种浏览器类型：chromium、firefox、webkit。

    Args:
        browser_type: 浏览器类型，可选值为 "chromium"、"firefox"、"webkit"，默认 "chromium"

    Returns:
        Optional[str]: 浏览器可执行文件路径，如果获取失败返回 None
    """
    config = load_config()
    if not config.browsers_installed:
        try:
            install_browsers()
            config = load_config()
        except RuntimeError:
            return None

    browser_map = {
        "chromium": config.chromium_path,
        "firefox": config.firefox_path,
        "webkit": config.webkit_path,
    }
    return browser_map.get(browser_type)


def ensure_playwright_ready() -> PlaywrightConfig:
    """
    确保 Playwright 浏览器环境就绪

    一站式初始化函数，检查浏览器安装状态，必要时自动安装，
    并确保浏览器路径在系统环境中可访问。
    此函数应在应用启动时或首次使用 Playwright 前调用。

    Returns:
        PlaywrightConfig: 初始化后的 Playwright 配置对象

    Raises:
        RuntimeError: 当浏览器安装失败且无法恢复时抛出
    """
    config = load_config()

    if config.browsers_installed:
        browsers_path = Path(config.install_path) if config.install_path else _get_default_playwright_browsers_path()
        browsers_path.mkdir(parents=True, exist_ok=True)
        if config.install_path:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = config.install_path
        return config

    browsers_path = _get_default_playwright_browsers_path()
    if check_browsers_installed(browsers_path):
        _save_config(browsers_path)
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_path)
        return load_config()

    install_browsers(browsers_path)
    config = load_config()
    if config.install_path:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = config.install_path
    return config


def verify_browser_accessibility() -> dict:
    """
    验证浏览器路径在系统环境中的可访问性

    检查所有已安装的浏览器路径是否仍然有效（文件存在），
    并验证 PLAYWRIGHT_BROWSERS_PATH 环境变量是否已正确设置。

    Returns:
        dict: 验证结果字典，包含以下键：
            - all_accessible: bool，是否所有浏览器都可访问
            - environment_set: bool，环境变量是否已设置
            - browsers_path: str，浏览器安装根目录
            - details: list[dict]，每个浏览器的详细验证结果
    """
    config = load_config()
    browsers_path = config.install_path if config.install_path else str(_get_default_playwright_browsers_path())

    details = []
    all_accessible = True

    if config.chromium_path:
        accessible = Path(config.chromium_path).exists()
        details.append({
            "browser": "chromium",
            "path": config.chromium_path,
            "accessible": accessible
        })
        if not accessible:
            all_accessible = False

    if config.firefox_path:
        accessible = Path(config.firefox_path).exists()
        details.append({
            "browser": "firefox",
            "path": config.firefox_path,
            "accessible": accessible
        })
        if not accessible:
            all_accessible = False

    if config.webkit_path:
        accessible = Path(config.webkit_path).exists()
        details.append({
            "browser": "webkit",
            "path": config.webkit_path,
            "accessible": accessible
        })
        if not accessible:
            all_accessible = False

    env_set = "PLAYWRIGHT_BROWSERS_PATH" in os.environ

    return {
        "all_accessible": all_accessible,
        "environment_set": env_set,
        "browsers_path": browsers_path,
        "version": config.version,
        "install_timestamp": config.install_timestamp,
        "details": details
    }


def _get_logger():
    """
    获取日志记录器实例

    尝试从日志服务模块获取日志实例，如果获取失败则使用简单的 print 输出

    Returns:
        callable: 日志输出函数
    """
    try:
        from infra.storage.logging_service import get_logger
        return get_logger("playwright_setup").info
    except Exception:
        return print
