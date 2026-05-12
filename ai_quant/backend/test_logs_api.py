#!/usr/bin/env python3
"""
日志查询 API 测试脚本

用于测试日志查询和统计接口
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from ai_quant_api.app import create_app

def main():
    print("=" * 60)
    print("日志查询 API 测试")
    print("=" * 60)

    print("\n1. 创建应用实例...")
    app = create_app()
    client = TestClient(app)
    print("✓ 应用实例创建成功")

    print("\n2. 测试日志统计接口...")
    response = client.get("/api/logs/stats")
    assert response.status_code == 200
    data = response.json()
    print(f"  状态码: {response.status_code}")
    print(f"  总日志数: {data['summary']['total']}")
    print(f"  文件数: {data['files_count']}")
    print(f"  磁盘使用: {data['disk_usage']['total_mb']} MB")
    if data['summary']['by_module']:
        print(f"  模块分布: {list(data['summary']['by_module'].keys())[:5]}")
    print("✓ 日志统计接口测试通过")

    print("\n3. 测试日志文件列表接口...")
    response = client.get("/api/logs/files")
    assert response.status_code == 200
    data = response.json()
    print(f"  状态码: {response.status_code}")
    print(f"  文件总数: {data['total_files']}")
    if data['files']:
        print(f"  示例文件: {data['files'][0]['name']}")
    print("✓ 日志文件列表接口测试通过")

    print("\n4. 测试日志查询接口（全部）...")
    response = client.get("/api/logs?limit=5")
    assert response.status_code == 200
    data = response.json()
    print(f"  状态码: {response.status_code}")
    print(f"  返回日志数: {len(data['logs'])}")
    print(f"  总日志数: {data['total']}")
    if data['logs']:
        log = data['logs'][0]
        print(f"  最新日志: [{log['timestamp']}] [{log['module']}] [{log['level']}] {log['message'][:50]}")
    print("✓ 日志查询接口（全部）测试通过")

    print("\n5. 测试日志查询接口（按模块过滤）...")
    response = client.get("/api/logs?module=reports&limit=3")
    assert response.status_code == 200
    data = response.json()
    print(f"  状态码: {response.status_code}")
    print(f"  返回日志数: {len(data['logs'])}")
    print(f"  总日志数: {data['total']}")
    print("✓ 日志查询接口（按模块）测试通过")

    print("\n6. 测试日志查询接口（按级别过滤）...")
    response = client.get("/api/logs?level=ERROR&limit=3")
    assert response.status_code == 200
    data = response.json()
    print(f"  状态码: {response.status_code}")
    print(f"  返回日志数: {len(data['logs'])}")
    print(f"  总日志数: {data['total']}")
    print("✓ 日志查询接口（按级别）测试通过")

    print("\n" + "=" * 60)
    print("所有日志 API 测试通过！")
    print("=" * 60)

if __name__ == "__main__":
    main()
