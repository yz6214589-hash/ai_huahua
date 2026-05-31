"""
查询回测记录 f5c37fe5-252 的详细信息
"""
import pymysql, json

conn = pymysql.connect(
    host="bj-cdb-6zjqetya.sql.tencentcdb.com", port=25341,
    user="root", password="huahua1688", database="huahua_trade",
    charset="utf8mb4", connect_timeout=10,
)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM backtest_history WHERE backtest_id LIKE %s", ("%f5c37fe5-252%",))
        row = cur.fetchone()
        if row:
            col_names = [d[0] for d in cur.description]
            print("=== 回测记录 ===")
            for i, v in enumerate(row):
                val = str(v)[:800] if v is not None else "NULL"
                print(f"  {col_names[i]}: {val}")
        else:
            print("未找到 backtest_id 包含 f5c37fe5-252 的记录")
            # 尝试模糊搜索
            cur.execute("SELECT backtest_id, strategy_name, stock_code FROM backtest_history WHERE backtest_id LIKE %s", ("%252%",))
            for r in cur.fetchall():
                print(f"  找到: {r[0]}, {r[1]}, {r[2]}")
finally:
    conn.close()
