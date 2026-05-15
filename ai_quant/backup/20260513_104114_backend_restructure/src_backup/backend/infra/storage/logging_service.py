"""
统一日志服务模块

本模块提供 AI 量化交易系统的统一日志管理功能，包括：
- 日志实例管理（单例模式）
- 统一日志格式
- 敏感信息脱敏
- 日志轮转配置
- 模块级日志隔离

使用方式：
    from src.backend..infra.storage.logging_service import get_logger

    logger = get_logger('reports')
    logger.info("任务开始", extra={"task_id": "abc123"})
"""

from __future__ import annotations

import logging
import os
import re
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LoggingConfig:
    """
    日志系统配置数据类

    使用 frozen=True 确保配置不可变，保证线程安全

    Attributes:
        log_dir: 日志文件存储目录
        log_level: 日志级别（DEBUG、INFO、WARNING、ERROR、CRITICAL）
        max_bytes: 单个日志文件最大字节数（默认 10MB）
        backup_count: 保留的备份文件数量
        console_enabled: 是否输出到控制台
        file_enabled: 是否输出到文件
        sensitive_fields: 敏感字段列表，用于脱敏
    """
    log_dir: Path
    log_level: str
    max_bytes: int
    backup_count: int
    console_enabled: bool
    file_enabled: bool
    sensitive_fields: tuple[str, ...]


