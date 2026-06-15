#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缺失数据补采脚本
针对数据库中PE/PB/ROE等字段缺失的数据进行补采
使用单线程、放慢请求速度避免Tushare限流
"""

import time
from datetime import datetime
from typing import Any, Dict, List

from core.db import MySQLConfig, connect, executemany, query_dict


def _log(msg: str):
    """打印带时间戳的日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [fix_missing] {msg}")


# 补采用的插入SQL
_INSERT_SQL = """
INSERT INTO trade_stock_financial
(stock_code, report_date, pe_ttm, pb, roe, roa, 
 profit_growth_yoy, revenue_growth_yoy, data_source, created_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
ON DUPLICATE KEY UPDATE
pe_ttm=COALESCE(VALUES(pe_ttm), pe_ttm),
pb=COALESCE(VALUES(pb), pb),
roe=COALESCE(VALUES(roe), roe),
roa=COALESCE(VALUES(roa), roa),
profit_growth_yoy=COALESCE(VALUES(profit_growth_yoy), profit_growth_yoy),
revenue_growth_yoy=COALESCE(VALUES(revenue_growth_yoy), revenue_growth_yoy),
data_source=VALUES(data_source)
"""


def get_stocks_with_missing_data(cfg: MySQLConfig, limit: int = 100) -> List[Dict[str, Any]]:
    """
    获取有缺失数据的股票列表（最近4个报告期）
    """
    conn = connect(cfg)
    try:
        # 只获取最近4个报告期的缺失数据（TuShare能获取到的范围）
        rows = query_dict(conn, """
            SELECT stock_code, report_date
            FROM trade_stock_financial
            WHERE (pe_ttm IS NULL OR pb IS NULL OR roe IS NULL)
              AND report_date >= DATE_SUB(CURDATE(), INTERVAL 18 MONTH)
            ORDER BY stock_code, report_date
            LIMIT %s
        """, (limit,))
        return rows
    finally:
        conn.close()


def get_stock_list_to_fix(cfg: MySQLConfig) -> List[str]:
    """
    获取需要补采的股票列表（去重，只包含最近4个报告期有缺失的股票）
    """
    conn = connect(cfg)
    try:
        rows = query_dict(conn, """
            SELECT DISTINCT stock_code
            FROM trade_stock_financial
            WHERE (pe_ttm IS NULL OR pb IS NULL OR roe IS NULL)
              AND report_date >= DATE_SUB(CURDATE(), INTERVAL 18 MONTH)
            ORDER BY stock_code
        """)
        return [r['stock_code'] for r in rows]
    finally:
        conn.close()


def fetch_from_tushare(stock_code: str) -> Dict[str, Any]:
    """
    使用TuShare获取股票财务数据（慢速模式）
    获取最近12个报告期的数据（3年，每季度一次）
    """
    try:
        from infra.tushare_client import get_pro_api
        
        pro = get_pro_api()
        
        # 1. 获取财务指标（获取最近12个报告期，覆盖3年数据）
        time.sleep(1.5)  # 放慢速度，避免限流
        fina_df = pro.fina_indicator(ts_code=stock_code, limit=12)
        
        if fina_df is None or len(fina_df) == 0:
            _log(f"  {stock_code} fina_indicator 返回空")
            return {}
        
        # 2. 获取daily_basic（PE/PB/市值）
        time.sleep(1.5)  # 放慢速度
        basic_df = pro.daily_basic(ts_code=stock_code, limit=1)
        
        results = []
        for _, row in fina_df.iterrows():
            report_date = str(row.get('end_date', ''))
            if not report_date:
                continue
            
            # 转换日期格式：确保是 YYYY-MM-DD 格式
            if len(report_date) == 8:
                report_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
            
            fin_data = {
                'report_date': report_date[:10],
                'roe': row.get('roe'),
                'roa': row.get('roa'),
                'profit_growth_yoy': row.get('netprofit_yoy'),
                'revenue_growth_yoy': row.get('or_yoy'),
            }
            results.append(fin_data)
        
        # 添加PE/PB数据到每条记录
        if basic_df is not None and len(basic_df) > 0:
            basic_row = basic_df.iloc[0]
            pe_ttm = basic_row.get('pe_ttm')
            pb = basic_row.get('pb')
            for r in results:
                r['pe_ttm'] = pe_ttm
                r['pb'] = pb
        
        _log(f"  TuShare返回 {len(results)} 条记录")
        return {'data': results}
    
    except Exception as e:
        _log(f"  TuShare获取 {stock_code} 失败: {type(e).__name__}: {e}")
        return {}


