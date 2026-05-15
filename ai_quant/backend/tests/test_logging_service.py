"""
日志服务模块测试

测试统一日志服务的核心功能：
- get_logger() 函数
- 日志格式化
- 敏感信息脱敏
- 日志轮转配置
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infra.storage.logging_service import (
    get_logger,
    sanitize,
    sanitize_dict,
    LoggingConfig,
    LoggerManager,
    init_logging,
    shutdown_logging
)


def test_get_logger():
    """测试 get_logger() 函数"""
    logger = get_logger('test_module')
    assert logger is not None
    assert logger.name == 'test_module'
    print("✓ get_logger() 函数测试通过")


def test_log_format():
    """测试日志格式"""
    logger = get_logger('test_format')
    logger.info("测试消息", extra={"key": "value"})

    log_file = Path(__file__).resolve().parents[2] / ".ai_quant" / "logs" / "test_format.log"
    if log_file.exists():
        content = log_file.read_text(encoding="utf-8")
        assert "[test_format]" in content
        assert "INFO" in content
        assert "测试消息" in content
        assert "key=value" in content
        print("✓ 日志格式测试通过")
    else:
        print("⚠ 日志文件不存在，跳过格式测试")


def test_sanitize_api_key():
    """测试 API Key 脱敏"""
    result1 = sanitize("sk-abcdef1234567890")
    assert result1.startswith("sk-")
    assert "****" in result1 or "..." in result1
    assert not "abcdef1234567890" in result1 or result1 == "sk-abcd...7890"

    result2 = sanitize("sk-1234567890abcdef")
    assert result2.startswith("sk-")
    assert "****" in result2 or "..." in result2
    assert not "1234567890abcdef" in result2

    print("✓ API Key 脱敏测试通过")


def test_sanitize_phone():
    """测试手机号脱敏"""
    assert sanitize("13812345678") == "138****5678"
    assert sanitize("18912345678") == "189****5678"
    print("✓ 手机号脱敏测试通过")


def test_sanitize_id_card():
    """测试身份证脱敏"""
    result = sanitize("330101199001011234")
    assert result.startswith("330")
    assert "****" in result
    assert not "330101199001011234" in result
    print("✓ 身份证脱敏测试通过")


def test_sanitize_normal():
    """测试普通字符串不脱敏"""
    assert sanitize("普通文本") == "普通文本"
    assert sanitize("hello world") == "hello world"
    print("✓ 普通字符串脱敏测试通过")


def test_sanitize_dict():
    """测试字典脱敏"""
    data = {
        "api_key": "sk-abcdef1234567890",
        "password": "mypassword123",
        "task_id": "abc123",
        "count": 100
    }
    result = sanitize_dict(data)
    assert result["api_key"] == "******"
    assert result["password"] == "******"
    assert result["task_id"] == "abc123"
    assert result["count"] == 100
    print("✓ 字典脱敏测试通过")


def test_logger_manager_singleton():
    """测试 LoggerManager 单例模式"""
    manager1 = LoggerManager.get_instance()
    manager2 = LoggerManager.get_instance()
    assert manager1 is manager2
    print("✓ LoggerManager 单例模式测试通过")


def test_multiple_loggers():
    """测试多个模块日志实例"""
    logger1 = get_logger('module1')
    logger2 = get_logger('module2')
    assert logger1 is not logger2
    assert logger1.name == 'module1'
    assert logger2.name == 'module2'
    print("✓ 多模块日志实例测试通过")


def test_log_levels():
    """测试不同日志级别"""
    logger = get_logger('test_levels')

    logger.debug("DEBUG 消息", extra={"level": "debug"})
    logger.info("INFO 消息", extra={"level": "info"})
    logger.warning("WARNING 消息", extra={"level": "warning"})
    logger.error("ERROR 消息", extra={"level": "error"})

    print("✓ 不同日志级别测试通过")


def test_structured_logging():
    """测试结构化日志"""
    logger = get_logger('test_structured')

    logger.info("任务执行", extra={
        "task_id": "task_001",
        "status": "success",
        "rows": 100,
        "duration": "2.5s"
    })

    logger.error("任务失败", extra={
        "task_id": "task_002",
        "error": "timeout",
        "traceback": "File xxx, line 100"
    })

    print("✓ 结构化日志测试通过")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始测试日志服务模块")
    print("="*60 + "\n")

    try:
        test_get_logger()
        test_logger_manager_singleton()
        test_multiple_loggers()
        test_log_levels()
        test_structured_logging()
        test_sanitize_api_key()
        test_sanitize_phone()
        test_sanitize_id_card()
        test_sanitize_normal()
        test_sanitize_dict()
        test_log_format()

        print("\n" + "="*60)
        print("所有测试通过!")
        print("="*60 + "\n")

        print("\n生成示例日志文件:")
        print("-" * 60)
        log_dir = Path(__file__).resolve().parents[2] / ".ai_quant" / "logs"
        print(f"日志目录: {log_dir}")
        if log_dir.exists():
            print("日志文件列表:")
            for log_file in sorted(log_dir.glob("*.log")):
                print(f"  - {log_file.name}")
        print("-" * 60 + "\n")

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
