import pymysql

conn = pymysql.connect(
    host='bj-cdb-6zjqetya.sql.tencentcdb.com',
    port=25341,
    user='root',
    password='huahua1688',
    database='huahua_trade',
    charset='utf8mb4'
)
cursor = conn.cursor()

def add_column_if_not_exists(table, column, definition):
    cursor.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column)
    )
    exists = cursor.fetchone()[0] > 0
    if exists:
        print(f'  SKIP: {table}.{column} already exists')
        return
    sql = f'ALTER TABLE `{table}` ADD COLUMN `{column}` {definition}'
    try:
        cursor.execute(sql)
        conn.commit()
        print(f'  OK: {table}.{column}')
    except Exception as e:
        conn.rollback()
        print(f'  FAIL: {table}.{column} - {e}')

print('=== 扩展 trade_risk_rule ===')
add_column_if_not_exists('trade_risk_rule', 'trigger_count', 'INT NOT NULL DEFAULT 0 COMMENT "累计触发次数" AFTER `notes`')
add_column_if_not_exists('trade_risk_rule', 'last_trigger_time', 'DATETIME DEFAULT NULL COMMENT "最后触发时间" AFTER `trigger_count`')
add_column_if_not_exists('trade_risk_rule', 'last_trigger_value', 'VARCHAR(100) DEFAULT NULL COMMENT "最后触发时的值" AFTER `last_trigger_time`')
add_column_if_not_exists('trade_risk_rule', 'status', 'ENUM("active", "inactive", "triggered") NOT NULL DEFAULT "active" COMMENT "规则状态" AFTER `last_trigger_value`')
add_column_if_not_exists('trade_risk_rule', 'created_by', 'VARCHAR(64) DEFAULT NULL COMMENT "创建人" AFTER `status`')

print('\n=== 扩展 trade_stock_financial ===')
add_column_if_not_exists('trade_stock_financial', 'operating_margin', 'DECIMAL(10,4) DEFAULT NULL COMMENT "营业利润率(%)" AFTER `psr`')
add_column_if_not_exists('trade_stock_financial', 'quick_ratio', 'DECIMAL(10,4) DEFAULT NULL COMMENT "速动比率" AFTER `operating_margin`')
add_column_if_not_exists('trade_stock_financial', 'total_asset_turnover', 'DECIMAL(10,4) DEFAULT NULL COMMENT "总资产周转率" AFTER `quick_ratio`')
add_column_if_not_exists('trade_stock_financial', 'inventory_turnover', 'DECIMAL(10,4) DEFAULT NULL COMMENT "存货周转率" AFTER `total_asset_turnover`')
add_column_if_not_exists('trade_stock_financial', 'receivables_turnover', 'DECIMAL(10,4) DEFAULT NULL COMMENT "应收账款周转率" AFTER `inventory_turnover`')
add_column_if_not_exists('trade_stock_financial', 'free_cash_flow', 'DECIMAL(20,2) DEFAULT NULL COMMENT "自由现金流(元)" AFTER `receivables_turnover`')
add_column_if_not_exists('trade_stock_financial', 'dividend_yield', 'DECIMAL(10,4) DEFAULT NULL COMMENT "股息率(%)" AFTER `free_cash_flow`')
add_column_if_not_exists('trade_stock_financial', 'ebitda', 'DECIMAL(20,2) DEFAULT NULL COMMENT "息税折旧摊销前利润(元)" AFTER `dividend_yield`')
add_column_if_not_exists('trade_stock_financial', 'ev_ebitda', 'DECIMAL(10,4) DEFAULT NULL COMMENT "EV/EBITDA" AFTER `ebitda`')
add_column_if_not_exists('trade_stock_financial', 'retained_earnings', 'DECIMAL(20,2) DEFAULT NULL COMMENT "留存收益(元)" AFTER `ev_ebitda`')

print('\n=== 扩展 trade_stock_master ===')
add_column_if_not_exists('trade_stock_master', 'sector_code1', 'VARCHAR(20) DEFAULT NULL COMMENT "申万一级行业代码" AFTER `sector_level2`')
add_column_if_not_exists('trade_stock_master', 'sector_code2', 'VARCHAR(20) DEFAULT NULL COMMENT "申万二级行业代码" AFTER `sector_code1`')
add_column_if_not_exists('trade_stock_master', 'total_shares', 'BIGINT DEFAULT NULL COMMENT "总股本" AFTER `sector_code2`')
add_column_if_not_exists('trade_stock_master', 'float_shares', 'BIGINT DEFAULT NULL COMMENT "流通股本" AFTER `total_shares`')

print('\n=== 验证扩展字段 ===')
cursor.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = 'trade_stock_financial' "
    "AND column_name IN ('operating_margin','quick_ratio','total_asset_turnover','free_cash_flow','dividend_yield','ebitda','ev_ebitda','retained_earnings')"
)
print(f'trade_stock_financial 新增字段: {[r[0] for r in cursor.fetchall()]}')

cursor.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = 'trade_risk_rule' "
    "AND column_name IN ('trigger_count','last_trigger_time','last_trigger_value','status','created_by')"
)
print(f'trade_risk_rule 新增字段: {[r[0] for r in cursor.fetchall()]}')

cursor.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = 'trade_stock_master' "
    "AND column_name IN ('sector_code1','sector_code2','total_shares','float_shares')"
)
print(f'trade_stock_master 新增字段: {[r[0] for r in cursor.fetchall()]}')

conn.close()
print('\n扩展字段迁移完成!')
