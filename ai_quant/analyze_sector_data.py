#!/usr/bin/env python3
"""
分析股票行业数据缺失问题
"""

import pymysql
from core.db import load_mysql_config


def analyze_sector_data():
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with conn.cursor() as cursor:
            # 统计总股票数
            cursor.execute('SELECT COUNT(*) as total FROM trade_stock_master')
            total = cursor.fetchone()['total']
            
            # 统计缺失一级行业数据的股票数
            cursor.execute('SELECT COUNT(*) as missing FROM trade_stock_master WHERE sector_level1 IS NULL OR sector_level1 = ""')
            missing_l1 = cursor.fetchone()['missing']
            
            # 统计缺失二级行业数据的股票数
            cursor.execute('SELECT COUNT(*) as missing FROM trade_stock_master WHERE sector_level2 IS NULL OR sector_level2 = ""')
            missing_l2 = cursor.fetchone()['missing']
            
            # 获取10个缺失行业数据的股票样本
            cursor.execute('SELECT stock_code, stock_name FROM trade_stock_master WHERE sector_level1 IS NULL OR sector_level1 = "" LIMIT 10')
            samples = cursor.fetchall()
            
            print('=' * 60)
            print('股票行业数据缺失分析报告')
            print('=' * 60)
            print(f'总股票数: {total}')
            print(f'缺失一级行业数据的股票数: {missing_l1}')
            print(f'缺失二级行业数据的股票数: {missing_l2}')
            print(f'一级行业缺失率: {missing_l1/total*100:.2f}%')
            print(f'二级行业缺失率: {missing_l2/total*100:.2f}%')
            print()
            print('缺失行业数据的股票样本:')
            print('-' * 60)
            for i, s in enumerate(samples, 1):
                print(f'{i:2d}. {s["stock_code"]} - {s["stock_name"]}')
            
            # 检查这些股票是否有对应的财务数据
            print()
            print('检查这些股票是否有财务数据:')
            print('-' * 60)
            for s in samples:
                cursor.execute('SELECT COUNT(*) as cnt FROM trade_stock_financial WHERE stock_code = %s', (s['stock_code'],))
                cnt = cursor.fetchone()['cnt']
                print(f'{s["stock_code"]} - {s["stock_name"]}: {cnt} 条财务记录')
            
    finally:
        conn.close()


if __name__ == '__main__':
    analyze_sector_data()
