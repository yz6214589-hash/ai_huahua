"""
应用配置管理模块
负责加载和管理应用程序的所有配置参数，包括应用名称、CORS设置、API密钥和日志配置等
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """
    应用程序配置数据类
    
    使用frozen=True确保配置对象不可变，保证配置的安全性和线程安全性
    
    Attributes:
        app_name: 应用程序名称
        cors_origins: 允许的CORS跨域来源列表
        api_key: API访问密钥，用于接口认证
    """
    app_name: str = "AI Quant Unified API"
    cors_origins: tuple[str, ...] = ("http://localhost:5173",)
    api_key: str = ""


def get_settings() -> Settings:
    """
    获取应用程序配置实例
    
    从环境变量中加载配置，如果环境变量未设置则使用默认值
    支持通过AI_QUANT_CORS_ORIGINS配置多个CORS来源（逗号分隔）
    强制要求CORS配置不能包含通配符*以确保安全性
    
    Returns:
        Settings: 配置对象实例
        
    Raises:
        ValueError: 当CORS来源包含通配符*时抛出异常
    """
    # 从环境变量读取CORS来源配置，支持多个来源用逗号分隔
    raw = os.getenv("AI_QUANT_CORS_ORIGINS", "http://localhost:5173")
    origins = tuple(x.strip() for x in raw.split(",") if x.strip())
    
    # 安全检查：禁止使用通配符配置CORS来源
    if any(x == "*" for x in origins):
        raise ValueError("AI_QUANT_CORS_ORIGINS 不允许包含 *")
    
    # 从环境变量读取API密钥配置
    api_key = str(os.getenv("AI_QUANT_API_KEY", "")).strip()
    
    return Settings(cors_origins=origins or ("http://localhost:5173",), api_key=api_key)


@dataclass(frozen=True)
class LoggingSettings:
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
    """
    log_dir: Path
    log_level: str
    max_bytes: int
    backup_count: int
    console_enabled: bool
    file_enabled: bool


def _project_root() -> Path:
    """
    获取项目根目录路径
    
    Returns:
        Path: 项目根目录的 Path 对象
    """
    return Path(__file__).resolve().parents[2]


def get_logging_settings() -> LoggingSettings:
    """
    获取日志系统配置实例
    
    从环境变量中加载日志配置，如果环境变量未设置则使用默认值
    
    Returns:
        LoggingSettings: 日志配置对象
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
    
    return LoggingSettings(
        log_dir=log_dir,
        log_level=log_level,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console_enabled=console_enabled,
        file_enabled=file_enabled
    )
