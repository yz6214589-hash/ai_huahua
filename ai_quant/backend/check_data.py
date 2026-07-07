from core.db import load_mysql_config
import pymysql

cfg = load_mysql_config()
conn = pymysql.connect(host=cfg.host, port=cfg.port, user=cfg.user, password=cfg.password, database=cfg.database, charset='utf8mb4')
cursor = conn.cursor()

# 统计数据来源
cursor.execute('SELECT data_source, COUNT(*) as cnt FROM trade_stock_financial GROUP BY data_source')
rows = cursor.fetchall()
print('数据来源统计:')
for row in rows:
    print('  {}: {} 条记录'.format(row[0], row[1]))

# 查询泽璟制药数据
cursor.execute('SELECT f.report_date, f.roe, f.gross_margin, f.pe_ttm, f.revenue_growth_yoy, f.profit_growth_yoy, f.data_source FROM trade_stock_financial f WHERE f.stock_code=%s ORDER BY f.report_date DESC LIMIT 3', ('688266.SH',))
rows = cursor.fetchall()
print()
print('泽璟制药(688266.SH)最新3条数据:')
print('-' * 90)
print('{:<12} {:<10} {:<12} {:<8} {:<12} {:<12} {}'.format('报告日期', 'ROE(%)', '毛利率(%)', 'PE', '营收增速(%)', '利润增速(%)', '数据源'))
print('-' * 90)
for row in rows:
    print('{:<12} {:<10.2f} {:<12.2f} {:<8.2f} {:<12.2f} {:<12.2f} {}'.format(row[0], row[1], row[2], row[3], row[4], row[5], row[6]))

conn.close()