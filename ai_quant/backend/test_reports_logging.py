#!/usr/bin/env python3
"""
reports 模块日志测试脚本

用于测试 reports 模块的日志功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.logging_service import get_logger

def main():
    print("=" * 60)
    print("reports 模块日志测试")
    print("=" * 60)

    print("\n1. 获取 reports 模块日志实例...")
    logger = get_logger('reports')
    print(f"  ✓ Logger name: {logger.name}")
    print(f"  ✓ Logger level: {logger.level}")

    print("\n2. 测试 INFO 级别日志...")
    logger.info("任务创建", extra={
        "task_id": "test_task_001",
        "model": "qwen-max",
        "stocks_count": 3
    })
    print("  ✓ INFO 日志发送成功")

    print("\n3. 测试 WARNING 级别日志...")
    logger.warning("LLM 未启用", extra={
        "model": "qwen-max",
        "stock_code": "600000"
    })
    print("  ✓ WARNING 日志发送成功")

    print("\n4. 测试 ERROR 级别日志...")
    logger.error("任务执行失败", extra={
        "task_id": "test_task_002",
        "error": "timeout",
        "error_location": "reports.py:456"
    })
    print("  ✓ ERROR 日志发送成功")

    print("\n5. 测试 DEBUG 级别日志...")
    logger.debug("LLM 调用开始", extra={
        "model": "qwen-max",
        "stock_code": "600000"
    })
    print("  ✓ DEBUG 日志发送成功")

    print("\n6. 检查日志文件...")
    log_file = Path(__file__).resolve().parents[1] / ".ai_quant" / "logs" / "reports.log"
    if log_file.exists():
        print(f"  ✓ 日志文件存在: {log_file}")
        content = log_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        print(f"  ✓ 日志行数: {len(lines)}")

        print("\n  最近 5 条日志:")
        for line in lines[-5:]:
            print(f"    {line}")
    else:
        print(f"  ✗ 日志文件不存在: {log_file}")

    print("\n" + "=" * 60)
    print("reports 模块日志测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
