"""
查询600519.SH的数据和回测记录
"""
import pymysql

conn = pymysql.connect(
    host="bj-cdb-6zjqetya.sql.tencentcdb.com", port=25341,
    user="root", password="huahua1688", database="huahua_trade",
    charset="utf8mb4", connect_timeout=10,
)
try:
    with conn.cursor() as cur:
        # 查询600519.SH的数据量
        cur.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM trade_stock_daily WHERE stock_code='600519.SH'")
        r = cur.fetchone()
        print(f"600519.SH 数据: {r[2]} 行, 从 {r[0]} 到 {r[1]}")

        # 查找 backtest_records 表结构
        cur.execute("DESCRIBE backtest_records")
        cols = [d[0] for d in cur.fetchall()]
        print(f"\nbacktest_records 列: {cols}")

        # 查找ID包含252的记录
        cur.execute("SELECT * FROM backtest_records WHERE id LIKE %s OR strategy_id LIKE %s OR stock_code LIKE %s",
                     ("%252%", "%252%", "%252%"))
        rows = cur.fetchall()
        print(f"\n包含252的记录数: {len(rows)}")
        for r in rows:
            print(f"  {r}")

        if len(rows) == 0:
            # 查找最近的回测记录
            cur.execute("SELECT * FROM backtest_records ORDER BY id DESC LIMIT 5")
            for r in cur.fetchall():
                print(f"  最近: {r}")
finally:
    conn.close()
