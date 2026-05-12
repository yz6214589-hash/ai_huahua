#!/usr/bin/env python3
"""
应用日志集成验证脚本

用于验证日志系统是否正确集成到应用中
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_quant_api.app import create_app

def main():
    print("=" * 60)
    print("应用日志集成验证")
    print("=" * 60)

    print("\n1. 创建应用实例...")
    app = create_app()
    print("✓ 应用实例创建成功")

    print("\n2. 验证路由...")
    routes = [route.path for route in app.routes]
    print(f"  路由数量: {len(routes)}")
    print(f"  包含 /api/health: {'/api/health' in routes}")
    print(f"  包含 /api/reports: {'/api/reports' in routes}")
    print(f"  包含 /api/jobs: {'/api/jobs' in routes}")
    print("✓ 路由验证完成")

    print("\n3. 检查日志文件...")
    log_file = Path(__file__).resolve().parents[1] / ".ai_quant" / "logs" / "app.log"
    if log_file.exists():
        print(f"  日志文件: {log_file}")
        content = log_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        print(f"  日志行数: {len(lines)}")

        print("\n  最近 10 条日志:")
        for line in lines[-10:]:
            print(f"    {line}")
        print("✓ 日志文件检查完成")
    else:
        print(f"  ⚠ 日志文件不存在: {log_file}")

    print("\n" + "=" * 60)
    print("应用日志集成验证完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
