#!/usr/bin/env python3
"""
HTTP 日志中间件测试脚本

用于测试 HTTP 日志中间件是否正常工作
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from ai_quant_api.app import create_app

def main():
    print("=" * 60)
    print("HTTP 日志中间件测试")
    print("=" * 60)

    print("\n1. 创建应用实例...")
    app = create_app()
    client = TestClient(app)
    print("✓ 应用实例创建成功")

    print("\n2. 测试健康检查端点...")
    response = client.get("/health")
    print(f"  状态码: {response.status_code}")
    print("✓ 健康检查请求完成")

    print("\n3. 测试根路径端点...")
    response = client.get("/")
    print(f"  状态码: {response.status_code}")
    print("✓ 根路径请求完成")

    print("\n4. 测试不存在的端点...")
    response = client.get("/api/nonexistent")
    print(f"  状态码: {response.status_code}")
    print("✓ 不存在端点请求完成")

    print("\n5. 等待日志写入...")
    import time
    time.sleep(0.5)

    print("\n6. 检查 HTTP 日志文件...")
    log_file = Path(__file__).resolve().parents[1] / ".ai_quant" / "logs" / "http.log"
    if log_file.exists():
        print(f"  ✓ 日志文件存在: {log_file}")
        content = log_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        print(f"  ✓ 日志行数: {len(lines)}")

        print("\n  最近 5 条日志:")
        for line in lines[-5:]:
            print(f"    {line}")
    else:
        print(f"  ⚠ 日志文件不存在: {log_file}")

    print("\n" + "=" * 60)
    print("HTTP 日志中间件测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
