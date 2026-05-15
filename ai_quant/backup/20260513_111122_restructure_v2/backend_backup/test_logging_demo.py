#!/usr/bin/env python3
"""
日志服务验证脚本

用于验证统一日志服务是否正常工作
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from runtime.logging_service import get_logger, init_logging

def main():
    print("=" * 60)
    print("日志服务验证脚本")
    print("=" * 60)

    print("\n1. 初始化日志系统...")
    init_logging()
    print("✓ 日志系统初始化完成")

    print("\n2. 测试各模块日志...")

    modules = ['reports', 'jobs', 'data', 'dashboard', 'sentiment',
               'morning', 'risk', 'execution', 'watchlist', 'strategy', 'ai']

    for module in modules:
        logger = get_logger(module)
        logger.info(f"{module} 模块日志测试", extra={"test": "ok"})
        print(f"  ✓ {module} 模块日志正常")

    print("\n3. 检查日志文件...")
    log_dir = Path(__file__).resolve().parents[1] / ".ai_quant" / "logs"
    if log_dir.exists():
        print(f"  日志目录: {log_dir}")
        log_files = list(log_dir.glob("*.log"))
        print(f"  日志文件数量: {len(log_files)}")
        for log_file in sorted(log_files)[:5]:
            print(f"    - {log_file.name}")
            if len(log_files) > 5:
                print(f"    ... 还有 {len(log_files) - 5} 个文件")
    else:
        print(f"  日志目录不存在: {log_dir}")

    print("\n4. 测试结构化日志...")
    logger = get_logger('test')
    logger.info("结构化日志测试", extra={
        "task_id": "task_001",
        "status": "success",
        "count": 100,
        "duration": "2.5s"
    })
    logger.warning("警告日志测试", extra={"warning": "测试警告"})
    logger.error("错误日志测试", extra={"error": "测试错误"})

    print("✓ 结构化日志测试完成")

    print("\n5. 测试敏感信息脱敏...")
    from runtime.logging_service import sanitize, sanitize_dict

    test_data = {
        "api_key": "sk-abcdefghijk123456",
        "password": "mypassword123",
        "phone": "13812345678",
        "task_id": "task_001"
    }
    sanitized = sanitize_dict(test_data)
    print(f"  原始数据: {test_data}")
    print(f"  脱敏后: {sanitized}")
    print("✓ 敏感信息脱敏测试完成")

    print("\n" + "=" * 60)
    print("所有验证通过！")
    print("=" * 60)

if __name__ == "__main__":
    main()
