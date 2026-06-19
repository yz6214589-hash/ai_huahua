#!/usr/bin/env python
"""使用QMT补采营收增速 - 通过本期营收÷去年同期营收计算（修复版）"""
import time
import sys
import traceback
from datetime import datetime

sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

from infra.qmt_gateway_client import get_financial_data
from core.db import connect, load_mysql_config, query_dict, execute


def _safe_float(val):
    """安全转换为float，失败返回None"""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f or f in (float('inf'), float('-inf')):  # nan/inf
            return None
        return f
    except (ValueError, TypeError):
        return None


def calc_revenue_yoy_from_qmt(rows):
    """从QMT财务数据计算营收增速"""
    rev_map = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        ed = r.get('报告期') or r.get('end_date') or r.get('报告日期')
        rev = _safe_float(r.get('营业收入') or r.get('total_revenue') or r.get('revenue'))
        if ed and rev is not None:
            rev_map[str(ed)] = rev

    result = {}
    for ed, rev in rev_map.items():
        s = str(ed).replace('-', '').replace('/', '')
        if len(s) < 6:
            continue
        year = int(s[:4])
        month = int(s[4:6])
        prev_year_prefix = f"{year - 1}{month:02d}"
        prev_key = None
        for pk in rev_map:
            pk_clean = str(pk).replace('-', '').replace('/', '')
            if pk_clean[:6] == prev_year_prefix:
                prev_key = pk
                break
        if prev_key and rev_map[prev_key] != 0:
            yoy = (rev - rev_map[prev_key]) / rev_map[prev_key] * 100
            result[ed] = round(yoy, 4)
    return result


def _normalize_date(ed):
    """将各种日期格式统一为 YYYY-MM-DD"""
    s = str(ed).replace('/', '-').replace('.', '-')
    digits = s.replace('-', '')
    if len(digits) == 8:
        return '%s-%s-%s' % (digits[:4], digits[4:6], digits[6:8])
    return s


def main():
    print('[%s] === QMT营收增速补采任务启动（修复版）===' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    conn = connect(load_mysql_config())
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

    conn = connect(load_mysql_config())
    success = 0
    failed = 0
    updated = 0
    no_data = 0
    fail_details = []  # 记录失败详情
    start_time = time.time()

    for i, code in enumerate(missing_codes):
        try:
            data = get_financial_data(code, max_rows=12)

            # 兼容多种返回格式
            if isinstance(data, dict):
                rows = data.get('rows') or data.get('data') or []
            elif isinstance(data, list):
                rows = data
            else:
                rows = []

            if not rows:
                no_data += 1
                continue

            yoy_map = calc_revenue_yoy_from_qmt(rows)

            if not yoy_map:
                no_data += 1
                continue

            count = 0
            for ed, yoy_val in yoy_map.items():
                report_date = _normalize_date(ed)
                execute(
                    conn,
                    'UPDATE trade_stock_financial SET revenue_growth_yoy = %s WHERE stock_code = %s AND report_date = %s AND revenue_growth_yoy IS NULL',
                    (yoy_val, code, report_date)
                )
                count += 1
            conn.commit()
            updated += count
            success += 1

        except Exception as e:
            failed += 1
            err_msg = str(e)[:100]
            if len(fail_details) < 20:  # 只记录前20个失败的详情
                fail_details.append((code, err_msg))

        # 进度日志（每50只）
        if (i + 1) % 50 == 0 or (i + 1) == total:
            elapsed = time.time() - start_time
            speed = (i + 1) / elapsed * 60 if elapsed > 0 else 0
            eta_min = (total - i - 1) / speed * 60 if speed > 0 else 0
            print('[%s] %d/%d (%.1f%%) | OK:%d FAIL:%d NODATA:%d | UPD:%d | %.1f/min | ETA %.0fmin' % (
                datetime.now().strftime('%H:%M:%S'), i + 1, total, (i + 1) / total * 100,
                success, failed, no_data, updated, speed, eta_min
            ))
            sys.stdout.flush()

        # QMT请求间隔
        time.sleep(0.3)

    conn.close()
    elapsed = time.time() - start_time
    print('')
    print('=== QMT补采任务完成 ===')
    print('总耗时: %.0f 分钟' % (elapsed / 60))
    print('成功: %d | 失败: %d | 无数据: %d' % (success, failed, no_data))
    print('更新记录: %d 条' % updated)
    if fail_details:
        print('失败详情（前20个）:')
        for code, msg in fail_details:
            print('  %s: %s' % (code, msg))


if __name__ == '__main__':
    main()
