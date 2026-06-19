#!/usr/bin/env python3
"""
使用 Tushare 采集最近 3 年的财务数据

数据源：tushare fina_indicator / income / balancesheet / daily_basic
时间范围：近 3 年（2023-01-01 至今）
"""

from __future__ import annotations

import sys
sys.path.insert(0, '/Users/apple/Desktop/ai_huahua/ai_quant/backend')

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

import pymysql

from core.db import executemany, load_mysql_config
from infra.tushare_client import get_pro_api


# ============== SQL 模板 ==============

_INSERT_SQL = """
INSERT INTO trade_stock_financial
(stock_code, report_date, revenue, net_profit, eps, roe, roa, gross_margin, net_margin,
 debt_ratio, current_ratio, operating_cashflow, total_assets, total_equity,
 pe_ttm, pb, market_cap, float_market_cap,
 profit_growth_yoy, revenue_growth_yoy,
 ebitda, quick_ratio, total_asset_turnover, retained_earnings, data_source, created_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
ON DUPLICATE KEY UPDATE
revenue=COALESCE(VALUES(revenue), revenue),
net_profit=COALESCE(VALUES(net_profit), net_profit),
eps=COALESCE(VALUES(eps), eps),
roe=COALESCE(VALUES(roe), roe),
roa=COALESCE(VALUES(roa), roa),
gross_margin=COALESCE(VALUES(gross_margin), gross_margin),
net_margin=COALESCE(VALUES(net_margin), net_margin),
debt_ratio=COALESCE(VALUES(debt_ratio), debt_ratio),
current_ratio=COALESCE(VALUES(current_ratio), current_ratio),
operating_cashflow=COALESCE(VALUES(operating_cashflow), operating_cashflow),
total_assets=COALESCE(VALUES(total_assets), total_assets),
total_equity=COALESCE(VALUES(total_equity), total_equity),
pe_ttm=COALESCE(VALUES(pe_ttm), pe_ttm),
pb=COALESCE(VALUES(pb), pb),
market_cap=COALESCE(VALUES(market_cap), market_cap),
float_market_cap=COALESCE(VALUES(float_market_cap), float_market_cap),
profit_growth_yoy=COALESCE(VALUES(profit_growth_yoy), profit_growth_yoy),
revenue_growth_yoy=COALESCE(VALUES(revenue_growth_yoy), revenue_growth_yoy),
ebitda=COALESCE(VALUES(ebitda), ebitda),
quick_ratio=COALESCE(VALUES(quick_ratio), quick_ratio),
total_asset_turnover=COALESCE(VALUES(total_asset_turnover), total_asset_turnover),
retained_earnings=COALESCE(VALUES(retained_earnings), retained_earnings),
data_source=VALUES(data_source)
"""


# ============== 工具函数 ==============

def _safe_float(v: Any) -> float | None:
    """将任意值安全转换为 float，None/NaN/Inf/越界 返回 None"""
    if v is None:
        return None
    try:
        import math
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        # 限制范围避免超过 decimal(10,4)/decimal(20,2) 等字段精度
        if x > 99999999999999 or x < -99999999999999:
            return None
        # 保留 4 位小数
        return round(x, 4)
    except (ValueError, TypeError):
        return None


def _tushare_call_with_retry(pro, fn_name, max_retries=5, base_sleep=2, **kwargs):
    """对 tushare 接口进行带限流重试的调用

    遇到 "请求速度过快" 等限流错误时，按指数退避策略重试
    """
    fn = getattr(pro, fn_name)
    last_error = None
    for attempt in range(max_retries):
        try:
            df = fn(**kwargs)
            return df
        except Exception as e:
            err_msg = str(e)
            last_error = e
            # 限流类错误或网络连接错误：指数退避
            if "请求速度过快" in err_msg or "限流" in err_msg or "rate limit" in err_msg.lower() or "frequency" in err_msg.lower() or "Connection" in type(e).__name__ or "ConnectionReset" in err_msg or "Connection aborted" in err_msg:
                wait_sec = base_sleep * (2 ** attempt)
                if wait_sec > 60:
                    wait_sec = 60
                _log(f"    [重试] {fn_name} {kwargs.get('ts_code','')} 等待 {wait_sec}s ({attempt+1}/{max_retries}) {type(e).__name__}")
                time.sleep(wait_sec)
            else:
                # 其他错误直接抛出
                raise
    # 全部重试失败，抛出最后一次错误
    raise last_error


