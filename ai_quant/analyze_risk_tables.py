"""
快速分析风控相关表
"""
import pymysql
from tabulate import tabulate

# 数据库配置
DB_CONFIG = {
    'host': 'bj-cdb-6zjqetya.sql.tencentcdb.com',
    'port': 25341,
    'user': 'root',
    'password': 'huahua1688',
    'database': 'huahua_trade',
    'charset': 'utf8mb4'
}

def connect():
    """连接数据库"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        print("✓ 数据库连接成功")
        return conn
    except Exception as e:
        print(f"✗ 连接失败: {e}")
        return None

def get_all_tables(cursor):
    """获取所有表"""
    cursor.execute("SHOW TABLES")
    return [t[0] for t in cursor.fetchall()]

def analyze_risk_tables(cursor, tables):
    """分析风控相关表"""
    risk_keywords = ['risk', 'alert', 'event', 'rule', 'position', 'account', 'capital', 'order', 'signal']
    
    print("\n" + "="*80)
    print("风控相关表分析")
    print("="*80)
    
    for table in tables:
        # 检查是否是风控相关表
        is_risk_table = any(keyword in table.lower() for keyword in risk_keywords)
        
        if is_risk_table:
            print(f"\n📊 表名: {table}")
            cursor.execute(f"DESCRIBE `{table}`")
            columns = cursor.fetchall()
            headers = ['字段名', '类型', 'NULL', '键', '默认', '额外']
            print(tabulate(columns, headers=headers, tablefmt='grid'))
            
            try:
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                count = cursor.fetchone()[0]
                print(f"📈 数据行数: {count}")
            except:
                pass

def main():
    print("="*80)
    print("腾讯云数据库分析工具")
    print("="*80)
    
    conn = connect()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        tables = get_all_tables(cursor)
        
        print(f"\n数据库共有 {len(tables)} 个表:")
        for i, t in enumerate(tables, 1):
            print(f"  {i}. {t}")
        
        # 分析风控相关表
        analyze_risk_tables(cursor, tables)
        
        print("\n" + "="*80)
        print("分析完成!")
        print("="*80)
        
    except Exception as e:
        print(f"\n✗ 分析失败: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
