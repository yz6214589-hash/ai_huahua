"""
数据库结构分析脚本（使用腾讯云MySQL）
"""
import pymysql
import os

# 数据库配置
DB_HOST = 'bj-cdb-6zjqetya.sql.tencentcdb.com'
DB_PORT = 25341
DB_USER = 'root'
DB_PASSWORD = 'huahua1688'
DB_NAME = 'huahua_trade'


def connect_db():
    """连接到数据库"""
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset='utf8mb4'
    )


def get_all_tables():
    """获取所有表"""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    cursor.close()
    conn.close()
    return [t[0] for t in tables]


def get_table_structure(table_name):
    """获取表结构"""
    conn = connect_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f"DESCRIBE `{table_name}`")
    structure = cursor.fetchall()
    cursor.close()
    conn.close()
    return structure


def get_foreign_keys(table_name):
    """获取表的外键"""
    conn = connect_db()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute(f"""
        SELECT
            COLUMN_NAME,
            CONSTRAINT_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = '{DB_NAME}'
          AND TABLE_NAME = '{table_name}'
          AND REFERENCED_TABLE_NAME IS NOT NULL
    """)
    fks = cursor.fetchall()
    cursor.close()
    conn.close()
    return fks


def main():
    print("=" * 80)
    print("AI量化交易系统 - 数据库结构分析")
    print("=" * 80)
    print()
    print(f"数据库: {DB_NAME}")
    print(f"主机: {DB_HOST}:{DB_PORT}")
    print()

    try:
        tables = get_all_tables()
        print(f"找到 {len(tables)} 个数据表:")
        print()

        for i, table in enumerate(tables, 1):
            print("=" * 80)
            print(f"表 {i}: {table}")
            print("=" * 80)

            structure = get_table_structure(table)
            print("\n字段结构:")
            print(f"{'字段名':<20} {'类型':<20} {'可空':<8} {'默认值':<15} {'注释'}")
            print("-" * 80)
            for field in structure:
                print(f"{field['Field']:<20} {field['Type']:<20} {field['Null']:<8} {str(field['Default']) or 'NULL':<15} {field.get('Comment', '')}")

            fks = get_foreign_keys(table)
            if fks:
                print("\n外键关系:")
                for fk in fks:
                    print(f"  - {fk['COLUMN_NAME']} -> {fk['REFERENCED_TABLE_NAME']}.{fk['REFERENCED_COLUMN_NAME']}")

            print()

    except Exception as e:
        print(f"连接失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
