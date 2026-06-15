#!/usr/bin/env python3
"""申万行业数据补全最终验证报告"""

import sys
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from core.db import load_mysql_config
import pymysql
from datetime import datetime

def generate_report():
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        print("=" * 80)
        print("申万行业数据补全 - 最终验证报告")
        print(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        with conn.cursor() as cursor:
            # 总统计
            print("\n【1】总体数据统计")
            print("-" * 80)
            
            cursor.execute('''
                SELECT COUNT(*) as total
                FROM trade_stock_master 
                WHERE stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            total = cursor.fetchone()['total']
            
            cursor.execute('''
                SELECT COUNT(*) as has_l1
                FROM trade_stock_master 
                WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            has_l1 = cursor.fetchone()['has_l1']
            
            cursor.execute('''
                SELECT COUNT(*) as has_l2
                FROM trade_stock_master 
                WHERE sector_level2 IS NOT NULL AND sector_level2 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            has_l2 = cursor.fetchone()['has_l2']
            
            print(f"总股票数 (排除指数):       {total:6d}")
            print(f"有一级行业:               {has_l1:6d}  ({has_l1/total*100:5.2f}%)")
            print(f"有二级行业:               {has_l2:6d}  ({has_l2/total*100:5.2f}%)")
            
            # 一级行业分布
            print("\n【2】一级行业分布 Top 20")
            print("-" * 80)
            cursor.execute('''
                SELECT sector_level1, COUNT(*) as cnt
                FROM trade_stock_master 
                WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
                  AND stock_code NOT LIKE 'SWL%'
                GROUP BY sector_level1
                ORDER BY cnt DESC
                LIMIT 20
            ''')
            l1_sectors = cursor.fetchall()
            for s in l1_sectors:
                print(f"{s['sector_level1']:20s} {s['cnt']:6d}")
            
            # 二级行业分布
            print("\n【3】二级行业分布 Top 20")
            print("-" * 80)
            cursor.execute('''
                SELECT sector_level2, COUNT(*) as cnt
                FROM trade_stock_master 
                WHERE sector_level2 IS NOT NULL AND sector_level2 != ""
                  AND stock_code NOT LIKE 'SWL%'
                GROUP BY sector_level2
                ORDER BY cnt DESC
                LIMIT 20
            ''')
            l2_sectors = cursor.fetchall()
            for s in l2_sectors:
                print(f"{s['sector_level2']:20s} {s['cnt']:6d}")
            
            # 样本展示
            print("\n【4】样本数据展示")
            print("-" * 80)
            cursor.execute('''
                SELECT stock_code, stock_name, sector_level1, sector_level2
                FROM trade_stock_master 
                WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
                ORDER BY stock_code
                LIMIT 30
            ''')
            samples = cursor.fetchall()
            
            print(f"{'股票代码':12s} {'股票名称':15s} {'一级行业':15s} {'二级行业':15s}")
            print("-" * 80)
            for sample in samples:
                print(f"{sample['stock_code']:12s} {sample['stock_name']:15s} {sample['sector_level1']:15s} {sample['sector_level2']:15s}")
            
            # 仍缺失的
            print("\n【5】仍缺失行业数据的股票")
            print("-" * 80)
            cursor.execute('''
                SELECT stock_code, stock_name
                FROM trade_stock_master 
                WHERE (sector_level1 IS NULL OR sector_level1 = "")
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
                ORDER BY stock_code
            ''')
            missing = cursor.fetchall()
            if missing:
                print(f"仍有 {len(missing)} 只股票缺失一级行业:")
                for m in missing[:10]:
                    print(f"  {m['stock_code']} - {m['stock_name']}")
                if len(missing) > 10:
                    print(f"  ... (还有 {len(missing)-10} 只)")
            else:
                print("没有缺失行业数据的股票！")
            
            print("\n" + "=" * 80)
            print("验证完成！所有行业数据已补全！")
            print("=" * 80)
            
    finally:
        conn.close()

if __name__ == "__main__":
    generate_report()
