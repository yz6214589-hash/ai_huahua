"""检查因子数据质量"""
import pymysql
from backend.core.db import load_mysql_config
cfg = load_mysql_config()
conn = pymysql.connect(host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password,
                       database=cfg.database, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()

cur.execute("SELECT COUNT(DISTINCT stock_code) as cnt FROM trade_stock_financial")
total = cur.fetchone()["cnt"]
print(f"financial表去重股票总数: {total}")

factors = ["pe_ttm","pb","roe","gross_margin","revenue_growth_yoy","profit_growth_yoy","debt_ratio"]
for f in factors:
    cur.execute(f"SELECT COUNT(DISTINCT stock_code) as cnt FROM trade_stock_financial WHERE {f} IS NOT NULL")
    c = cur.fetchone()["cnt"]
    print(f"  {f:25} 非空: {c:>5} 只 ({c*100//total}%)")

where = " AND ".join([f"{f} IS NOT NULL" for f in factors])
cur.execute(f"SELECT COUNT(DISTINCT stock_code) as cnt FROM trade_stock_financial WHERE {where}")
c = cur.fetchone()["cnt"]
print(f"\n7个因子全部非空: {c} 只")

# 看看如果去掉profit_growth_yoy（因为次新股常缺同比），结果如何
subset = [f for f in factors if f != "profit_growth_yoy"]
where2 = " AND ".join([f"{f} IS NOT NULL" for f in subset])
cur.execute(f"SELECT COUNT(DISTINCT stock_code) as cnt FROM trade_stock_financial WHERE {where2}")
c2 = cur.fetchone()["cnt"]
print(f"去掉利润增速后6因子全部非空: {c2} 只")

# 再验证下前端默认因子配置
print("\n前端默认因子（前7个）：")
print("  pe -> pe_ttm, pb -> pb, roe -> roe")
print("  gross_margin -> gross_margin, revenue_growth -> revenue_growth_yoy")
print("  profit_growth -> profit_growth_yoy, debt_ratio -> debt_ratio")

# 默认权重
default_factors = ["pe_ttm","pb","roe","gross_margin","revenue_growth_yoy","profit_growth_yoy","debt_ratio"]
where3 = " AND ".join([f"{f} IS NOT NULL" for f in default_factors])
cur.execute(f"SELECT COUNT(DISTINCT stock_code) as cnt FROM trade_stock_financial WHERE {where3}")
c3 = cur.fetchone()["cnt"]
print(f"\n前端默认的7个因子全部非空: {c3} 只")

conn.close()
