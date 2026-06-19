#!/usr/bin/env python
"""营收增速全量补采脚本 - 从 fina_indicator 的 or_yoy 字段补采"""
import time
import sys
from datetime import datetime

sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from collect_financial_3y import _process_one_stock, _load_daily_basic_cache, _INSERT_SQL
from infra.tushare_client import get_pro_api
from core.db import connect, load_mysql_config, query_dict, executemany


def main():
    print('[%s] === 营收增速全量补采任务启动 ===' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    # 1. 获取缺失股票列表
    conn = connect(load_mysql_config())
    missing_codes = [r['stock_code'] for r in query_dict(
        conn,
        'SELECT DISTINCT stock_code FROM trade_stock_financial WHERE revenue_growth_yoy IS NULL ORDER BY stock_code'
    )]
    print('缺失营收增速的股票: %d 只' % len(missing_codes))
    conn.close()

    if not missing_codes:
        print('无缺失数据，任务结束')
        return

    # 2. 初始化TuShare
    pro = get_pro_api()
    _load_daily_basic_cache(pro)

    # 3. 逐只补采
    total = len(missing_codes)
    processed = 0
    success = 0
    failed = 0
    batch = []
    batch_count = 0
    start_time = time.time()

    conn = connect(load_mysql_config())

    for i, code in enumerate(missing_codes):
        try:
            rows = _process_one_stock(pro, code, '20230101', '20260609')
            if rows:
                batch.extend(rows)
                success += 1
            else:
                failed += 1
        except Exception:
            failed += 1
        processed += 1

        # 批量写入（每30只）
        if len(batch) >= 30:
            try:
                executemany(conn, _INSERT_SQL, batch)
                conn.commit()
                batch_count += len(batch)
                batch = []
            except Exception as e:
                conn.rollback()
                print('[WARN] 批量写入失败: %s' % e)
                batch = []

        # 进度日志（每50只）
        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            speed = processed / elapsed * 60 if elapsed > 0 else 0
            eta = (total - processed) / speed * 60 if speed > 0 else 0
            print('[%s] 进度: %d/%d (%.1f%%) | 成功:%d 失败:%d | 已写入:%d | 速度:%.1f只/分 | 剩余:%.0f分钟' % (
                datetime.now().strftime('%H:%M:%S'), processed, total, processed / total * 100,
                success, failed, batch_count, speed, eta
            ))
            sys.stdout.flush()

        # 请求间隔（避免限流）
        time.sleep(2.0)

    # 写入剩余数据
    if batch:
        try:
            executemany(conn, _INSERT_SQL, batch)
            conn.commit()
            batch_count += len(batch)
        except Exception as e:
            conn.rollback()
            print('[WARN] 最终写入失败: %s' % e)

    conn.close()
    elapsed = time.time() - start_time
    print('')
    print('=== 补采任务完成 ===')
    print('总耗时: %.0f 分钟' % (elapsed / 60))
    print('处理股票: %d 只' % processed)
    print('成功: %d | 失败: %d' % (success, failed))
    print('写入记录: %d 条' % batch_count)


if __name__ == '__main__':
    main()