def fix_missing_data(cfg: MySQLConfig, batch_size: int = 50):
    """
    执行缺失数据补采
    """
    start_time = datetime.now()
    _log("=" * 60)
    _log("开始缺失数据补采任务")
    _log(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    _log("=" * 60)
    
    # 获取需要补采的股票列表
    stocks = get_stock_list_to_fix(cfg)
    total_stocks = len(stocks)
    _log(f"发现 {total_stocks} 只股票存在缺失数据")
    
    if not stocks:
        _log("没有需要补采的股票，任务结束")
        return
    
    processed = 0
    rows_updated = 0
    failed = []
    batch: List[tuple] = []
    
    for i, stock_code in enumerate(stocks, 1):
        _log(f"[{i}/{total_stocks}] 处理 {stock_code}...")
        
        # 获取该股票当前缺失的日期
        conn = connect(cfg)
        try:
            missing_dates = query_dict(conn, """
                SELECT report_date 
                FROM trade_stock_financial 
                WHERE stock_code = %s AND (pe_ttm IS NULL OR pb IS NULL OR roe IS NULL)
                ORDER BY report_date
            """, (stock_code,))
            missing_date_set = {str(r['report_date'])[:10] for r in missing_dates}
        finally:
            conn.close()
        
        if not missing_date_set:
            _log(f"  {stock_code} 已无缺失数据，跳过")
            processed += 1
            continue
        
        # 从TuShare获取数据
        result = fetch_from_tushare(stock_code)
        fin_data = result.get('data', [])
        
        if not fin_data:
            _log(f"  {stock_code} 获取数据失败，跳过")
            failed.append(stock_code)
            processed += 1
            continue
        
        # 只处理有缺失的日期
        updated_count = 0
        for item in fin_data:
            rpt_date = item['report_date']
            if rpt_date in missing_date_set:
                batch.append((
                    stock_code,
                    rpt_date,
                    item.get('pe_ttm'),
                    item.get('pb'),
                    item.get('roe'),
                    item.get('roa'),
                    item.get('profit_growth_yoy'),
                    item.get('revenue_growth_yoy'),
                    'tushare_fix'
                ))
                updated_count += 1
        
        _log(f"  {stock_code} 发现 {len(missing_date_set)} 条缺失，补采 {updated_count} 条")
        processed += 1
        
        # 每batch_size只股票提交一次
        if len(batch) >= batch_size or i == total_stocks:
            _log(f"  提交批次: {len(batch)} 条记录...")
            conn = connect(cfg)
            try:
                written = executemany(conn, _INSERT_SQL, batch)
                rows_updated += written
                _log(f"  成功更新 {written} 条记录")
            except Exception as e:
                _log(f"  写入失败: {type(e).__name__}: {e}")
            finally:
                conn.close()
                batch.clear()
        
        # 额外延迟，避免限流
        time.sleep(0.5)
    
    total_elapsed = (datetime.now() - start_time).total_seconds()
    
    _log("=" * 60)
    _log("缺失数据补采任务完成")
    _log(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"总耗时: {total_elapsed:.0f}秒 ({total_elapsed/60:.1f}分钟)")
    _log(f"处理股票: {processed} 只")
    _log(f"更新记录: {rows_updated} 条")
    _log(f"失败股票: {len(failed)} 只")
    if failed:
        _log(f"失败列表: {failed[:10]}")
    _log("=" * 60)


if __name__ == "__main__":
    from core.db import load_mysql_config
    
    cfg = load_mysql_config()
    fix_missing_data(cfg, batch_size=50)
