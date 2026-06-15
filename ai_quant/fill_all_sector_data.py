#!/usr/bin/env python3
"""
批量补全所有非指数类股票的申万行业数据
使用 Tushare 获取股票的申万行业分类并更新到数据库
"""

import pymysql
from datetime import datetime
from typing import Dict, List
import sys

# 添加项目路径
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from core.db import load_mysql_config


def get_all_missing_stocks() -> List[Dict[str, str]]:
    """获取所有缺失行业数据的非指数类股票"""
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            # 获取所有缺失一级行业数据的股票（排除指数和行业伪代码）
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
            return cursor.fetchall()
    finally:
        conn.close()


def fetch_sw_industry_from_tushare() -> Dict[str, Dict[str, str]]:
    """使用 Tushare 获取股票的行业分类"""
    try:
        from infra.tushare_client import get_pro_api
        
        pro = get_pro_api()
        
        print("正在从 Tushare 获取股票基础信息（含行业分类）...")
        
        # 获取所有股票的基础信息（包含行业字段）
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,industry,list_date')
        
        result: Dict[str, Dict[str, str]] = {}
        
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                ts_code = row['ts_code']
                industry = row['industry'] if row['industry'] else None
                
                if ts_code not in result:
                    result[ts_code] = {'sw_level1': None, 'sw_level2': None, 'industry': None}
                
                result[ts_code]['industry'] = industry
                result[ts_code]['sw_level1'] = industry  # 使用 industry 作为一级行业
        
        print(f"从 Tushare 获取到 {len(result)} 只股票的行业信息")
        return result
        
    except Exception as e:
        print(f"Tushare 获取行业信息失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def update_sector_data(sector_map: Dict[str, Dict[str, str]], stocks: List[Dict[str, str]]):
    """更新数据库中的行业数据"""
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4'
    )
    try:
        cursor = conn.cursor()
        
        update_sql = '''
            UPDATE trade_stock_master 
            SET sector_level1 = %s, sector_level2 = %s, updated_at = NOW()
            WHERE stock_code = %s
        '''
        
        updated_count = 0
        failed_count = 0
        failed_list = []
        
        for stock in stocks:
            code = stock['stock_code']
            if code in sector_map:
                info = sector_map[code]
                try:
                    cursor.execute(update_sql, (
                        info['sw_level1'] or info['industry'],
                        info['sw_level2'],
                        code
                    ))
                    updated_count += 1
                except Exception as e:
                    failed_count += 1
                    failed_list.append(code)
                    print(f"  更新股票 {code} 失败: {e}")
        
        conn.commit()
        print(f"\n更新完成:")
        print(f"  成功: {updated_count}")
        print(f"  失败: {failed_count}")
        
        if failed_list:
            print(f"\n失败的股票: {failed_list[:20]}")
        
    finally:
        conn.close()


def verify_result():
    """验证补全结果"""
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            # 统计总股票数（排除行业伪代码和指数）
            cursor.execute('''
                SELECT COUNT(*) as total 
                FROM trade_stock_master 
                WHERE stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            total = cursor.fetchone()['total']
            
            # 统计缺失一级行业数据的股票数
            cursor.execute('''
                SELECT COUNT(*) as missing 
                FROM trade_stock_master 
                WHERE (sector_level1 IS NULL OR sector_level1 = "")
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            missing = cursor.fetchone()['missing']
            
            # 统计已有行业数据的股票数
            cursor.execute('''
                SELECT COUNT(*) as filled 
                FROM trade_stock_master 
                WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            filled = cursor.fetchone()['filled']
            
            # 统计已有二级行业数据的股票数
            cursor.execute('''
                SELECT COUNT(*) as filled_l2 
                FROM trade_stock_master 
                WHERE sector_level2 IS NOT NULL AND sector_level2 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            filled_l2 = cursor.fetchone()['filled_l2']
            
            print()
            print('=' * 70)
            print('行业数据补全验证报告')
            print('=' * 70)
            print(f'总股票数(排除指数和行业伪代码): {total:,}')
            print(f'已填充一级行业数据: {filled:,} ({filled/total*100:.2f}%)')
            print(f'已填充二级行业数据: {filled_l2:,} ({filled_l2/total*100:.2f}%)')
            print(f'仍缺失一级行业数据: {missing:,} ({missing/total*100:.2f}%)')
            
            # 展示一些已填充的数据
            cursor.execute('''
                SELECT stock_code, stock_name, sector_level1, sector_level2 
                FROM trade_stock_master 
                WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
                LIMIT 10
            ''')
            filled_samples = cursor.fetchall()
            
            print()
            print('已填充行业数据的股票样本:')
            print('-' * 70)
            for s in filled_samples:
                print(f"{s['stock_code']} - {s['stock_name']}")
                print(f"  一级行业: {s['sector_level1']}")
                print(f"  二级行业: {s['sector_level2'] if s['sector_level2'] else 'N/A'}")
            
            # 展示仍缺失的数据
            if missing > 0:
                cursor.execute('''
                    SELECT stock_code, stock_name 
                    FROM trade_stock_master 
                    WHERE (sector_level1 IS NULL OR sector_level1 = "")
                      AND stock_code NOT LIKE 'SWL%'
                      AND stock_code NOT LIKE '000%'
                      AND stock_code NOT LIKE '399%'
                      AND stock_code NOT LIKE '880%'
                    LIMIT 10
                ''')
                missing_samples = cursor.fetchall()
                
                print()
                print('仍缺失行业数据的股票样本:')
                print('-' * 70)
                for s in missing_samples:
                    print(f"{s['stock_code']} - {s['stock_name']}")
            
    finally:
        conn.close()


def main():
    print('=' * 70)
    print('批量补全所有非指数类股票的申万行业数据')
    print(f'执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    
    # 1. 获取所有缺失行业数据的股票
    print('\n步骤1: 获取所有缺失行业数据的非指数类股票...')
    missing_stocks = get_all_missing_stocks()
    print(f'找到 {len(missing_stocks)} 只缺失行业数据的股票')
    
    if not missing_stocks:
        print('所有股票都已有行业数据，无需补全')
        verify_result()
        return
    
    # 2. 使用 Tushare 获取行业信息
    print('\n步骤2: 使用 Tushare 获取申万行业分类...')
    sector_map = fetch_sw_industry_from_tushare()
    
    if not sector_map:
        print('未能获取到任何行业数据，任务结束')
        return
    
    # 3. 更新数据库
    print('\n步骤3: 更新数据库中的行业数据...')
    update_sector_data(sector_map, missing_stocks)
    
    # 4. 验证结果
    verify_result()


if __name__ == '__main__':
    main()