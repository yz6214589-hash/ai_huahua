#!/usr/bin/env python3
"""
日志系统综合测试脚本

验证整个日志系统的完整性和功能
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def test_logging_service():
    """测试日志服务核心功能"""
    print("\n1. 测试日志服务核心功能...")

    from runtime.logging_service import get_logger, init_logging, sanitize, sanitize_dict

    init_logging()

    logger = get_logger("test")
    assert logger is not None
    assert logger.name == "test"

    logger.info("测试消息", extra={"key": "value"})

    assert sanitize("sk-abcdef1234567890") != "sk-abcdef1234567890"
    assert sanitize("13812345678") == "138****5678"

    data = {"api_key": "sk-test1234567890", "password": "secret"}
    result = sanitize_dict(data)
    assert result["api_key"] == "******"
    assert result["password"] == "******"

    print("  ✓ 日志服务核心功能测试通过")


def test_all_modules():
    """测试所有业务模块的日志"""
    print("\n2. 测试所有业务模块...")

    from runtime.logging_service import get_logger

    modules = [
        'dashboard', 'reports', 'data', 'jobs', 'sentiment',
        'morning', 'risk', 'execution', 'watchlist', 'strategy', 'ai', 'http'
    ]

    for module in modules:
        logger = get_logger(module)
        logger.info(f"{module} 模块日志测试")
        print(f"  ✓ {module} 模块")

    print("  ✓ 所有业务模块日志测试通过")


def test_http_logging():
    """测试 HTTP 日志中间件"""
    print("\n3. 测试 HTTP 日志中间件...")

    from fastapi.testclient import TestClient
    from app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")
    assert response.status_code == 200

    response = client.get("/nonexistent")
    assert response.status_code == 404

    print("  ✓ HTTP 日志中间件测试通过")


def test_logs_api():
    """测试日志查询 API"""
    print("\n4. 测试日志查询 API...")

    from fastapi.testclient import TestClient
    from app import create_app

    app = create_app()
    client = TestClient(app)

    response = client.get("/api/logs/stats")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert data["summary"]["total"] > 0

    response = client.get("/api/logs?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data["logs"]) <= 10

    response = client.get("/api/logs?module=reports&limit=5")
    assert response.status_code == 200

    print("  ✓ 日志查询 API 测试通过")


def test_log_files():
    """测试日志文件生成"""
    print("\n5. 测试日志文件生成...")

    log_dir = Path(__file__).resolve().parent / ".ai_quant" / "logs"
    if not log_dir.exists():
        log_dir = Path(__file__).resolve().parents[1] / ".ai_quant" / "logs"

    assert log_dir.exists(), f"日志目录不存在: {log_dir}"

    log_files = list(log_dir.glob("*.log"))
    assert len(log_files) > 0

    modules = ['app.log', 'reports.log', 'jobs.log', 'http.log']
    for module_log in modules:
        log_file = log_dir / module_log
        if log_file.exists():
            content = log_file.read_text(encoding="utf-8")
            assert len(content) > 0
            print(f"  ✓ {module_log} 文件正常")

    print("  ✓ 日志文件生成测试通过")


def test_log_rotation():
    """测试日志轮转配置"""
    print("\n6. 测试日志轮转配置...")

    from runtime.logging_service import get_logger
    from config import get_logging_settings

    config = get_logging_settings()
    assert config.max_bytes == 10485760  # 10MB
    assert config.backup_count == 5
    assert config.file_enabled == True

    logger = get_logger("rotation_test")
    for i in range(100):
        logger.info(f"轮转测试消息 {i}")

    print("  ✓ 日志轮转配置测试通过")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("日志系统综合测试")
    print("=" * 60)

    try:
        test_logging_service()
        test_all_modules()
        test_http_logging()
        test_logs_api()
        test_log_files()
        test_log_rotation()

        print("\n" + "=" * 60)
        print("所有综合测试通过！")
        print("=" * 60)

        print("\n日志系统功能总结:")
        print("-" * 60)

        log_dir = Path(__file__).resolve().parents[1] / ".ai_quant" / "logs"
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            print(f"日志文件总数: {len(log_files)}")

            total_size = sum(f.stat().st_size for f in log_files)
            print(f"日志总大小: {total_size / 1024:.2f} KB")

            modules = {}
            for f in log_files:
                if f.stat().st_size > 0:
                    modules[f.stem] = f.stat().st_size

            if modules:
                print("\n各模块日志大小:")
                for name, size in sorted(modules.items(), key=lambda x: x[1], reverse=True)[:10]:
                    print(f"  {name}: {size / 1024:.2f} KB")

        print("-" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
