"""
查询回测记录 f5c37fe5-252
"""
import pymysql

conn = pymysql.connect(
    host="127.0.0.1", port=3306,
    user="root", password="huahua1688", database="huahua_trade",
    charset="utf8mb4", connect_timeout=10,
)
try:
    with conn.cursor() as cur:
        # 查找网格交易回测记录
        cur.execute("SELECT backtest_id, strategy_id, stock_code, start_date, end_date, params_json, metrics_json, trades_json, created_at FROM backtest_records WHERE backtest_id LIKE %s", ("%f5c37fe5-252%",))
        for r in cur.fetchall():
            print(f"backtest_id: {r[0]}")
            print(f"strategy_id: {r[1]}")
            print(f"stock_code: {r[2]}")
            print(f"start_date: {r[3]}")
            print(f"end_date: {r[4]}")
            import json
            params = json.loads(r[5]) if r[5] else {}
            print(f"params: {json.dumps(params, ensure_ascii=False, indent=2)}")
            metrics = json.loads(r[6]) if r[6] else {}
            print(f"metrics: {json.dumps(metrics, ensure_ascii=False, indent=2)}")
            trades = json.loads(r[7]) if r[7] else []
            print(f"trades 数量: {len(trades)}")
            if trades:
                for t in trades[:5]:
                    print(f"  {t}")
            print(f"created_at: {r[8]}")

        # 也查找最近5条网格回测
        cur.execute("SELECT backtest_id, stock_code, start_date, end_date, created_at FROM backtest_records WHERE strategy_id='grid_classic' ORDER BY created_at DESC LIMIT 5")
        print("\n最近的网格回测:")
        for r in cur.fetchall():
            print(f"  {r}")
finally:
    conn.close()
