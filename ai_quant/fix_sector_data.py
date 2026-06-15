#!/usr/bin/env python3
"""
修复股票行业数据缺失问题
使用 Tushare 获取股票的行业分类信息并更新到数据库
"""

import pymysql
from datetime import datetime
from typing import Any, Dict, List

# 使用项目中的数据库配置
from core.db import load_mysql_config


def get_missing_stocks() -> List[Dict[str, str]]:
    """获取缺失行业数据的股票列表"""
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            # 获取缺失一级行业数据的股票（排除指数）
            cursor.execute('''
                SELECT stock_code, stock_name 
                FROM trade_stock_master 
                WHERE sector_level1 IS NULL OR sector_level1 = ""
                  AND stock_code NOT LIKE 'SWL%'
                LIMIT 50
            ''')
            return cursor.fetchall()
    finally:
        conn.close()


def fetch_sector_from_tushare(stocks: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """使用 Tushare 获取股票行业信息"""
    try:
        from infra.tushare_client import get_pro_api
        
        pro = get_pro_api()
        
        # 获取所有股票的基础信息
        df = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,industry,list_date')
        
        result = {}
        for _, row in df.iterrows():
            ts_code = row['ts_code']
            result[ts_code] = {
                'industry': row['industry'] if row['industry'] else None,
                'name': row['name']
            }
        
        # 构建缺失股票的行业映射
        sector_map = {}
        for stock in stocks:
            code = stock['stock_code']
            if code in result:
                sector_map[code] = result[code]
        
        return sector_map
        
    except Exception as e:
        print(f"Tushare API 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def fetch_sector_from_akshare(stocks: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
    """使用 AkShare 获取股票行业信息（备用方案）"""
    try:
        import akshare as ak
        
        # 获取行业板块数据
        print("正在获取行业板块数据...")
        sector_df = ak.stock_sector_spot()
        
        sector_map = {}
        
        # 从行业板块获取
        for _, row in sector_df.iterrows():
            code = str(row['代码']).strip()
            name = row['名称']
            sector = row['所属行业']
            if code and sector:
                # 构建标准格式的股票代码
                if code.startswith('6'):
                    full_code = f"{code}.SH"
                elif code.startswith('3') or code.startswith('0'):
                    full_code = f"{code}.SZ"
                elif code.startswith('9'):
                    full_code = f"{code}.BJ"
                else:
                    continue
                sector_map[full_code] = {'industry': sector, 'name': name}
        
        print(f"从 AkShare 获取到 {len(sector_map)} 条行业数据")
        return sector_map
        
    except Exception as e:
        print(f"AkShare API 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def update_sector_data(sector_map: Dict[str, Dict[str, str]]):
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
        for code, info in sector_map.items():
            try:
                cursor.execute(update_sql, (info['industry'], None, code))
                updated_count += 1
            except Exception as e:
                print(f"更新股票 {code} 失败: {e}")
        
        conn.commit()
        print(f"成功更新 {updated_count} 只股票的行业数据")
        
    finally:
        conn.close()


def verify_fix():
    """验证修复结果"""
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            # 统计总股票数（排除行业伪代码）
            cursor.execute('SELECT COUNT(*) as total FROM trade_stock_master WHERE stock_code NOT LIKE "SWL%"')
            total = cursor.fetchone()['total']
            
            # 统计缺失一级行业数据的股票数
            cursor.execute('SELECT COUNT(*) as missing FROM trade_stock_master WHERE (sector_level1 IS NULL OR sector_level1 = "") AND stock_code NOT LIKE "SWL%"')
            missing = cursor.fetchone()['missing']
            
            # 统计已有行业数据的股票数
            cursor.execute('SELECT COUNT(*) as filled FROM trade_stock_master WHERE sector_level1 IS NOT NULL AND sector_level1 != "" AND stock_code NOT LIKE "SWL%"')
            filled = cursor.fetchone()['filled']
            
            print()
            print('=' * 60)
            print('行业数据修复验证报告')
            print('=' * 60)
            print(f'总股票数(排除行业伪代码): {total}')
            print(f'已填充行业数据的股票数: {filled}')
            print(f'仍缺失行业数据的股票数: {missing}')
            print(f'填充率: {filled/total*100:.2f}%')
            
            # 展示一些已填充的数据
            cursor.execute('SELECT stock_code, stock_name, sector_level1 FROM trade_stock_master WHERE sector_level1 IS NOT NULL AND sector_level1 != "" AND stock_code NOT LIKE "SWL%" LIMIT 10')
            filled_samples = cursor.fetchall()
            
            print()
            print('已填充行业数据的股票样本:')
            print('-' * 60)
            for s in filled_samples:
                print(f"{s['stock_code']} - {s['stock_name']} - {s['sector_level1']}")
            
            # 展示仍缺失的数据
            cursor.execute('SELECT stock_code, stock_name FROM trade_stock_master WHERE (sector_level1 IS NULL OR sector_level1 = "") AND stock_code NOT LIKE "SWL%" LIMIT 10')
            missing_samples = cursor.fetchall()
            
            print()
            print('仍缺失行业数据的股票样本:')
            print('-' * 60)
            for s in missing_samples:
                print(f"{s['stock_code']} - {s['stock_name']}")
            
    finally:
        conn.close()


def main():
    print('=' * 60)
    print('股票行业数据修复工具')
    print(f'执行时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 60)
    
    # 1. 获取缺失行业数据的股票
    print('\n步骤1: 获取缺失行业数据的股票...')
    missing_stocks = get_missing_stocks()
    print(f'找到 {len(missing_stocks)} 只缺失行业数据的股票')
    
    if not missing_stocks:
        print('所有股票都已有行业数据，无需修复')
        return
    
    # 2. 尝试使用 AkShare 获取行业信息（AkShare 更稳定）
    print('\n步骤2: 使用 AkShare 获取行业信息...')
    sector_map = fetch_sector_from_akshare(missing_stocks)
    print(f'通过 AkShare 获取到 {len(sector_map)} 只股票的行业信息')
    
    # 3. 如果 AkShare 没有获取到足够数据，尝试 Tushare
    if len(sector_map) < len(missing_stocks) * 0.5:
        print('\n步骤3: AkShare 数据不足，尝试使用 Tushare...')
        tushare_map = fetch_sector_from_tushare(missing_stocks)
        # 合并结果，Tushare 数据作为补充
        sector_map.update(tushare_map)
        print(f'通过 Tushare 补充获取到 {len(tushare_map)} 只股票的行业信息')
    
    # 4. 更新数据库
    if sector_map:
        print('\n步骤4: 更新数据库中的行业数据...')
        update_sector_data(sector_map)
    
    # 5. 验证修复结果
    verify_fix()


if __name__ == '__main__':
    main()