def _log(msg: str) -> None:
    """打印带时间戳的日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


# ============== 数据采集函数 ==============

def _is_a_share_stock(code: str) -> bool:
    """判断是否为真正的A股（排除指数、ETF/LOF/REITs等非个股品种）

    真正A股的代码规则：
    - 上海(SH): 600xxx, 601xxx, 603xxx, 605xxx, 688xxx（科创板）
    - 深圳(SZ): 000xxx, 001xxx, 002xxx, 003xxx, 300xxx, 301xxx（创业板）
    """
    parts = code.split(".")
    if len(parts) != 2:
        return False
    num = parts[0]
    exchange = parts[1].upper()

    if exchange == "SH":
        return num.startswith(("600", "601", "603", "605", "688"))
    elif exchange == "SZ":
        return num.startswith(("000", "001", "002", "003", "300", "301"))
    return False


def _get_stock_list(cfg) -> list[str]:
    """从数据库 trade_stock_master 获取所有股票代码并过滤非A股"""
    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT stock_code FROM trade_stock_master
                ORDER BY stock_code
            """)
            all_codes = [r['stock_code'] for r in cur.fetchall()]
            # 过滤非A股品种（指数、ETF/LOF等）
            a_share_codes = [c for c in all_codes if _is_a_share_stock(c)]
            filtered = len(all_codes) - len(a_share_codes)
            if filtered > 0:
                _log(f"过滤掉 {filtered} 只非A股品种（指数、ETF等），保留 {len(a_share_codes)} 只")
            return a_share_codes
    finally:
        conn.close()


