#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缺失数据补采脚本 V3
修复nan值写入MySQL问题
"""

import time
import csv
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.db import MySQLConfig, connect, executemany, query_dict


def _log(msg: str):
    """打印带时间戳的日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [fix_missing_v3] {msg}")


def _safe_value(val) -> Optional[float]:
    """安全转换值，将nan/inf转为None"""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


# 补采用的更新SQL（只更新缺失字段）
_UPDATE_SQL = """
UPDATE trade_stock_financial
SET 
    pe_ttm = IF(pe_ttm IS NULL, %s, pe_ttm),
    pb = IF(pb IS NULL, %s, pb),
    roe = IF(roe IS NULL, %s, roe),
    roa = IF(roa IS NULL, %s, roa),
    profit_growth_yoy = IF(profit_growth_yoy IS NULL, %s, profit_growth_yoy),
    revenue_growth_yoy = IF(revenue_growth_yoy IS NULL, %s, revenue_growth_yoy),
    data_source = %s
WHERE stock_code = %s AND report_date = %s
"""


def load_missing_report(csv_path: str) -> List[Dict[str, str]]:
    """从CSV文件加载缺失数据报告"""
    missing_records = []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            has_missing = False
            if row['缺失PE'] == 'Y':
                has_missing = True
            if row['缺失PB'] == 'Y':
                has_missing = True
            if row['缺失ROE'] == 'Y':
                has_missing = True
            if row['缺失ROA'] == 'Y':
                has_missing = True
            if row['缺失利润增速'] == 'Y':
                has_missing = True
            if row['缺失营收增速'] == 'Y':
                has_missing = True
            
            if has_missing:
                missing_records.append({
                    'stock_code': row['股票代码'],
                    'report_date': row['报告日期'],
                    'missing_pe': row['缺失PE'] == 'Y',
                    'missing_pb': row['缺失PB'] == 'Y',
                    'missing_roe': row['缺失ROE'] == 'Y',
                    'missing_roa': row['缺失ROA'] == 'Y',
                    'missing_profit': row['缺失利润增速'] == 'Y',
                    'missing_revenue': row['缺失营收增速'] == 'Y',
                    'data_source': row['数据源']
                })
    return missing_records


def fetch_financial_data(stock_code: str) -> Dict[str, Any]:
    """从TuShare获取财务数据（慢速模式）"""
    try:
        from infra.tushare_client import get_pro_api
        
        pro = get_pro_api()
        
        time.sleep(1.2)
        fina_df = pro.fina_indicator(ts_code=stock_code, limit=12)
        
        if fina_df is None or len(fina_df) == 0:
            return {}
        
        time.sleep(1.2)
        basic_df = pro.daily_basic(ts_code=stock_code, limit=1)
        
        pe_ttm = None
        pb = None
        if basic_df is not None and len(basic_df) > 0:
            pe_ttm = _safe_value(basic_df.iloc[0].get('pe_ttm'))
            pb = _safe_value(basic_df.iloc[0].get('pb'))
        
        results = {}
        for _, row in fina_df.iterrows():
            report_date = str(row.get('end_date', ''))
            if len(report_date) == 8:
                report_date = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
            
            results[report_date[:10]] = {
                'roe': _safe_value(row.get('roe')),
                'roa': _safe_value(row.get('roa')),
                'profit_growth_yoy': _safe_value(row.get('netprofit_yoy')),
                'revenue_growth_yoy': _safe_value(row.get('or_yoy')),
                'pe_ttm': pe_ttm,
                'pb': pb,
            }
        
        return results
    
    except Exception as e:
        _log(f"  TuShare获取 {stock_code} 失败: {type(e).__name__}: {e}")
        return {}


def fix_missing_data(cfg: MySQLConfig, csv_path: str):
    """执行缺失数据补采"""
    start_time = datetime.now()
    _log("=" * 60)
    _log("开始缺失数据补采任务 V3")
    _log(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    _log("=" * 60)
    
    missing_records = load_missing_report(csv_path)
    _log(f"共发现 {len(missing_records)} 条缺失记录")
    
    if not missing_records:
        _log("没有需要补采的记录")
        return
    
    stock_groups = {}
    for record in missing_records:
        code = record['stock_code']
        if code not in stock_groups:
            stock_groups[code] = []
        stock_groups[code].append(record)
    
    _log(f"涉及股票数量: {len(stock_groups)} 只")
    
    total_stocks = len(stock_groups)
    processed = 0
    updated = 0
    failed = []
    
    for i, (stock_code, records) in enumerate(stock_groups.items(), 1):
        _log(f"[{i}/{total_stocks}] 处理 {stock_code} ({len(records)}条缺失)...")
        
        fin_data = fetch_financial_data(stock_code)
        
        if not fin_data:
            _log(f"  {stock_code} 获取数据失败，跳过")
            failed.append(stock_code)
            processed += 1
            continue
        
        updated_count = 0
        for record in records:
            rpt_date = record['report_date']
            if rpt_date in fin_data:
                data = fin_data[rpt_date]
                
                conn = connect(cfg)
                try:
                    written = conn.execute(
                        _UPDATE_SQL,
                        (
                            data.get('pe_ttm') if record['missing_pe'] else None,
                            data.get('pb') if record['missing_pb'] else None,
                            data.get('roe') if record['missing_roe'] else None,
                            data.get('roa') if record['missing_roa'] else None,
                            data.get('profit_growth_yoy') if record['missing_profit'] else None,
                            data.get('revenue_growth_yoy') if record['missing_revenue'] else None,
                            'tushare_fix',
                            stock_code,
                            rpt_date
                        )
                    )
                    if written > 0:
                        updated_count += 1
                except Exception as e:
                    _log(f"  写入 {stock_code} {rpt_date} 失败: {type(e).__name__}: {e}")
                finally:
                    conn.close()
        
        _log(f"  {stock_code} 更新 {updated_count} 条记录")
        updated += updated_count
        processed += 1
        time.sleep(0.3)
    
    total_elapsed = (datetime.now() - start_time).total_seconds()
    
    _log("=" * 60)
    _log("缺失数据补采任务完成")
    _log(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"总耗时: {total_elapsed:.0f}秒 ({total_elapsed/60:.1f}分钟)")
    _log(f"处理股票: {processed} 只")
    _log(f"更新记录: {updated} 条")
    _log(f"失败股票: {len(failed)} 只")
    _log("=" * 60)


if __name__ == "__main__":
    from core.db import load_mysql_config
    
    cfg = load_mysql_config()
    csv_path = '/Users/apple/Desktop/ai_huahua/ai_quant/missing_data_report.csv'
    fix_missing_data(cfg, csv_path)
