#!/usr/bin/env python
"""营收增速补采 - 轻量版，只调 fina_indicator 一个接口"""
import time
import sys
from datetime import datetime

sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from infra.tushare_client import get_pro_api
from core.db import connect, load_mysql_config, query_dict, execute


def main():
    print('[%s] === 营收增速补采（轻量版）===' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    conn = connect(load_mysql_config())

    # 1. 获取缺失股票列表
    missing_codes = [r['stock_code'] for r in query_dict(
        conn,
        'SELECT DISTINCT stock_code FROM trade_stock_financial WHERE revenue_growth_yoy IS NULL ORDER BY stock_code'
    )]
    total = len(missing_codes)
    print('缺失营收增速的股票: %d 只' % total)
    conn.close()

    if not missing_codes:
        print('无缺失数据')
        return

    pro = get_pro_api()
    conn = connect(load_mysql_config())

    success = 0
    failed = 0
    updated = 0
    start_time = time.time()

    for i, code in enumerate(missing_codes):
        try:
            # 只调 fina_indicator，取 or_yoy
            for attempt in range(5):
                try:
                    df = pro.fina_indicator(ts_code=code, start_date='20230101', end_date='20260609',
                                            fields='ts_code,end_date,or_yoy')
                    break
                except Exception as e:
                    if attempt < 4 and ('Connection' in type(e).__name__ or '请求速度过快' in str(e)):
                        wait = 3 * (attempt + 1)
                        time.sleep(wait)
                    else:
                        raise

            if df is not None and len(df) > 0:
                count = 0
                for _, row in df.iterrows():
                    or_yoy = row.get('or_yoy')
                    end_date = row.get('end_date')
                    if or_yoy is not None and end_date is not None:
                        execute(
                            conn,
                            'UPDATE trade_stock_financial SET revenue_growth_yoy = %s WHERE stock_code = %s AND report_date = %s',
                            (float(or_yoy), code, str(end_date))
                        )
                        count += 1
                conn.commit()
                updated += count
                success += 1
            else:
                failed += 1
        except Exception:
            failed += 1

        # 进度日志
        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            speed = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            eta = (total - i - 1) / speed * 60 if speed > 0 else 0
            print('[%s] %d/%d (%.1f%%) | 成功:%d 失败:%d | 更新:%d条 | %.1f只/分 | 剩余%.0f分' % (
                datetime.now().strftime('%H:%M:%S'), i + 1, total, (i + 1) / total * 100,
                success, failed, updated, speed, eta
            ))
            sys.stdout.flush()

        time.sleep(1.0)

    conn.close()
    elapsed = time.time() - start_time
    print('')
    print('=== 完成 ===')
    print('耗时: %.0f 分钟' % (elapsed / 60))
    print('成功: %d | 失败: %d | 更新记录: %d' % (success, failed, updated))


if __name__ == '__main__':
    main()