def _get_fina_indicator(pro, ts_code: str, start_date: str, end_date: str) -> list[dict]:
    """获取 tushare fina_indicator 财务指标数据

    字段映射注意：
    - tushare 的 gross_margin 是"毛利"（金额，元），不是毛利率
    - 毛利率应该用 grossprofit_margin（百分比）
    """
    try:
        df = _tushare_call_with_retry(pro, 'fina_indicator', ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or len(df) == 0:
            return []
        # 按 end_date 去重，保留 update_flag=1 的最新记录
        results = []
        for _, row in df.iterrows():
            end_date_val = row.get('end_date')
            if end_date_val is None:
                continue
            results.append({
                'end_date': str(end_date_val),
                'eps': _safe_float(row.get('eps')),
                # 注意：tushare 的 gross_margin 是毛利金额，应使用 grossprofit_margin（毛利率，百分比）
                'gross_margin': _safe_float(row.get('grossprofit_margin')),
                'current_ratio': _safe_float(row.get('current_ratio')),
                'quick_ratio': _safe_float(row.get('quick_ratio')),
                'ebitda': _safe_float(row.get('ebitda')),
                'bps': _safe_float(row.get('bps')),
                'ocfps': _safe_float(row.get('ocfps')),
                'retained_earnings': _safe_float(row.get('retained_earnings')),
                'net_margin': _safe_float(row.get('netprofit_margin')),
                'roe': _safe_float(row.get('roe')),
                'roa': _safe_float(row.get('roa')),
                'debt_ratio': _safe_float(row.get('debt_to_assets')),
                'total_asset_turnover': _safe_float(row.get('assets_turn')),
                'yoy_net_profit': _safe_float(row.get('netprofit_yoy')),
                'yoy_revenue': _safe_float(row.get('or_yoy')),
                'yoy_equity': _safe_float(row.get('eqt_yoy')),
            })
        return results
    except Exception as e:
        _log(f"  [{ts_code}] fina_indicator 失败: {type(e).__name__}: {e}")
        return []


def _get_income_data(pro, ts_code: str, start_date: str, end_date: str) -> dict[str, dict]:
    """获取 tushare income 利润表数据，按 end_date 分组"""
    try:
        df = _tushare_call_with_retry(pro, 'income', ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or len(df) == 0:
            return {}
        result = {}
        for _, row in df.iterrows():
            ed = str(row.get('end_date') or '')
            if not ed:
                continue
            # update_flag=1 的优先
            if ed in result and result[ed].get('update_flag', 0) >= _safe_float(row.get('update_flag')):
                continue
            result[ed] = {
                'revenue': _safe_float(row.get('revenue') or row.get('total_revenue') or row.get('operate_revenue')),
                'net_profit': _safe_float(row.get('n_income_attr_p') or row.get('net_profit')),
                'yoy_revenue': _safe_float(row.get('revenue_yoy') or row.get('total_revenue_yoy')),
                'update_flag': _safe_float(row.get('update_flag')) or 0,
            }
        return result
    except Exception as e:
        _log(f"  [{ts_code}] income 失败: {type(e).__name__}: {e}")
        return {}


def _get_balancesheet_data(pro, ts_code: str, start_date: str, end_date: str) -> dict[str, dict]:
    """获取 tushare balancesheet 资产负债表数据"""
    try:
        df = _tushare_call_with_retry(pro, 'balancesheet', ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is None or len(df) == 0:
            return {}
        result = {}
        for _, row in df.iterrows():
            ed = str(row.get('end_date') or '')
            if not ed:
                continue
            if ed in result and result[ed].get('update_flag', 0) >= _safe_float(row.get('update_flag')):
                continue
            result[ed] = {
                'total_assets': _safe_float(row.get('total_assets')),
                'total_equity': _safe_float(row.get('total_hldr_eqy_exc_min_int') or row.get('total_hldr_eqy_inc_min_int') or row.get('total_equity')),
                'update_flag': _safe_float(row.get('update_flag')) or 0,
            }
        return result
    except Exception as e:
        _log(f"  [{ts_code}] balancesheet 失败: {type(e).__name__}: {e}")
        return {}


def _get_daily_basic(pro, ts_code: str) -> dict[str, Any]:
    """获取 tushare daily_basic 最新行情数据（PE/PB/市值）"""
    try:
        df = _tushare_call_with_retry(pro, 'daily_basic', ts_code=ts_code, limit=1)
        if df is None or len(df) == 0:
            return {}
        row = df.iloc[0]
        return {
            'pe_ttm': _safe_float(row.get('pe_ttm')),
            'pb': _safe_float(row.get('pb')),
            'market_cap': _safe_float(row.get('total_mv')),
            'float_market_cap': _safe_float(row.get('circ_mv')),
        }
    except Exception as e:
        _log(f"  [{ts_code}] daily_basic 失败: {type(e).__name__}: {e}")
        return {}


# ============== 主处理函数 ==============

# 全市场 daily_basic 缓存（启动时拉取一次，所有股票共享）
_DAILY_BASIC_CACHE: dict[str, dict[str, Any]] = {}
_DAILY_BASIC_LOADED = False


def _load_daily_basic_cache(pro) -> None:
    """启动时拉取一次全市场 daily_basic，所有股票共享

    节省：原来 1 只股票 1 次 daily_basic 调用，5000 只 = 5000 次调用
    优化后：1 次调用，缓存全市场数据
    """
    global _DAILY_BASIC_CACHE, _DAILY_BASIC_LOADED
    if _DAILY_BASIC_LOADED:
        return
    try:
        _log("正在预加载全市场 daily_basic 缓存...")
        # 取最近 1 个交易日
        df = _tushare_call_with_retry(pro, 'daily_basic', limit=5000)
        if df is not None and len(df) > 0:
            for _, row in df.iterrows():
                ts_code = str(row.get('ts_code') or '')
                if ts_code:
                    _DAILY_BASIC_CACHE[ts_code] = {
                        'pe_ttm': _safe_float(row.get('pe_ttm')),
                        'pb': _safe_float(row.get('pb')),
                        'market_cap': _safe_float(row.get('total_mv')),
                        'float_market_cap': _safe_float(row.get('circ_mv')),
                    }
            _log(f"  daily_basic 缓存完成: {len(_DAILY_BASIC_CACHE)} 只股票")
        _DAILY_BASIC_LOADED = True
    except Exception as e:
        _log(f"  daily_basic 缓存失败: {e}，将回退到单只查询")
        _DAILY_BASIC_LOADED = True  # 标记为已加载，避免反复尝试


def _get_market_data_from_cache(ts_code: str) -> dict[str, Any]:
    """从缓存获取行情数据"""
    return _DAILY_BASIC_CACHE.get(ts_code, {})


def _process_one_stock(pro, ts_code: str, start_date: str, end_date: str) -> list[tuple]:
    """处理单只股票，返回批量写入的元组列表

    优化策略：
    - daily_basic 改为全市场缓存（启动时拉取一次，所有股票共享）
    - fina_indicator 串行调用
    - income 和 balancesheet 并发调用（减少等待时间）
    - 单只股票耗时约 20-24 秒（优化约 30%）
    """
    try:
        # 1. 获取财务指标（串行）
        fina_list = _get_fina_indicator(pro, ts_code, start_date, end_date)
        if not fina_list:
            return []

        # 2. 并发获取 income 和 balance 数据
        # 两个接口并发请求，网络等待时间重叠，节省约 1/3 时间
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_income = ex.submit(_get_income_data, pro, ts_code, start_date, end_date)
            f_balance = ex.submit(_get_balancesheet_data, pro, ts_code, start_date, end_date)
            income_map = f_income.result()
            balance_map = f_balance.result()

        # 3. 行情数据从缓存获取（不需调用 tushare）
        market_data = _get_market_data_from_cache(ts_code)

        # 4. 合并数据
        rows = []
        for fina in fina_list:
            ed = fina['end_date']
            income = income_map.get(ed, {})
            balance = balance_map.get(ed, {})

            row = (
                ts_code,
                ed,  # report_date
                income.get('revenue'),
                income.get('net_profit'),
                fina.get('eps'),
                fina.get('roe'),
                fina.get('roa'),
                fina.get('gross_margin'),
                fina.get('net_margin'),
                fina.get('debt_ratio'),
                fina.get('current_ratio'),
                fina.get('ocfps'),
                balance.get('total_assets'),
                balance.get('total_equity'),
                market_data.get('pe_ttm'),
                market_data.get('pb'),
                market_data.get('market_cap'),
                market_data.get('float_market_cap'),
                fina.get('yoy_net_profit'),
                fina.get('yoy_revenue') if fina.get('yoy_revenue') is not None else income.get('yoy_revenue'),
                fina.get('ebitda'),
                fina.get('quick_ratio'),
                fina.get('total_asset_turnover'),
                fina.get('retained_earnings'),
                'tushare',
            )
            rows.append(row)

        return rows
    except Exception as e:
        _log(f"  [{ts_code}] 处理失败: {type(e).__name__}: {e}")
        return []


# ============== 主入口 ==============

def main():
    _log("=" * 80)
    _log("开始 Tushare 财务数据采集（近 3 年）")
    _log("=" * 80)

    # 1. 计算时间范围：近 3 年
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=3 * 365 + 30)).strftime("%Y%m%d")
    _log(f"采集时间范围: {start_date} 至 {end_date}")

    # 2. 加载配置
    cfg = load_mysql_config()
    pro = get_pro_api()

    # 3. 获取股票列表
    _log("获取股票列表...")
    codes = _get_stock_list(cfg)
    _log(f"共 {len(codes)} 只股票")

    # 3.1 预加载全市场 daily_basic 缓存
    _load_daily_basic_cache(pro)

    # 断点续传：默认跳过已采集的股票
    if "--no-skip" not in sys.argv:
        conn_check = pymysql.connect(
            host=cfg.host, port=cfg.port, user=cfg.user,
            password=cfg.password, database=cfg.database,
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
        )
        try:
            with conn_check.cursor() as cur:
                cur.execute("SELECT DISTINCT stock_code FROM trade_stock_financial")
                done = {r['stock_code'] for r in cur.fetchall()}
        finally:
            conn_check.close()
        before = len(codes)
        codes = [c for c in codes if c not in done]
        _log(f"断点续传: 跳过已采集 {before - len(codes)} 只, 剩余 {len(codes)} 只待处理")

    # 测试模式：只处理前 N 只
    test_mode = "--test" in sys.argv
    test_count = 5
    if test_mode:
        codes = codes[:test_count]
        _log(f"测试模式：只处理前 {test_count} 只股票: {codes}")

    # 4. 双线程处理
    # 2 线程，每个线程内部 fina 串行 + income/balance 并发
    # 实测：单只股票约 26s，2 线程理论速度 ≈ 4.6 只/分钟
    max_workers = 2
    batch_size = 500
    request_interval = 0.1  # 单只股票处理完后等待 0.1 秒，避免双线程同时发起请求
    # 每 30 秒打印一次进度
    progress_interval = 30
    processed = 0
    total_rows = 0
    last_log_time = time.time()
    last_log_processed = 0  # 上次打印进度时的已处理数
    failed_codes = []

    _log(f"启动 {max_workers} 线程并发处理...")

    conn = pymysql.connect(
        host=cfg.host, port=cfg.port, user=cfg.user,
        password=cfg.password, database=cfg.database,
        charset='utf8mb4'
    )
    batch = []

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 交错提交任务，避免双线程同时发起 API 请求
            future_to_code = {}
            for i, code in enumerate(codes):
                future_to_code[executor.submit(_process_one_stock, pro, code, start_date, end_date)] = code
                if i < 2:
                    # 前 2 个任务间隔 0.5s 提交，错开 API 请求时机
                    time.sleep(0.5)

            for future in as_completed(future_to_code):
                code = future_to_code[future]
                processed += 1
                try:
                    rows = future.result(timeout=60)
                except Exception as e:
                    _log(f"  [{processed}/{len(codes)}] {code} 异常: {e}")
                    failed_codes.append(code)
                    continue

                if rows:
                    batch.extend(rows)
                    total_rows += len(rows)

                # 单只股票间加间隔，避免 tushare 限流
                if request_interval > 0 and processed < len(codes):
                    time.sleep(request_interval)

                # 每 30 秒打印一次进度
                now = time.time()
                if processed == 1 or (now - last_log_time) >= progress_interval or processed == len(codes):
                    elapsed = now - last_log_time
                    delta = processed - last_log_processed  # 增量处理数
                    speed = delta / max(elapsed, 1) * 60 if delta > 0 else 0
                    _log(f"  进度: {processed}/{len(codes)}, 已采集 {total_rows:,} 条, 速度 {speed:.1f} 只/分钟")
                    last_log_time = now
                    last_log_processed = processed

                # 中间提交
                if len(batch) >= batch_size:
                    try:
                        conn.ping(reconnect=True)
                    except Exception:
                        conn.close()
                        conn = pymysql.connect(
                            host=cfg.host, port=cfg.port, user=cfg.user,
                            password=cfg.password, database=cfg.database,
                            charset='utf8mb4'
                        )
                    try:
                        written = executemany(conn, _INSERT_SQL, batch)
                        conn.commit()
                        _log(f"  [中间提交] 写入 {written} 行 (累计 {total_rows:,})")
                    except Exception as e:
                        # 逐条插入找出问题行
                        _log(f"  [中间提交失败] {e}, 尝试逐条定位问题行...")
                        cur = conn.cursor()
                        ok_count = 0
                        for i, row in enumerate(batch):
                            try:
                                cur.execute(_INSERT_SQL, row)
                                ok_count += 1
                            except Exception as row_e:
                                _log(f"    问题行[{i}]: {row}")
                                _log(f"    错误: {row_e}")
                        conn.commit()
                        cur.close()
                        _log(f"  逐条完成: 成功 {ok_count}/{len(batch)}")
                    batch.clear()

        # 5. 提交剩余批次
        if batch:
            try:
                conn.ping(reconnect=True)
            except Exception:
                conn.close()
                conn = pymysql.connect(
                    host=cfg.host, port=cfg.port, user=cfg.user,
                    password=cfg.password, database=cfg.database,
                    charset='utf8mb4'
                )
            written = executemany(conn, _INSERT_SQL, batch)
            conn.commit()
            _log(f"  [最终提交] 写入 {written} 行")

    finally:
        conn.close()

    _log("=" * 80)
    _log(f"采集完成: 处理 {processed} 只, 写入 {total_rows:,} 条, 失败 {len(failed_codes)} 只")
    if failed_codes:
        _log(f"失败股票: {failed_codes[:20]}")
    _log("=" * 80)


if __name__ == "__main__":
    main()
