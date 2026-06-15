#!/usr/bin/env python3
"""
使用 AkShare 补充股票的二级行业数据
"""

import pymysql
from datetime import datetime
from typing import Dict, List
import sys

# 添加项目路径
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from core.db import load_mysql_config


def fetch_sector_from_akshare() -> Dict[str, Dict[str, str]]:
    """使用 AkShare 获取股票的行业信息"""
    try:
        import akshare as ak
        
        print("正在从 AkShare 获取行业板块数据...")
        
        # 获取行业板块数据
        sector_df = ak.stock_sector_spot()
        
        result: Dict[str, Dict[str, str]] = {}
        
        for _, row in sector_df.iterrows():
            # 获取股票代码和行业信息
            code = None
            name = None
            industry = None
            
            for col in row.index:
                col_str = str(col)
                if '代码' in col_str or 'code' in col_str.lower():
                    code = str(row[col]).strip()
                elif '名称' in col_str or 'name' in col_str.lower():
                    name = str(row[col]).strip()
                elif '行业' in col_str or 'industry' in col_str.lower():
                    industry = str(row[col]).strip()
            
            if code and industry:
                # 构建标准格式的股票代码
                if code.startswith('6'):
                    full_code = f"{code}.SH"
                elif code.startswith('3') or code.startswith('0'):
                    full_code = f"{code}.SZ"
                elif code.startswith('9'):
                    full_code = f"{code}.BJ"
                else:
                    continue
                
                if full_code not in result:
                    result[full_code] = {'industry': industry, 'name': name}
        
        print(f"从 AkShare 获取到 {len(result)} 只股票的行业信息")
        return result
        
    except Exception as e:
        print(f"AkShare 获取行业信息失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def get_stocks_with_level1() -> List[Dict[str, str]]:
    """获取已有一级行业但缺失二级行业的股票"""
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT stock_code, stock_name, sector_level1 
                FROM trade_stock_master 
                WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
                  AND (sector_level2 IS NULL OR sector_level2 = "")
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
                ORDER BY stock_code
            ''')
            return cursor.fetchall()
    finally:
        conn.close()


def update_sector_level2(sector_map: Dict[str, Dict[str, str]], stocks: List[Dict[str, str]]):
    """更新数据库中的二级行业数据"""
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
            SET sector_level2 = %s, updated_at = NOW()
            WHERE stock_code = %s
        '''
        
        updated_count = 0
        failed_count = 0
        failed_list = []
        
        for stock in stocks:
            code = stock['stock_code']
            if code in sector_map:
                info = sector_map[code]
                # 如果 AkShare 的行业与数据库中的一级行业不同，则作为二级行业
                if info['industry'] != stock['sector_level1']:
                    try:
                        cursor.execute(update_sql, (info['industry'], code))
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
            
            # 统计已有一级行业数据的股票数
            cursor.execute('''
                SELECT COUNT(*) as filled_l1 
                FROM trade_stock_master 
                WHERE sector_level1 IS NOT NULL AND sector_level1 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
            ''')
            filled_l1 = cursor.fetchone()['filled_l1']
            
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
            print('二级行业数据补全验证报告')
            print('=' * 70)
            print(f'总股票数(排除指数和行业伪代码): {total:,}')
            print(f'已填充一级行业数据: {filled_l1:,} ({filled_l1/total*100:.2f}%)')
            print(f'已填充二级行业数据: {filled_l2:,} ({filled_l2/total*100:.2f}%)')
            
            # 展示一些已填充的数据
            cursor.execute('''
                SELECT stock_code, stock_name, sector_level1, sector_level2 
                FROM trade_stock_master 
                WHERE sector_level2 IS NOT NULL AND sector_level2 != ""
                  AND stock_code NOT LIKE 'SWL%'
                  AND stock_code NOT LIKE '000%'
                  AND stock_code NOT LIKE '399%'
                  AND stock_code NOT LIKE '880%'
                LIMIT 10
            ''')
            filled_samples = cursor.fetchall()
            
            print()
            print('已填充二级行业数据的股票样本:')
            print('-' * 70)
            for s in filled_samples:
                print(f"{s['stock_code']} - {s['stock_name']}")
                print(f"  一级行业: {s['sector_level1']}")
                print(f"  二级行业: {s['sector_level2']}")
            
    finally:
        conn.close()


def main():
    print('=' * 70)
    print('使用 AkShare 补充二级行业数据')
    print(f'执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)
    
    # 1. 获取已有一级行业但缺失二级行业的股票
    print('\n步骤1: 获取已有一级行业但缺失二级行业的股票...')
    stocks = get_stocks_with_level1()
    print(f'找到 {len(stocks)} 只需要补充二级行业的股票')
    
    if not stocks:
        print('所有股票都已有二级行业数据，无需补全')
        verify_result()
        return
    
    # 2. 使用 AkShare 获取行业信息
    print('\n步骤2: 使用 AkShare 获取行业信息...')
    sector_map = fetch_sector_from_akshare()
    
    if not sector_map:
        print('未能获取到任何行业数据，任务结束')
        return
    
    # 3. 更新数据库
    print('\n步骤3: 更新数据库中的二级行业数据...')
    update_sector_level2(sector_map, stocks)
    
    # 4. 验证结果
    verify_result()


if __name__ == '__main__':
    main()