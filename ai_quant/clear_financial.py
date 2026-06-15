#!/usr/bin/env python3
"""清空 trade_stock_financial 表"""

import sys
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from core.db import load_mysql_config
import pymysql

def clear_table():
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4'
    )

    try:
        with conn.cursor() as cursor:
            # 确认清空前数量
            cursor.execute("SELECT COUNT(*) FROM trade_stock_financial")
            before = cursor.fetchone()[0]
            print(f"清空前记录数: {before:,}")

            # 清空表
            cursor.execute("TRUNCATE TABLE trade_stock_financial")

            cursor.execute("SELECT COUNT(*) FROM trade_stock_financial")
            after = cursor.fetchone()[0]
            print(f"清空后记录数: {after:,}")
            print("表已清空")

    finally:
        conn.close()

if __name__ == "__main__":
    clear_table()
