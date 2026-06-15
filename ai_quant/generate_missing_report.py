#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成缺失数据统计报告
输出CSV文件包含所有缺失指标的记录
"""

import csv
from datetime import datetime
from core.db import load_mysql_config, connect, query_dict


def generate_report():
    """生成缺失数据报告"""
    start_time = datetime.now()
    print(f"[{start_time}] 开始生成缺失数据报告...")
    
    cfg = load_mysql_config()
    conn = connect(cfg)
    
    try:
        # 查询缺失数据
        rows = query_dict(conn, """
            SELECT stock_code, report_date, 
                   CASE WHEN pe_ttm IS NULL THEN 'Y' ELSE '' END AS missing_pe,
                   CASE WHEN pb IS NULL THEN 'Y' ELSE '' END AS missing_pb,
                   CASE WHEN roe IS NULL THEN 'Y' ELSE '' END AS missing_roe,
                   CASE WHEN roa IS NULL THEN 'Y' ELSE '' END AS missing_roa,
                   CASE WHEN profit_growth_yoy IS NULL THEN 'Y' ELSE '' END AS missing_profit_growth,
                   CASE WHEN revenue_growth_yoy IS NULL THEN 'Y' ELSE '' END AS missing_revenue_growth,
                   data_source
            FROM trade_stock_financial
            WHERE pe_ttm IS NULL OR pb IS NULL OR roe IS NULL OR roa IS NULL 
               OR profit_growth_yoy IS NULL OR revenue_growth_yoy IS NULL
            ORDER BY stock_code, report_date
        """)
        
        print(f"发现 {len(rows)} 条缺失数据记录")
        
        # 统计汇总
        pe_count = sum(1 for r in rows if r['missing_pe'] == 'Y')
        pb_count = sum(1 for r in rows if r['missing_pb'] == 'Y')
        roe_count = sum(1 for r in rows if r['missing_roe'] == 'Y')
        roa_count = sum(1 for r in rows if r['missing_roa'] == 'Y')
        profit_count = sum(1 for r in rows if r['missing_profit_growth'] == 'Y')
        revenue_count = sum(1 for r in rows if r['missing_revenue_growth'] == 'Y')
        
        print(f"缺失PE: {pe_count} 条")
        print(f"缺失PB: {pb_count} 条")
        print(f"缺失ROE: {roe_count} 条")
        print(f"缺失ROA: {roa_count} 条")
        print(f"缺失利润增速: {profit_count} 条")
        print(f"缺失营收增速: {revenue_count} 条")
        
        # 写入CSV文件
        output_file = '/Users/apple/Desktop/ai_huahua/ai_quant/missing_data_report.csv'
        with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                '股票代码', '报告日期', '缺失PE', '缺失PB', '缺失ROE', '缺失ROA', 
                '缺失利润增速', '缺失营收增速', '数据源'
            ])
            for row in rows:
                writer.writerow([
                    row['stock_code'],
                    row['report_date'],
                    row['missing_pe'],
                    row['missing_pb'],
                    row['missing_roe'],
                    row['missing_roa'],
                    row['missing_profit_growth'],
                    row['missing_revenue_growth'],
                    row['data_source']
                ])
        
        print(f"CSV文件已生成: {output_file}")
        print(f"报告生成耗时: {(datetime.now() - start_time).total_seconds():.2f}秒")
        
    finally:
        conn.close()


if __name__ == "__main__":
    generate_report()
