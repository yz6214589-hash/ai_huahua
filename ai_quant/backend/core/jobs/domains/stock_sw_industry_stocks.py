"""
申万行业分类与股票关联采集任务
数据来源：Tushare（获取股票的申万行业分类）
写入表：trade_stock_master

修复行业数据缺失问题：将股票与对应的申万一级、二级行业关联
"""

from __future__ import annotations

from typing import Any, Dict, List
import pymysql
import os
from datetime import datetime

from core.jobs.common import JobStats
from core.db import load_mysql_config


def _fetch_sw_industry_from_tushare() -> Dict[str, Dict[str, str]]:
    """
    使用 Tushare 获取股票的申万行业分类
    
    Returns:
        dict: {股票代码: {'industry': 行业名称, 'sw_level1': 一级行业, 'sw_level2': 二级行业}}
    """
    try:
        from infra.tushare_client import get_pro_api
        
        pro = get_pro_api()
        
        print("从 Tushare 获取申万行业分类...")
        
        # 获取申万行业分类（A 股最新行业分类）
        df = pro.swl_classify(level='L1')  # 获取一级行业成分股
        df2 = pro.swl_classify(level='L2')  # 获取二级行业成分股
        
        result: Dict[str, Dict[str, str]] = {}
        
        # 先处理一级行业
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                ts_code = row['ts_code']
                if ts_code not in result:
                    result[ts_code] = {'sw_level1': None, 'sw_level2': None, 'industry': None}
                result[ts_code]['sw_level1'] = row['industry']
                result[ts_code]['industry'] = row['industry']  # 默认使用一级行业作为行业名称
        
        # 再处理二级行业（补充或覆盖）
        if df2 is not None and not df2.empty:
            for _, row in df2.iterrows():
                ts_code = row['ts_code']
                if ts_code not in result:
                    result[ts_code] = {'sw_level1': None, 'sw_level2': None, 'industry': None}
                result[ts_code]['sw_level2'] = row['industry']
                # 如果已有一级行业，则使用二级行业作为更细粒度的行业名称
                if result[ts_code]['sw_level1']:
                    result[ts_code]['industry'] = row['industry']
        
        print(f"获取到 {len(result)} 只股票的申万行业分类")
        return result
        
    except Exception as e:
        print(f"Tushare 获取申万行业分类失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def _fetch_sw_industry_from_akshare() -> Dict[str, Dict[str, str]]:
    """
    使用 AkShare 获取股票的行业分类（备用方案）
    
    Returns:
        dict: {股票代码: {'industry': 行业名称}}
    """
    try:
        import akshare as ak
        
        print("从 AkShare 获取行业分类...")
        
        # 获取行业板块数据
        sector_df = ak.stock_sector_spot()
        
        result: Dict[str, Dict[str, str]] = {}
        
        for _, row in sector_df.iterrows():
            # 尝试不同的列名（AkShare 可能返回不同的列名）
            code = None
            name = None
            industry = None
            
            for col in row.index:
                if '代码' in str(col) or 'code' in str(col).lower():
                    code = str(row[col]).strip()
                elif '名称' in str(col) or 'name' in str(col).lower():
                    name = str(row[col]).strip()
                elif '行业' in str(col) or 'industry' in str(col).lower():
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
                    result[full_code] = {'sw_level1': None, 'sw_level2': None, 'industry': None}
                result[full_code]['industry'] = industry
        
        print(f"从 AkShare 获取到 {len(result)} 只股票的行业分类")
        return result
        
    except Exception as e:
        print(f"AkShare 获取行业分类失败: {e}")
        import traceback
        traceback.print_exc()
        return {}


def _get_stocks_missing_sector() -> List[str]:
    """
    获取数据库中缺失行业数据的股票列表
    
    Returns:
        list: 股票代码列表
    """
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
                SELECT stock_code 
                FROM trade_stock_master 
                WHERE (sector_level1 IS NULL OR sector_level1 = "")
                  AND stock_code NOT LIKE 'SWL%'
            ''')
            return [row['stock_code'] for row in cursor.fetchall()]
    finally:
        conn.close()


def run_sw_industry_stock_mapping() -> JobStats:
    """
    运行股票-行业关联采集任务
    
    获取股票的申万行业分类信息并更新到数据库
    
    Returns:
        JobStats: 任务执行统计
    """
    print("=" * 60)
    print("股票-申万行业关联采集任务开始")
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 获取缺失行业数据的股票列表
    print("\n步骤1: 获取缺失行业数据的股票列表")
    missing_stocks = _get_stocks_missing_sector()
    print(f"找到 {len(missing_stocks)} 只缺失行业数据的股票")
    
    if not missing_stocks:
        print("所有股票都已有行业数据，任务结束")
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="none",
            fallback_chain=[],
            message="所有股票都已有行业数据"
        )
    
    # 2. 使用 Tushare 获取行业信息
    print("\n步骤2: 使用 Tushare 获取申万行业分类")
    tushare_data = _fetch_sw_industry_from_tushare()
    
    # 3. 如果 Tushare 数据不足，使用 AkShare 补充
    fallback_chain = ["tushare"]
    if len(tushare_data) < len(missing_stocks) * 0.5:
        print("\n步骤3: Tushare 数据不足，使用 AkShare 补充")
        akshare_data = _fetch_sw_industry_from_akshare()
        # 合并数据，AkShare 补充缺失的数据
        for code, info in akshare_data.items():
            if code not in tushare_data:
                tushare_data[code] = info
        fallback_chain.append("akshare")
        print(f"合并后共获取到 {len(tushare_data)} 只股票的行业信息")
    
    # 4. 更新数据库
    print("\n步骤4: 更新数据库中的行业数据")
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4'
    )
    
    saved_count = 0
    failed_count = 0
    failed_list = []
    
    try:
        cursor = conn.cursor()
        
        update_sql = '''
            UPDATE trade_stock_master 
            SET sector_level1 = %s, sector_level2 = %s, updated_at = NOW()
            WHERE stock_code = %s
        '''
        
        for stock_code in missing_stocks:
            if stock_code in tushare_data:
                info = tushare_data[stock_code]
                try:
                    cursor.execute(update_sql, (
                        info['sw_level1'] or info['industry'],
                        info['sw_level2'],
                        stock_code
                    ))
                    saved_count += 1
                except Exception as e:
                    failed_count += 1
                    failed_list.append(stock_code)
                    print(f"  更新股票 {stock_code} 失败: {e}")
        
        conn.commit()
        cursor.close()
        
        print(f"\n更新完成:")
        print(f"  成功: {saved_count}")
        print(f"  失败: {failed_count}")
        
    finally:
        conn.close()
    
    # 5. 验证结果
    print("\n步骤5: 验证更新结果")
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as total FROM trade_stock_master WHERE stock_code NOT LIKE "SWL%"')
            total = cursor.fetchone()['total']
            
            cursor.execute('SELECT COUNT(*) as filled FROM trade_stock_master WHERE sector_level1 IS NOT NULL AND sector_level1 != "" AND stock_code NOT LIKE "SWL%"')
            filled = cursor.fetchone()['filled']
            
            cursor.execute('SELECT COUNT(*) as missing FROM trade_stock_master WHERE (sector_level1 IS NULL OR sector_level1 = "") AND stock_code NOT LIKE "SWL%"')
            missing = cursor.fetchone()['missing']
            
            print(f"总股票数: {total}")
            print(f"已填充行业数据: {filled}")
            print(f"仍缺失行业数据: {missing}")
            print(f"填充率: {filled/total*100:.2f}%")
    finally:
        conn.close()
    
    print("\n" + "=" * 60)
    print("股票-申万行业关联采集任务完成")
    print("=" * 60)
    
    return JobStats(
        items_processed=len(missing_stocks),
        rows_written=saved_count,
        failed_items=failed_list[:100] if len(failed_list) > 100 else failed_list,
        data_source_final="tushare" if len(fallback_chain) == 1 else "akshare",
        fallback_chain=fallback_chain,
        message=f"成功更新 {saved_count}/{len(missing_stocks)} 只股票的行业数据"
    )


if __name__ == "__main__":
    stats = run_sw_industry_stock_mapping()
    print("\n任务统计:")
    print(f"  处理项目数: {stats.items_processed}")
    print(f"  写入行数: {stats.rows_written}")
    print(f"  失败项目: {len(stats.failed_items)}")
    print(f"  数据源: {stats.data_source_final}")
    print(f"  消息: {stats.message}")
