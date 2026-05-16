"""
连接到腾讯云数据库并分析现有表结构
"""
import pymysql
from tabulate import tabulate
import sys

# 数据库配置
DB_CONFIG = {
    'host': 'bj-cdb-6zjqetya.sql.tencentcdb.com',
    'port': 25341,
    'user': 'root',
    'password': 'huahua1688',
    'database': 'huahua_trade',
    'charset': 'utf8mb4'
}


def connect_to_database():
    """连接到数据库"""
    try:
        print("正在连接到腾讯云数据库...")
        print(f"主机: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
        print(f"数据库: {DB_CONFIG['database']}")
        
        conn = pymysql.connect(**DB_CONFIG)
        print("✓ 数据库连接成功!")
        return conn
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return None


def get_all_tables(cursor):
    """获取所有表"""
    cursor.execute("SHOW TABLES")
    return [table[0] for table in cursor.fetchall()]


def analyze_table(cursor, table_name):
    """分析单个表"""
    print(f"\n{'='*80}")
    print(f"表名: {table_name}")
    print('='*80)
    
    # 获取表结构
    print("\n📋 表结构:")
    cursor.execute(f"DESCRIBE `{table_name}`")
    columns = cursor.fetchall()
    headers = ['字段名', '类型', '允许NULL', '键', '默认值', '额外信息']
    print(tabulate(columns, headers=headers, tablefmt='grid'))
    
    # 获取行数
    try:
        cursor.execute(f"SELECT COUNT(*) as count FROM `{table_name}`")
        count = cursor.fetchone()[0]
        print(f"\n📊 数据行数: {count}")
    except:
        print(f"\n📊 数据行数: 无法获取")
    
    # 获取索引
    cursor.execute(f"SHOW INDEX FROM `{table_name}`")
    indexes = cursor.fetchall()
    if indexes:
        print(f"\n🔍 索引信息:")
        index_data = [[idx[2], idx[4], idx[3]] for idx in indexes]
        print(tabulate(index_data, headers=['索引名', '列名', '类型'], tablefmt='grid'))


def main():
    """主函数"""
    print("=" * 80)
    print("数据库表结构分析工具")
    print("=" * 80)
    
    # 连接数据库
    conn = connect_to_database()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # 获取所有表
        print("\n正在获取所有表...")
        tables = get_all_tables(cursor)
        
        print(f"\n✅ 数据库中共有 {len(tables)} 个表:")
        for i, table in enumerate(tables, 1):
            print(f"  {i}. {table}")
        
        # 分析每个表
        print("\n" + "=" * 80)
        print("开始分析每个表的结构...")
        print("=" * 80)
        
        for table in tables:
            try:
                analyze_table(cursor, table)
            except Exception as e:
                print(f"\n❌ 分析表 {table} 时出错: {e}")
        
        print("\n" + "=" * 80)
        print("分析完成!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
