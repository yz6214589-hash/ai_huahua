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

cursor.execute('SHOW TABLES')
tables = [t[0] for t in cursor.fetchall()]

with open('/Users/apple/Desktop/ai_huahua/ai_quant/current_schema.txt', 'w') as f:
    for table_name in tables:
        cursor.execute(f'SHOW CREATE TABLE `{table_name}`')
        result = cursor.fetchone()
        f.write(f'=== {table_name} ===\n')
        f.write(result[1])
        f.write('\n\n')

conn.close()
print('Done! Schema saved to current_schema.txt')
