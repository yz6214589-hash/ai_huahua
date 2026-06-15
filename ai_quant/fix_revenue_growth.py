#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
营收增速专项补采脚本
针对营收增速缺失率高的问题进行专项补采
"""

import time
import csv
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.db import MySQLConfig, connect, query_dict


def _log(msg: str):
    """打印带时间戳的日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [revenue_fix] {msg}")


def _safe_value(val) -> Optional[float]:
    """安全转换值"""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def get_stocks_with_missing_revenue(cfg: MySQLConfig) -> List[str]:
    """获取营收增速缺失的股票列表"""
    conn = connect(cfg)
    try:
        rows = query_dict(conn, """
            SELECT DISTINCT stock_code 
            FROM trade_stock_financial 
            WHERE revenue_growth_yoy IS NULL 
            ORDER BY stock_code
        """)
        return [row['stock_code'] for row in rows]
    finally:
        conn.close()


def fetch_revenue_growth(pro, stock_code: str) -> Dict[str, float]:
    """获取股票的营收增速数据"""
    try:
        time.sleep(1.5)
        fina_df = pro.fina_indicator(ts_code=stock_code, limit=12)
        
        if fina_df is None or len(fina_df) == 0:
            return {}
        
        results = {}
        for _, row in fina_df.iterrows():
            report_date = str(row.get('end_date', ''))
            if len(report_date) == 8:
                report_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
            revenue_growth = _safe_value(row.get('or_yoy'))
            if revenue_growth is not None:
                results[report_date[:10]] = revenue_growth
        
        return results
    
    except Exception as e:
        _log(f"  获取 {stock_code} 失败: {type(e).__name__}")
        return {}


def fix_revenue_growth(cfg: MySQLConfig):
    """执行营收增速补采"""
    from infra.tushare_client import get_pro_api
    
    pro = get_pro_api()
    start_time = datetime.now()
    
    _log("=" * 60)
    _log("开始营收增速专项补采")
    _log(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    _log("=" * 60)
    
    stocks = get_stocks_with_missing_revenue(cfg)
    _log(f"需要补采的股票数量: {len(stocks)} 只")
    
    if not stocks:
        _log("没有需要补采的股票")
        return
    
    total_stocks = len(stocks)
    updated = 0
    failed = []
    
    for i, stock_code in enumerate(stocks, 1):
        _log(f"[{i}/{total_stocks}] 处理 {stock_code}...")
        
        data = fetch_revenue_growth(pro, stock_code)
        
        if not data:
            failed.append(stock_code)
            continue
        
        conn = connect(cfg)
        try:
            for report_date, growth in data.items():
                rows = conn.execute("""
                    UPDATE trade_stock_financial 
                    SET revenue_growth_yoy = %s, data_source = 'tushare_revenue'
                    WHERE stock_code = %s AND report_date = %s AND revenue_growth_yoy IS NULL
                """, (growth, stock_code, report_date))
                if rows > 0:
                    updated += 1
        except Exception as e:
            _log(f"  写入失败: {type(e).__name__}")
        finally:
            conn.close()
        
        _log(f"  更新 {len(data)} 条记录")
        
        if i % 50 == 0:
            elapsed = (datetime.now() - start_time).total_seconds()
            avg_speed = i / elapsed * 60
            remaining = (total_stocks - i) / i * elapsed / 60
            _log(f"  进度: {i}/{total_stocks} ({i/total_stocks*100:.1f}%)")
            _log(f"  速度: {avg_speed:.1f} 只/分钟")
            _log(f"  预计剩余: {remaining:.1f} 分钟")
        
        time.sleep(0.5)
    
    total_elapsed = (datetime.now() - start_time).total_seconds()
    
    _log("=" * 60)
    _log("营收增速补采完成")
    _log(f"总耗时: {total_elapsed:.0f}秒 ({total_elapsed/60:.1f}分钟)")
    _log(f"处理股票: {len(stocks)} 只")
    _log(f"更新记录: {updated} 条")
    _log(f"失败股票: {len(failed)} 只")
    _log("=" * 60)


if __name__ == "__main__":
    from core.db import load_mysql_config
    
    cfg = load_mysql_config()
    fix_revenue_growth(cfg)
