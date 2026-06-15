#!/usr/bin/env python3
"""备份 trade_stock_financial 表数据（分批插入）"""

import sys
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from core.db import load_mysql_config
import pymysql
from datetime import datetime

def backup_data():
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4'
    )

    try:
        with conn.cursor() as cursor:
            backup_table = f"trade_stock_financial_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"创建备份表: {backup_table}")

            # 1. 创建同结构空表
            cursor.execute(f"CREATE TABLE {backup_table} LIKE trade_stock_financial")
            print("表结构创建成功")

            # 2. 统计总数
            cursor.execute("SELECT COUNT(*) FROM trade_stock_financial")
            total = cursor.fetchone()[0]
            print(f"原表总记录数: {total:,}")

            # 3. 分批插入（每批 5000 条）
            batch_size = 5000
            inserted = 0
            offset = 0

            while offset < total:
                end = min(offset + batch_size, total)
                cursor.execute(
                    f"INSERT INTO {backup_table} SELECT * FROM trade_stock_financial LIMIT %s OFFSET %s",
                    (batch_size, offset)
                )
                inserted += cursor.rowcount
                conn.commit()
                print(f"  已备份 {inserted:,}/{total:,} 条")
                offset = end

            print(f"\n备份完成: {inserted:,} 条记录")
            print(f"备份表名: {backup_table}")

    finally:
        conn.close()

if __name__ == "__main__":
    backup_data()
