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

with open('/Users/apple/Desktop/ai_huahua/ai_quant/backend/migrations/010_unified_migration.sql', 'r', encoding='utf-8') as f:
    sql_content = f.read()

sql_statements = []
current = []
for line in sql_content.split('\n'):
    stripped = line.strip()
    if stripped.startswith('--') or stripped == '':
        continue
    current.append(line)
    if stripped.endswith(';'):
        stmt = '\n'.join(current)
        stmt = stmt.strip()
        if stmt and stmt != ';':
            sql_statements.append(stmt)
        current = []

success = 0
failed = 0
for i, stmt in enumerate(sql_statements):
    try:
        cursor.execute(stmt)
        conn.commit()
        success += 1
        first_line = stmt.split('\n')[0][:80]
        print(f'[{i+1}] OK: {first_line}')
    except Exception as e:
        conn.rollback()
        failed += 1
        first_line = stmt.split('\n')[0][:80]
        print(f'[{i+1}] FAIL: {first_line}')
        print(f'    Error: {e}')

print(f'\nTotal: {len(sql_statements)}, Success: {success}, Failed: {failed}')

cursor.execute('SHOW TABLES')
tables = [t[0] for t in cursor.fetchall()]
print(f'\nAll tables ({len(tables)}):')
for t in sorted(tables):
    print(f'  - {t}')

conn.close()