class LoggerManager:
    """
    日志管理器（单例模式）

    负责管理所有模块的日志实例，提供统一的日志配置和管理接口

    Attributes:
        _instance: 单例实例
        _initialized: 是否已初始化
        _loggers: 已创建的日志实例缓存
        _config: 日志配置
    """
    _instance: "LoggerManager | None" = None
    _initialized: bool = False

    def __init__(self):
        """初始化日志管理器"""
        self._loggers: dict[str, logging.Logger] = {}
        self._config: LoggingConfig | None = None

    @classmethod
    def get_instance(cls) -> "LoggerManager":
        """
        获取单例实例

        Returns:
            LoggerManager: 日志管理器单例
        """
        if cls._instance is None:
            cls._instance = LoggerManager()
        return cls._instance

    def initialize(self, config: LoggingConfig) -> None:
        """
        初始化日志系统

        Args:
            config: 日志配置对象
        """
        if self._initialized:
            return

        self._config = config

        if config.file_enabled:
            config.log_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = True

    def get_logger(self, name: str) -> logging.Logger:
        """
        获取指定模块的日志实例

        如果该模块的日志实例不存在，则创建一个新的实例。
        每个模块的日志实例都会配置独立的文件处理器。

        Args:
            name: 模块名称，如 'reports', 'jobs', 'data' 等

        Returns:
            logging.Logger: 配置好的日志实例
        """
        if name in self._loggers:
            return self._loggers[name]

        if self._config is None:
            self.initialize(_load_default_config())

        logger = self._create_logger(name)
        self._loggers[name] = logger
        return logger

    def _create_logger(self, name: str) -> logging.Logger:
        """
        创建指定模块的日志实例

        Args:
            name: 模块名称

        Returns:
            logging.Logger: 新创建的日志实例
        """
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, self._config.log_level.upper(), logging.INFO))
        logger.handlers.clear()

        formatter = UnifiedFormatter()

        if self._config.console_enabled:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        if self._config.file_enabled:
            file_handler = logging.handlers.RotatingFileHandler(
                filename=str(self._config.log_dir / f"{name}.log"),
                maxBytes=self._config.max_bytes,
                backupCount=self._config.backup_count,
                encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        logger.propagate = False
        return logger

    def shutdown(self) -> None:
        """
        关闭日志系统

        关闭所有日志处理器，刷新缓冲区
        """
        for logger in self._loggers.values():
            for handler in logger.handlers:
                handler.close()
                logger.removeHandler(handler)
        self._loggers.clear()
        self._initialized = False


class UnifiedFormatter(logging.Formatter):
    """
    统一日志格式化器

    提供统一的日志格式：
    [时间戳] [模块名] [日志级别] 消息

    支持结构化日志参数输出
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录

        Args:
            record: 日志记录对象

        Returns:
            str: 格式化后的日志字符串
        """
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        module = record.name
        message = record.getMessage()

        extra_info = ""
        if record.args and isinstance(record.args, dict):
            extra_dict = sanitize_dict(record.args)
            if extra_dict:
                parts = [f"{k}={v}" for k, v in extra_dict.items()]
                extra_info = " " + " ".join(parts)

        return f"[{timestamp}] [{module}] [{level}] {message}{extra_info}"


def sanitize(value: str) -> str:
    """
    对敏感信息进行脱敏处理

    支持以下类型的脱敏：
    - API Key: 保留前4位和后4位
    - 手机号: 保留前3位和后4位
    - 身份证: 保留前6位和后4位

    Args:
        value: 需要脱敏的字符串

    Returns:
        str: 脱敏后的字符串
    """
    if not value or not isinstance(value, str):
        return str(value) if value else ""

    original = value

    api_key_patterns = [
        r"(sk-[a-zA-Z0-9]{4})[a-zA-Z0-9]+([a-zA-Z0-9]{4})",
        r"(api[_-]?key['\"]?\s*[:=]\s*['\"]?)([a-zA-Z0-9]{4})[a-zA-Z0-9]+",
    ]
    for pattern in api_key_patterns:
        match = re.search(pattern, original, re.IGNORECASE)
        if match:
            if len(match.groups()) >= 2:
                return f"{match.group(1)}...{match.group(2)}"
            elif len(match.groups()) == 1:
                return f"{match.group(1)}...****"

    phone_pattern = r"(\d{3})\d{4}(\d{4})"
    phone_match = re.search(phone_pattern, original)
    if phone_match:
        return f"{phone_match.group(1)}****{phone_match.group(2)}"

    id_card_pattern = r"(\d{6})\d{7,9}([\dXx])"
    id_match = re.search(id_card_pattern, original)
    if id_match:
        return f"{id_match.group(1)}****{id_match.group(2)}"

    return original


def sanitize_dict(data: dict[str, Any]) -> dict[str, Any]:
    """
    对字典中的敏感字段进行脱敏处理

    Args:
        data: 包含敏感信息的字典

    Returns:
        dict: 脱敏后的字典
    """
    if not data or not isinstance(data, dict):
        return {}

    sensitive_keys = {
        "api_key", "apikey", "api-key", "password", "pwd",
        "secret", "token", "auth", "credential"
    }

    result = {}
    for key, value in data.items():
        if key.lower() in sensitive_keys:
            result[key] = "******"
        elif isinstance(value, str):
            result[key] = sanitize(value)
        elif isinstance(value, (int, float, bool)):
            result[key] = value
        elif value is None:
            result[key] = None
        else:
            result[key] = str(value)

    return result


def _project_root() -> Path:
    """
    获取项目根目录路径

    Returns:
        Path: 项目根目录的 Path 对象
    """
    return Path(__file__).resolve().parents[2]


def _load_default_config() -> LoggingConfig:
    """
    加载默认日志配置

    从环境变量中读取配置，如果未设置则使用默认值

    Returns:
        LoggingConfig: 日志配置对象
    """
    log_dir_env = os.getenv("AI_QUANT_LOG_DIR", "").strip()
    if log_dir_env:
        log_dir = Path(log_dir_env)
    else:
        log_dir = _project_root() / ".ai_quant" / "logs"

    log_level = os.getenv("AI_QUANT_LOG_LEVEL", "INFO").strip().upper()

    max_bytes_env = os.getenv("AI_QUANT_LOG_MAX_BYTES", "10485760").strip()
    try:
        max_bytes = int(max_bytes_env)
    except ValueError:
        max_bytes = 10485760

    backup_count_env = os.getenv("AI_QUANT_LOG_BACKUP_COUNT", "5").strip()
    try:
        backup_count = int(backup_count_env)
    except ValueError:
        backup_count = 5

    console_enabled = os.getenv("AI_QUANT_LOG_CONSOLE", "true").strip().lower() not in ("false", "0", "no")
    file_enabled = os.getenv("AI_QUANT_LOG_FILE", "true").strip().lower() not in ("false", "0", "no")

    sensitive_fields = (
        "api_key", "password", "token", "secret",
        "phone", "mobile", "id_card", "身份证"
    )

    return LoggingConfig(
        log_dir=log_dir,
        log_level=log_level,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console_enabled=console_enabled,
        file_enabled=file_enabled,
        sensitive_fields=sensitive_fields
    )


_manager: LoggerManager | None = None


def get_logger(name: str) -> logging.Logger:
    """
    获取指定模块的日志实例

    这是统一的日志获取接口，各模块应使用此函数获取 logger。
    使用单例模式，确保配置一致。

    Args:
        name: 模块名称，如 'reports', 'jobs', 'data' 等

    Returns:
        logging.Logger: 配置好的日志实例

    Example:
        from src.backend..infra.storage.logging_service import get_logger

        logger = get_logger('reports')
        logger.info("任务开始", extra={"task_id": "abc123"})
        logger.error("任务失败", extra={"error": str(e), "traceback": traceback.format_exc()})
    """
    global _manager
    if _manager is None:
        _manager = LoggerManager.get_instance()
        _manager.initialize(_load_default_config())
    return _manager.get_logger(name)


def init_logging() -> None:
    """
    初始化日志系统

    在应用启动时调用此函数来初始化日志系统。
    通常在 app.py 的 create_app() 函数中调用。
    """
    global _manager
    _manager = LoggerManager.get_instance()
    _manager.initialize(_load_default_config())

    startup_logger = _manager.get_logger("app")
    startup_logger.info("日志系统初始化完成", extra={
        "log_dir": str(_load_default_config().log_dir),
        "log_level": _load_default_config().log_level,
        "console_enabled": _load_default_config().console_enabled,
        "file_enabled": _load_default_config().file_enabled
    })


def shutdown_logging() -> None:
    """
    关闭日志系统

    在应用关闭时调用此函数来关闭日志系统。
    通常在 app.py 的 shutdown 事件中调用。
    """
    global _manager
    if _manager is not None:
        _manager.shutdown()
        _manager = None


import logging.handlers
