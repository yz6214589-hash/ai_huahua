"""
财务数据采集任务（QMT + TuShare + AkShare）
数据源优先级：QMT Gateway > TuShare > AkShare > 数据库回退

功能：
1. 使用QMT获取行情数据（收盘价）
2. 使用QMT获取财务指标（ROE、毛利率、营收等，从4张财务报表提取）
3. QMT失败时使用TuShare作为备选
4. TuShare失败时使用AkShare作为最终备选
5. 计算衍生指标
6. 写入数据库
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError, as_completed
from datetime import datetime
from threading import Lock
from typing import Any, Optional
import time

import pandas as pd

from core.db import MySQLConfig, connect, executemany, query_dict
from core.jobs.common import JobStats, normalize_stock_code, safe_float, to_ymd
from infra.storage.logging_service import get_logger

logger = get_logger("stock_financial")

# 全市场 daily_basic 缓存（启动时拉取一次，所有股票共享）
_DAILY_BASIC_CACHE: dict[str, dict[str, Any]] = {}
_DAILY_BASIC_LOADED = False


def _log(msg: str):
    """打印带时间戳的日志（同时输出到控制台和日志系统）

    Args:
        msg: 日志消息内容
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [stock_financial] {msg}")
    logger.info(msg)


def _load_daily_basic_cache() -> None:
    """
    启动时拉取一次全市场 daily_basic，所有股票共享，减少重复API调用
    
    使用 TuShare 的 daily_basic 接口批量获取 PE、PB、市值等行情数据
    """
    global _DAILY_BASIC_CACHE, _DAILY_BASIC_LOADED
    if _DAILY_BASIC_LOADED:
        return
    
    _log("正在预加载全市场 daily_basic 缓存...")
    try:
        from infra.tushare_client import get_pro_api
        pro = get_pro_api()
        
        df = pro.daily_basic(limit=5000)
        if df is None or len(df) == 0:
            _log("  daily_basic 接口返回空数据")
            _DAILY_BASIC_LOADED = True
            return
        
        for _, row in df.iterrows():
            ts_code = str(row.get('ts_code') or '')
            if ts_code:
                _DAILY_BASIC_CACHE[ts_code] = {
                    'pe_ttm': safe_float(row.get('pe_ttm')),
                    'pb': safe_float(row.get('pb')),
                    'market_cap': safe_float(row.get('total_mv')),
                    'float_market_cap': safe_float(row.get('circ_mv')),
                    'close': safe_float(row.get('close')),
                }
        _log(f"  daily_basic 缓存完成: {len(_DAILY_BASIC_CACHE)} 只股票")
    except Exception as e:
        _log(f"  daily_basic 缓存失败: {type(e).__name__}: {e}，将回退到单只查询")
    finally:
        _DAILY_BASIC_LOADED = True


def _get_daily_basic_from_cache(stock_code: str) -> dict[str, Any] | None:
    """
    从缓存获取股票的 daily_basic 数据
    
    Args:
        stock_code: 股票代码
        
    Returns:
        dict | None: daily_basic 数据（包含 pe_ttm, pb, market_cap, float_market_cap, close）
    """
    return _DAILY_BASIC_CACHE.get(stock_code)


_INSERT_SQL = """
INSERT INTO trade_stock_financial
(stock_code, report_date, revenue, net_profit, eps, roe, roa, gross_margin, net_margin,
 debt_ratio, current_ratio, operating_cashflow, total_assets, total_equity,
 pe_ttm, pb, market_cap, float_market_cap,
 profit_growth_yoy, revenue_growth_yoy,
 data_source, created_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
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
data_source=VALUES(data_source)
"""


def _infer_exchange(code_num: str) -> str:
    """根据股票代码推断交易所"""
    if code_num.startswith("6"):
        return "SH"
    return "SZ"


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


def _get_stock_list_from_db(cfg: MySQLConfig, max_stocks: int) -> list[str]:
    """
    从数据库获取已有数据的股票列表

    Args:
        cfg: 数据库配置
        max_stocks: 最大股票数量（0表示无限制）

    Returns:
        list[str]: 股票代码列表
    """
    try:
        conn = connect(cfg)
        try:
            if max_stocks > 0:
                sql = "SELECT DISTINCT stock_code FROM trade_stock_financial ORDER BY stock_code LIMIT %s"
                params = (max_stocks,)
            else:
                sql = "SELECT DISTINCT stock_code FROM trade_stock_financial ORDER BY stock_code"
                params = ()
            rows = query_dict(conn, sql, params)
            return [r["stock_code"] for r in rows if _is_a_share_stock(r["stock_code"])]
        finally:
            conn.close()
    except Exception as e:
        _log(f"从数据库获取股票列表失败: {e}")
        return []


def _get_stock_list_qmt_or_akshare(test_mode: bool, test_stock: str, max_stocks: int) -> list[str]:
    """
    获取股票列表

    测试模式返回指定股票，非测试模式从 QMT Gateway 获取全市场A股列表。

    Args:
        test_mode: 是否为测试模式
        test_stock: 测试股票代码
        max_stocks: 最大股票数量

    Returns:
        list[str]: 股票代码列表
    """
    if test_mode:
        s = normalize_stock_code(test_stock)
        return [s] if s else []

    # 从 QMT Gateway 获取全市场A股列表
    _log("从 QMT Gateway 获取全市场A股列表...")
    try:
        from infra.qmt_gateway_client import get_stock_list as _qmt_stock_list
        all_codes = _qmt_stock_list()
        if not all_codes:
            _log("QMT Gateway 返回空列表")
            return []
        codes = all_codes[:max_stocks] if max_stocks > 0 else all_codes
        # 规范化股票代码格式，防止 QMT Gateway 返回双后缀（如 000026.SZ.SZ）
        norm_codes: list[str] = []
        for c in codes:
            parts = c.strip().split(".")
            if len(parts) >= 2:
                # 取前两部分：代码 + 交易所，去除多余后缀
                norm_codes.append(f"{parts[0]}.{parts[1].upper()}")
            else:
                s = normalize_stock_code(c)
                if s:
                    norm_codes.append(s)
        # 过滤非A股品种（指数、ETF/LOF等）
        a_share_codes = [c for c in norm_codes if _is_a_share_stock(c)]
        filtered = len(norm_codes) - len(a_share_codes)
        if filtered > 0:
            _log(f"过滤掉 {filtered} 只非A股品种（指数、ETF等）")
        _log(f"获取到 {len(all_codes)} 只股票，取前 {len(a_share_codes)} 只")
        return a_share_codes
    except Exception as e:
        _log(f"QMT Gateway 获取股票列表失败: {type(e).__name__}: {e}")
        return []


def _compute_yoy_growth(financial_list: list[dict]) -> list[dict]:
    """
    为每条财务数据计算同比增长率

    对每条记录，尝试找到去年同期（年份-1，同月同日）的数据来对比。
    如果找不到精确匹配，找最近的前一年记录来近似。
    """
    if len(financial_list) < 2:
        return financial_list

    sorted_list = sorted(financial_list, key=lambda x: x.get("report_date", ""))

    date_to_data: dict[str, dict] = {}
    for item in sorted_list:
        rpt = item.get("report_date", "")
        if rpt:
            date_to_data[rpt] = item

    from datetime import datetime as dt_mod
    from dateutil.relativedelta import relativedelta

    for item in sorted_list:
        rpt = item.get("report_date", "")
        if not rpt:
            continue
        try:
            # 兼容两种日期格式：2023-06-30 和 20230630
            rpt_clean = rpt.replace("-", "")
            if len(rpt_clean) == 8:
                current_date = dt_mod.strptime(rpt_clean, "%Y%m%d")
            else:
                current_date = dt_mod.strptime(rpt, "%Y-%m-%d")
            target_date = current_date - relativedelta(years=1)
            target_str = target_date.strftime("%Y-%m-%d")
            # 同时准备不带横线的格式
            target_str_compact = target_date.strftime("%Y%m%d")

            prev_data = None
            if target_str in date_to_data:
                prev_data = date_to_data[target_str]
            elif target_str_compact in date_to_data:
                prev_data = date_to_data[target_str_compact]

            if prev_data:
                prev_revenue = prev_data.get("revenue")
                cur_revenue = item.get("revenue")
                if prev_revenue and cur_revenue and prev_revenue != 0:
                    growth = (cur_revenue - prev_revenue) / abs(prev_revenue)
                    item["revenue_growth_yoy"] = round(growth * 100, 4)

                prev_profit = prev_data.get("net_profit")
                cur_profit = item.get("net_profit")
                if prev_profit and cur_profit and prev_profit != 0:
                    growth = (cur_profit - prev_profit) / abs(prev_profit)
                    item["profit_growth_yoy"] = round(growth * 100, 4)
        except (ValueError, Exception):
            pass

    return sorted_list


def _get_market_data_qmt(stock_code: str) -> dict[str, Any]:
    """
    使用QMT获取股票的实时行情数据

    Returns:
        dict包含: price, pe, pb, market_cap, float_market_cap
    """
    try:
        from infra import qmt_gateway_client

        # 获取最新日线数据
        result = qmt_gateway_client.historical_kline(
            stock_code=stock_code,
            period="1d",
            end_time="",
        )

        rows = result.get("rows") or []
        if not rows:
            return None

        # 最新收盘价
        latest = rows[-1]
        price = safe_float(latest.get("close"))
        if not price:
            return None

        # QMT的K线数据不包含PE/PB/市值
        # 这些数据需要从财务报表或者专门的行情接口获取
        return {
            "price": price,
            "pe": None,
            "pb": None,
            "market_cap": None,
            "float_market_cap": None,
        }
    except Exception as e:
        _log(f"QMT 获取 {stock_code} 行情失败: {e}")
        return None


def _get_market_data_akshare(stock_code: str) -> Optional[dict[str, Any]]:
    """
    使用akshare获取股票的实时行情数据（单只查询）

    Returns:
        dict包含: price, pe, pb, market_cap, float_market_cap
    """
    try:
        import akshare as ak

        code_num = stock_code.split(".")[0]
        df = ak.stock_zh_a_spot_em()

        # 查找该股票
        for _, row in df.iterrows():
            code = str(row.get("代码") or "").strip()
            if code == code_num:
                price = safe_float(row.get("最新价"))
                pe = safe_float(row.get("市盈率（动态）"))
                pb = safe_float(row.get("市净率"))
                market_cap = safe_float(row.get("总市值"))
                float_market_cap = safe_float(row.get("流通市值"))

                return {
                    "price": price,
                    "pe": pe if pe and pe > 0 else None,
                    "pb": pb if pb and pb > 0 else None,
                    "market_cap": market_cap,
                    "float_market_cap": float_market_cap,
                }

        return None
    except Exception as e:
        _log(f"akshare 获取 {stock_code} 行情失败: {e}")
        return None


def _run_with_timeout(func, timeout: int = 30):
    """使用线程池执行函数并设置超时，避免akshare请求卡死"""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError:
            _log(f"函数执行超过 {timeout} 秒，已取消")
            future.cancel()
            return None
        except Exception as e:
            _log(f"函数执行异常: {e}")
            return None


def _get_market_data_from_akshare() -> dict[str, dict[str, Any]]:
    """调用 akshare 获取全市场行情数据，带超时保护"""
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            return {}

        result: dict[str, dict[str, Any]] = {}
        for _, row in df.iterrows():
            code_num = str(row.get("代码") or "").strip()
            if not code_num:
                continue
            pe = safe_float(row.get("市盈率（动态）"))
            pb = safe_float(row.get("市净率"))
            result[code_num] = {
                "price": safe_float(row.get("最新价")),
                "pe": pe if pe and pe > 0 else None,
                "pb": pb if pb and pb > 0 else None,
                "market_cap": safe_float(row.get("总市值")),
                "float_market_cap": safe_float(row.get("流通市值")),
            }
        return result
    except Exception as e:
        _log(f"akshare 获取全市场行情数据失败: {e}")
        return {}


def _get_market_data_from_tushare(stock_codes: list[str]) -> dict[str, dict[str, Any]]:
    """
    使用 TuShare 批量获取股票市场数据（作为 akshare 的备选数据源）

    当 akshare 批量获取市场数据失败或超时时，使用 TuShare 的 daily_basic 接口
    逐只获取股票的 PE、PB、市值等数据。

    Args:
        stock_codes: 股票代码列表

    Returns:
        dict: {stock_code: {price, pe, pb, market_cap, float_market_cap}}
    """
    try:
        from infra.tushare_client import get_pro_api

        pro = get_pro_api()
        result: dict[str, dict[str, Any]] = {}

        _log(f"正在通过 TuShare daily_basic 逐只获取 {len(stock_codes)} 只股票的市场数据...")
        for code in stock_codes:
            try:
                df = pro.daily_basic(ts_code=code, limit=1)
                if df is None or len(df) == 0:
                    continue

                row = df.iloc[0]
                pe = safe_float(row.get("pe"))
                pe_ttm = safe_float(row.get("pe_ttm"))
                pb = safe_float(row.get("pb"))
                total_mv = safe_float(row.get("total_mv"))
                circ_mv = safe_float(row.get("circ_mv"))
                close = safe_float(row.get("close"))

                result[code] = {
                    "price": close,
                    "pe": pe_ttm if pe_ttm else (pe if pe and pe > 0 else None),
                    "pb": pb if pb and pb > 0 else None,
                    "market_cap": total_mv,
                    "float_market_cap": circ_mv,
                }
                time.sleep(0.3)
            except Exception as inner_e:
                _log(f"TuShare daily_basic 获取 {code} 失败: {type(inner_e).__name__}: {inner_e}")
                continue

        _log(f"TuShare 批量获取市场数据完成，成功获取 {len(result)}/{len(stock_codes)} 只")
        return result
    except Exception as e:
        _log(f"TuShare 批量获取市场数据失败: {type(e).__name__}: {e}")
        return {}


def _get_market_data_map(stock_codes: list[str]) -> dict[str, dict[str, Any]]:
    """
    批量获取多只股票的akshare行情数据（带超时保护）

    避免为每只股票重复下载全量市场数据，大幅提升效率
    
    使用 _run_with_timeout 防止网络请求卡死

    Args:
        stock_codes: 股票代码列表

    Returns:
        dict: {stock_code: {price, pe, pb, market_cap, float_market_cap}}
    """
    _log("正在通过 akshare 批量获取全市场行情数据（超时90秒）...")
    code_num_map = _run_with_timeout(_get_market_data_from_akshare, timeout=90)
    if not code_num_map:
        _log("akshare 批量获取市场数据失败或超时，跳过行情兜底")
        return {}

    result: dict[str, dict[str, Any]] = {}
    for code in stock_codes:
        code_num = code.split(".")[0]
        data = code_num_map.get(code_num)
        if data:
            result[code] = data

    _log(f"akshare 批量获取市场数据完成，全市场 {len(code_num_map)} 只，匹配目标 {len(result)} 只")
    return result


def _get_market_data(stock_code: str) -> dict[str, Any]:
    """
    获取股票行情数据

    优先使用QMT，备用akshare

    Args:
        stock_code: 股票代码

    Returns:
        dict: 行情数据
    """
    # 优先尝试QMT
    data = _get_market_data_qmt(stock_code)
    if data and data.get("pe") is not None:
        return data

    # 备用akshare
    data = _get_market_data_akshare(stock_code)
    return data if data else {}




def _normalize_pct(val):
    """
    将比率值统一归一化为百分比形式存储

    QMT返回的比率值存在两种格式：
    - 小数形式：0.1057 表示 10.57%（大部分股票）
    - 百分比形式：45.29 表示 45.29%（少数股票如泽璟制药）

    判断逻辑：如果绝对值小于1，认为是小数形式，乘以100转为百分比
    注意：此函数仅用于单字段判断，对于同一记录中多个比率字段格式一致的场景，
    建议使用 _normalize_pct_batch 批量处理
    """
    if val is None:
        return None
    if abs(val) < 1:
        return round(val * 100, 4)
    return round(val, 4)


def _normalize_pct_batch(roe_val, gross_margin_val, net_margin_val):
    """
    批量归一化同一记录中的比率字段

    核心逻辑：同一只股票同一报告期的所有比率字段格式一致。
    以毛利率(gross_margin)为参照判断格式：
    - 毛利率通常在 5%~95% 之间
    - 如果毛利率 < 1，说明是小数形式（如 0.8976 表示 89.76%），所有比率字段需乘以100
    - 如果毛利率 >= 1，说明已经是百分比形式（如 89.76 表示 89.76%），直接保留

    当毛利率为 None 时，回退到逐字段判断（_normalize_pct）

    Args:
        roe_val: ROE原始值
        gross_margin_val: 毛利率原始值（参照字段）
        net_margin_val: 净利率原始值

    Returns:
        (归一化ROE, 归一化毛利率, 归一化净利率)
    """
    if gross_margin_val is not None and abs(gross_margin_val) < 1:
        need_multiply = True
    elif gross_margin_val is not None and abs(gross_margin_val) >= 1:
        need_multiply = False
    else:
        need_multiply = None

    def _convert(v):
        if v is None:
            return None
        if need_multiply is True:
            return round(v * 100, 4)
        elif need_multiply is False:
            return round(v, 4)
        else:
            return _normalize_pct(v)

    return _convert(roe_val), _convert(gross_margin_val), _convert(net_margin_val)


def _clean_nan(v):
    """将 NaN/inf 值转为 None，避免 MySQL 写入失败"""
    if v is None:
        return None
    try:
        import math
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
    except (TypeError, ValueError):
        return None
    return v


def _get_financial_data_qmt(stock_code: str, max_rows: int = 12) -> Optional[list[dict[str, Any]]]:
    """
    通过 QMT Gateway 远程获取股票的综合财务数据

    QMT Gateway 部署在 Windows 服务器上，通过 xtquant 从 PershareIndex、
    Income、Balance、CashFlow 四张报表中提取财务指标，包含：
    - 盈利能力：ROE、毛利率、净利率、营收、净利润
    - 偿债能力：资产负债率、流动比率
    - 每股指标：EPS
    - 现金流：经营活动现金流
    - 规模：总资产、净资产

    Args:
        stock_code: 股票代码，如 "600519.SH"
        max_rows: 最大返回行数

    Returns:
        list[dict] | None: 财务指标列表，失败返回 None
    """
    _log(f"步骤3-QMT: 通过 QMT Gateway 获取 {stock_code} 财务数据...")
    try:
        from infra.qmt_gateway_client import get_financial_data as _qmt_finance

        resp = _qmt_finance(stock_code=stock_code, max_rows=max_rows)
        rows = resp.get("rows") or []
        if not rows:
            _log(f"QMT Gateway 返回 {stock_code} 财务数据为空")
            return None

        results = []
        for r in rows:
            report_date_raw = r.get("报告期") or r.get("end_date") or ""
            report_date = str(report_date_raw)[:10] if report_date_raw else ""
            if not report_date:
                continue

            revenue = safe_float(r.get("营业收入"))
            net_profit = safe_float(r.get("净利润"))
            total_assets = safe_float(r.get("总资产"))
            total_equity = safe_float(r.get("净资产"))
            total_shares = safe_float(r.get("总股本"))

            debt_ratio = None
            if total_assets and total_assets != 0 and total_equity is not None:
                debt_ratio = round((1 - total_equity / total_assets) * 100, 4)

            bps = safe_float(r.get("每股净资产"))
            if bps is None and total_equity is not None and total_shares is not None and total_shares != 0:
                bps = round(total_equity / total_shares, 4)

            raw_roe = safe_float(r.get("ROE"))
            raw_gm = safe_float(r.get("毛利率"))
            raw_nm = safe_float(r.get("净利率"))
            normalized_roe, normalized_gm, normalized_nm = _normalize_pct_batch(raw_roe, raw_gm, raw_nm)

            results.append({
                "report_date": report_date,
                "revenue": revenue,
                "net_profit": net_profit,
                "eps": safe_float(r.get("基本每股收益")),
                "bps": bps,
                "roe": normalized_roe,
                "roa": None,
                "gross_margin": normalized_gm,
                "net_margin": normalized_nm,
                "debt_ratio": debt_ratio,
                "current_ratio": None,
                "operating_cashflow": safe_float(r.get("每股经营现金流")),
                "total_assets": total_assets,
                "total_equity": total_equity,
                "total_shares": total_shares,
            })

        _log(f"QMT Gateway 成功获取 {stock_code} 财务数据，共 {len(results)} 条")
        return results[:max_rows]
    except Exception as e:
        _log(f"QMT Gateway 获取 {stock_code} 财务数据失败: {type(e).__name__}: {e}")
        return None


def _get_financial_data_akshare(stock_code: str, max_rows: int = 12) -> list[dict[str, Any]]:
    """
    使用akshare获取财务指标数据（带超时保护）

    Args:
        stock_code: 股票代码
        max_rows: 最大返回行数

    Returns:
        list[dict]: 财务指标列表
    """
    def _fetch():
        import akshare as ak
        code_num = stock_code.split(".")[0]
        return ak.stock_financial_analysis_indicator_em(symbol=code_num, indicator="按报告期")

    df = _run_with_timeout(_fetch, timeout=30)
    if df is None or (hasattr(df, 'empty') and df.empty) or (isinstance(df, (list, tuple)) and len(df) == 0):
        return []
    if not hasattr(df, 'empty'):
        return []

    try:
        df = df.head(max_rows)
        results = []
        for _, r in df.iterrows():
            rd = r.get("REPORT_DATE") if "REPORT_DATE" in df.columns else (r.get("报告期") if "报告期" in df.columns else None)
            report_date = to_ymd(rd)
            if not report_date:
                continue

            payload = r.to_dict()
            for k, v in list(payload.items()):
                if isinstance(v, (pd.Timestamp,)):
                    payload[k] = v.isoformat()

            raw_ak_roe = safe_float(payload.get("净资产收益率") or payload.get("WEIGHT_AVG_ROE"))
            raw_ak_gm = safe_float(payload.get("销售毛利率") or payload.get("GROSS_PROFIT_RATIO"))
            raw_ak_nm = safe_float(payload.get("销售净利率") or payload.get("NET_PROFIT_RATIO"))
            ak_roe, ak_gm, ak_nm = _normalize_pct_batch(raw_ak_roe, raw_ak_gm, raw_ak_nm)

            results.append({
                "report_date": report_date,
                "revenue": safe_float(payload.get("营业总收入") or payload.get("REVENUE")),
                "net_profit": safe_float(payload.get("净利润") or payload.get("NET_PROFIT")),
                "eps": safe_float(payload.get("每股收益") or payload.get("BASIC_EPS")),
                "bps": safe_float(payload.get("每股净资产") or payload.get("BPS")),
                "roe": ak_roe,
                "roa": safe_float(payload.get("总资产净利率") or payload.get("ROA")),
                "gross_margin": ak_gm,
                "net_margin": ak_nm,
                "debt_ratio": safe_float(payload.get("资产负债率") or payload.get("DEBT_ASSET_RATIO")),
                "current_ratio": safe_float(payload.get("流动比率") or payload.get("CURRENT_RATIO")),
                "operating_cashflow": safe_float(payload.get("经营活动产生的现金流量净额") or payload.get("OPERATE_CASH_FLOW")),
                "total_assets": safe_float(payload.get("总资产") or payload.get("TOTAL_ASSETS")),
                "total_equity": safe_float(payload.get("所有者权益合计") or payload.get("TOTAL_EQUITY")),
                "total_shares": safe_float(payload.get("总股本") or payload.get("TOTAL_SHARES")),
            })
        return results
    except Exception as e:
        _log(f"akshare 解析 {stock_code} 财务数据失败: {e}")
        return []


def _get_financial_data_tushare(stock_code: str, max_rows: int = 12) -> list[dict[str, Any]]:
    """
    使用 TuShare 获取财务指标数据（作为 akshare 的备选数据源）

    当 akshare 获取财务数据失败时，使用 TuShare 的 fina_indicator 接口获取。

    Args:
        stock_code: 股票代码，如 "600519.SH"
        max_rows: 最大返回行数

    Returns:
        list[dict]: 财务指标列表，字段格式与 _get_financial_data_akshare 一致
    """
    try:
        from infra.tushare_client import get_pro_api

        pro = get_pro_api()
        time.sleep(0.3)
        df = pro.fina_indicator(ts_code=stock_code, limit=max_rows)
        if df is None or len(df) == 0:
            _log(f"TuShare fina_indicator 返回 {stock_code} 数据为空")
            return []

        def _pct(v):
            if v is None:
                return None
            try:
                x = float(v)
                if x != x:
                    return None
                return round(x, 4)
            except (ValueError, TypeError):
                return None

        results = []
        for _, r in df.iterrows():
            report_date = to_ymd(r.get("end_date"))
            if not report_date:
                continue

            results.append({
                "report_date": report_date,
                "revenue": None,
                "net_profit": None,
                "eps": safe_float(r.get("eps")),
                "roe": _pct(r.get("roe")),
                "roa": _pct(r.get("roa")),
                "gross_margin": _pct(r.get("grossprofit_margin")),
                "net_margin": _pct(r.get("netprofit_margin")),
                "debt_ratio": _pct(r.get("debt_to_assets")),
                "current_ratio": safe_float(r.get("current_ratio")),
                "operating_cashflow": None,
                "total_assets": None,
                "total_equity": None,
            })
        _log(f"TuShare 成功获取 {stock_code} 财务数据，共 {len(results)} 条")
        return results[:max_rows]
    except Exception as e:
        _log(f"TuShare 获取 {stock_code} 财务数据失败: {type(e).__name__}: {e}")
        return []


def _get_existing_report_dates(conn, stock_code: str) -> set[str]:
    """
    获取股票已有的报告期日期集合（用于去重）
    
    Args:
        conn: 数据库连接
        stock_code: 股票代码
        
    Returns:
        set[str]: 已有的报告期日期集合
    """
    try:
        rows = query_dict(conn, 
            "SELECT report_date FROM trade_stock_financial WHERE stock_code = %s",
            (stock_code,))
        return {str(r["report_date"]) for r in rows}
    except Exception as e:
        _log(f"从数据库获取 {stock_code} 已有报告期失败: {e}")
        return set()


def _get_existing_financial_data_from_db(conn, stock_code: str, max_rows: int = 12) -> list[dict[str, Any]]:
    """
    从数据库获取已有财务数据
    
    Args:
        conn: 数据库连接
        stock_code: 股票代码
        max_rows: 最大返回行数
        
    Returns:
        list[dict]: 财务指标列表
    """
    try:
        rows = query_dict(conn, """
            SELECT report_date, revenue, net_profit, eps, roe, roa, gross_margin, 
                   net_margin, debt_ratio, current_ratio, operating_cashflow, 
                   total_assets, total_equity
            FROM trade_stock_financial 
            WHERE stock_code = %s 
            ORDER BY report_date DESC
            LIMIT %s
        """, (stock_code, max_rows))
        
        results = []
        for r in rows:
            results.append({
                "report_date": r["report_date"].isoformat() if r["report_date"] else None,
                "revenue": r["revenue"],
                "net_profit": r["net_profit"],
                "eps": r["eps"],
                "roe": r["roe"],
                "roa": r["roa"],
                "gross_margin": r["gross_margin"],
                "net_margin": r["net_margin"],
                "debt_ratio": r["debt_ratio"],
                "current_ratio": r["current_ratio"],
                "operating_cashflow": r["operating_cashflow"],
                "total_assets": r["total_assets"],
                "total_equity": r["total_equity"],
            })
        return results
    except Exception as e:
        _log(f"从数据库获取 {stock_code} 已有财务数据失败: {e}")
        return []


def run_stock_financial_collection(
    cfg: MySQLConfig,
    mode: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
    progress_callback=None,
) -> JobStats:
    """
    运行财务数据采集任务

    数据源优先级：TuShare > QMT Gateway > AkShare > 数据库回退。
    支持多线程并发采集、断点续传和日期级别去重。

    Args:
        cfg: 数据库配置
        mode: 运行模式，"test"为测试模式
        params: 参数字典
            - test_stock: 测试股票代码，默认002163.SZ
            - max_stocks: 最大股票数量，默认0（全部）
            - max_rows_per_stock: 每只股票最大行数，默认12
            - max_workers: 并发线程数，默认4
            - resume: 是否启用断点续传，默认True（跳过已有数据的股票）
        progress_callback: 进度回调函数，接收已处理股票数量

    Returns:
        JobStats: 任务执行统计
    """
    test_mode = (mode or "").lower() == "test"
    
    # 预加载全市场 daily_basic 缓存（非测试模式）
    if not test_mode:
        _load_daily_basic_cache()
    test_stock = str((params or {}).get("test_stock") or "002163.SZ")
    max_stocks_val = (params or {}).get("max_stocks")
    max_stocks = int(max_stocks_val) if max_stocks_val is not None else (0 if not test_mode else 1)
    max_rows_per_stock = int((params or {}).get("max_rows_per_stock") or 12)
    max_workers = max(1, int((params or {}).get("max_workers") or 4))
    resume = bool((params or {}).get("resume", True))

    # 获取股票列表：先测试模式返回指定股票，非测试模式从数据库读取
    codes = _get_stock_list_qmt_or_akshare(test_mode, test_stock, max_stocks)
    if not codes:
        _log("无法从外部源获取股票列表，从数据库读取...")
        codes = _get_stock_list_from_db(cfg, max_stocks)

    if not codes:
        _log("没有股票需要处理")
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="unknown",
            fallback_chain=[],
            message="没有股票列表",
        )

    # 断点续传：跳过已有完整财务数据的股票（roe为判断依据，而非pb）
    # 因为pb来自行情数据（QMT Gateway），行情源可能不可达但财务数据已就绪
    if resume and not test_mode:
        _log("断点续传模式: 查询已有完整财务数据的股票...")
        try:
            conn_check = connect(cfg)
            try:
                existing_rows = query_dict(conn_check,
                    "SELECT stock_code FROM trade_stock_financial "
                    "WHERE roe IS NOT NULL "
                    "GROUP BY stock_code HAVING COUNT(*) >= %s",
                    (max_rows_per_stock,))
                existing_codes = {r["stock_code"] for r in existing_rows}
                if existing_codes:
                    before = len(codes)
                    codes = [c for c in codes if c not in existing_codes]
                    skipped = before - len(codes)
                    _log(f"断点续传: 跳过 {skipped} 只已有完整财务数据的股票, 待处理 {len(codes)} 只")
            finally:
                conn_check.close()
        except Exception as e:
            _log(f"断点续传查询失败: {type(e).__name__}: {e}, 将全量处理")

    if not codes:
        _log("所有股票已有完整PB数据，无需处理")
        return JobStats(
            items_processed=0, rows_written=0, failed_items=[],
            data_source_final="qmt", fallback_chain=["qmt"],
            message="所有股票已有完整PB数据，跳过",
        )

    # 优先处理上海股票（防止任务中断导致上海股票缺失）
    # 上海股票（601/603/605/688等）目前几乎没有财务数据
    sh_count = sum(1 for c in codes if c.upper().endswith(".SH"))
    sz_count = len(codes) - sh_count
    if sh_count > 0:
        codes.sort(key=lambda c: (0, c) if c.upper().endswith(".SH") else (1, c))
        _log(f"优先处理上海股票: SH={sh_count} 只优先, SZ={sz_count} 只随后")

    processed = 0
    rows_written = 0
    failed: list[str] = []
    used_sources: set[str] = set()
    total_count = len(codes)
    intermediate_batch_size = 200
    last_log_pct = 0
    task_start_time = datetime.now()

    conn = connect(cfg)
    progress_lock = Lock()
    batch: list[tuple[Any, ...]] = []

    _log(f"开始全量采集: 共 {total_count} 只股票, 每只最多 {max_rows_per_stock} 条, "
         f"{max_workers} 线程, 中间提交阈值={intermediate_batch_size}")
    _log(f"数据源: QMT Gateway (Windows服务器), 数据库回退: 启用")

    # 批量获取AkShare全市场行情数据，作为PE/PB/市值兜底
    akshare_market_map = _get_market_data_map(codes)
    if akshare_market_map:
        _log(f"AkShare行情兜底数据已就绪，覆盖 {len(akshare_market_map)} 只股票")
    else:
        _log("AkShare行情数据获取失败，PB/市值将仅依赖计算")

    def _process_one(code: str) -> tuple[str, list[tuple], str, bool]:
        """单线程处理一只股票，返回 (code, rows, source, is_failed)"""
        try:
            market_data = _get_market_data_qmt(code)
            if not market_data:
                market_data = {}

            qmt_price = market_data.get("price")

            # 获取财务数据：TuShare → QMT → AkShare → 数据库回退（按优先级）
            financial_data = _get_financial_data_tushare(code, max_rows_per_stock)
            fin_source = "tushare"

            if not financial_data:
                _log(f"  [{code}] TuShare 无财务数据，尝试 QMT 备选...")
                financial_data = _get_financial_data_qmt(code, max_rows_per_stock)
                if financial_data:
                    fin_source = "qmt"

            if not financial_data:
                _log(f"  [{code}] QMT 也无财务数据，尝试 AkShare 备选...")
                financial_data = _get_financial_data_akshare(code, max_rows_per_stock)
                if financial_data:
                    fin_source = "akshare"

            if not financial_data:
                _log(f"  [{code}] AkShare 也无财务数据，尝试数据库回退...")
                financial_data = _get_existing_financial_data_from_db(conn, code, max_rows_per_stock)
                if financial_data:
                    fin_source = "db"

            if not financial_data:
                return code, [], "unknown", True

            # 日期级别去重：过滤已存在的报告期数据
            existing_dates = _get_existing_report_dates(conn, code)
            if existing_dates:
                before_count = len(financial_data)
                financial_data = [f for f in financial_data if f["report_date"] not in existing_dates]
                skipped_count = before_count - len(financial_data)
                if skipped_count > 0:
                    _log(f"  [{code}] 跳过 {skipped_count} 条已存在的报告期数据")

            if not financial_data:
                _log(f"  [{code}] 所有报告期数据均已存在，跳过")
                return code, [], fin_source, False

            # 计算同比增长率
            if fin_source in ("qmt", "tushare", "akshare"):
                financial_data = _compute_yoy_growth(financial_data)

            # 用 QMT 最新价格和财务数据计算 PE/PB/市值
            # PE = 收盘价 / 最近4季度EPS之和 (TTM)
            # PB = 收盘价 / 每股净资产 (bps)
            # 市值 = 收盘价 × 总股本
            sorted_fin = sorted(financial_data, key=lambda x: x.get("report_date", ""))
            eps_values = [f.get("eps") for f in sorted_fin if f.get("eps") is not None]
            eps_ttm = sum(eps_values[-4:]) if eps_values else None

            latest_fin = sorted_fin[-1] if sorted_fin else {}
            bps_val = latest_fin.get("bps")
            total_shares_val = latest_fin.get("total_shares")

            computed_pe = None
            computed_pb = None
            computed_market_cap = None
            computed_float_market_cap = None

            if qmt_price and qmt_price > 0:
                if eps_ttm and eps_ttm != 0:
                    computed_pe = round(qmt_price / eps_ttm, 4)
                if bps_val and bps_val != 0:
                    computed_pb = round(qmt_price / bps_val, 4)
                if total_shares_val:
                    computed_market_cap = round(qmt_price * total_shares_val, 2)

            # 外部行情数据兜底（akshare enrich 会用）
            pe = computed_pe or market_data.get("pe")
            pb = computed_pb or market_data.get("pb")
            market_cap = computed_market_cap or market_data.get("market_cap")
            float_market_cap = computed_float_market_cap or market_data.get("float_market_cap")

            # AkShare行情数据兜底：QMT行情PE/PB为空时，使用AkShare全市场行情
            ak_data = akshare_market_map.get(code) if akshare_market_map else None
            if ak_data:
                if pe is None:
                    pe = ak_data.get("pe")
                if pb is None:
                    pb = ak_data.get("pb")
                if market_cap is None:
                    market_cap = ak_data.get("market_cap")
                if float_market_cap is None:
                    float_market_cap = ak_data.get("float_market_cap")

            rows: list[tuple] = []
            for fin in financial_data:
                rows.append((
                    code, fin["report_date"],
                    _clean_nan(fin["revenue"]), _clean_nan(fin["net_profit"]), _clean_nan(fin["eps"]),
                    _clean_nan(fin["roe"]), _clean_nan(fin["roa"]), _clean_nan(fin["gross_margin"]), _clean_nan(fin["net_margin"]),
                    _clean_nan(fin["debt_ratio"]), _clean_nan(fin["current_ratio"]),
                    _clean_nan(fin["operating_cashflow"]), _clean_nan(fin["total_assets"]), _clean_nan(fin["total_equity"]),
                    _clean_nan(pe), _clean_nan(pb), _clean_nan(market_cap), _clean_nan(float_market_cap),
                    _clean_nan(fin.get("profit_growth_yoy")),
                    _clean_nan(fin.get("revenue_growth_yoy")),
                    fin_source
                ))
            with progress_lock:
                used_sources.add(fin_source)
            return code, rows, fin_source, False
        except Exception as e:
            _log(f"  [{code}] 线程异常: {type(e).__name__}: {e}")
            return code, [], "unknown", True

    try:
        processed_ref = [0]
        batch_lock = Lock()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {}
            for code in codes:
                future = executor.submit(_process_one, code)
                future_to_code[future] = code

            stock_done_count = 0
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                stock_done_count += 1

                try:
                    result_code, result_rows, result_source, is_failed = future.result(timeout=300)
                except FutureTimeoutError:
                    _log(f"  [{stock_done_count}/{total_count}] {code} 线程超时(300s)，跳过")
                    with progress_lock:
                        failed.append(code)
                    continue
                except Exception as e:
                    _log(f"  [{stock_done_count}/{total_count}] {code} 线程异常: {type(e).__name__}: {e}")
                    with progress_lock:
                        failed.append(code)
                    continue

                with progress_lock:
                    processed_ref[0] += 1
                    processed_now = processed_ref[0]

                if is_failed:
                    _log(f"  [{processed_now}/{total_count}] {code} 完成: 0 条 (无数据)")
                    with progress_lock:
                        failed.append(code)
                    continue

                # 将结果追加到批次
                with batch_lock:
                    batch.extend(result_rows)

                elapsed = (datetime.now() - task_start_time).total_seconds()
                _log(f"  [{processed_now}/{total_count}] {code} 完成: {len(result_rows)} 条, 来源={result_source}, "
                     f"批处理中={len(batch)} 条 (累计耗时 {elapsed:.0f}s)")

                # 每处理完一只股票更新进度回调
                if progress_callback:
                    try:
                        progress_callback(processed_now)
                    except Exception:
                        pass

                # 每200只提交一次中间批次
                if processed_now % intermediate_batch_size == 0 and batch:
                    with batch_lock:
                        curr_batch = list(batch)
                        batch.clear()
                    batch_elapsed = (datetime.now() - task_start_time).total_seconds()
                    _log(f"[中间提交] 已处理 {processed_now}/{total_count}, "
                         f"当前批次 {len(curr_batch)} 条, 累计耗时 {batch_elapsed:.0f}s")
                    try:
                        conn.ping(reconnect=True)
                    except Exception:
                        conn.close()
                        conn = connect(cfg)
                    try:
                        written = executemany(conn, _INSERT_SQL, curr_batch)
                        _log(f"[中间提交] 写入 {written} 行成功 (累计 {rows_written + written})")
                        rows_written += written
                    except Exception as e:
                        _log(f"[中间提交] 写入失败: {type(e).__name__}: {e}, 数据将重试")
                        with batch_lock:
                            batch.extend(curr_batch)

                # 每10%输出进度
                current_pct = int(processed_now / total_count * 100) if total_count > 0 else 0
                if current_pct >= last_log_pct + 10:
                    last_log_pct = current_pct
                    elapsed_total = (datetime.now() - task_start_time).total_seconds()
                    speed = processed_now / elapsed_total * 60 if elapsed_total > 0 else 0
                    eta_remain = (total_count - processed_now) / speed * 60 if speed > 0 else 0
                    _log(f"[进度] {current_pct}% ({processed_now}/{total_count}), "
                         f"已耗时 {elapsed_total:.0f}s, 速度 {speed:.1f}只/分钟, "
                         f"预计剩余 {eta_remain:.0f}s, 失败 {len(failed)} 只")
                    if failed:
                        _log(f"[进度] 失败股票最近5只: {failed[-5:]}")

        processed = processed_ref[0]

        # 提交剩余批次
        if batch:
            with batch_lock:
                final_batch = list(batch)
                batch.clear()
            _log(f"[最终提交] 写入剩余 {len(final_batch)} 条记录 (累计耗时 {(datetime.now()-task_start_time).total_seconds():.0f}s)...")
            try:
                conn.ping(reconnect=True)
            except Exception:
                conn.close()
                conn = connect(cfg)
            try:
                written = executemany(conn, _INSERT_SQL, final_batch)
                _log(f"[最终提交] 写入 {written} 行成功")
                rows_written += written
            except Exception as e:
                _log(f"[最终提交] 写入失败: {type(e).__name__}: {e}")
                rows_written = 0

        total_elapsed = (datetime.now() - task_start_time).total_seconds()
        speed_avg = processed / total_elapsed * 60 if total_elapsed > 0 else 0
        
        _log(f"[完成] ========== 财务季度数据采集任务完成 ==========")
        _log(f"[完成] 总耗时: {total_elapsed:.0f}秒 ({total_elapsed/60:.1f}分钟)")
        _log(f"[完成] 处理股票: {processed} 只")
        _log(f"[完成] 写入记录: {rows_written} 行")
        _log(f"[完成] 失败股票: {len(failed)} 只")
        _log(f"[完成] 平均速度: {speed_avg:.1f} 只/分钟")
        _log(f"[完成] 使用数据源: {', '.join(sorted(used_sources))}")
        if failed:
            _log(f"[完成] 失败列表前10: {failed[:10]}")
            _log(f"[完成] 失败原因可能: 数据源不可用、网络超时、API限流等")

        # 构建数据源链和最终数据源（按优先级顺序）
        source_order = ["tushare", "qmt", "akshare", "db"]
        fallback_chain = [s for s in source_order if s in used_sources]
        if not fallback_chain:
            fallback_chain = ["unknown"]
        data_source_final = "+".join(fallback_chain) if fallback_chain else "unknown"

        return JobStats(
            items_processed=processed,
            rows_written=rows_written,
            failed_items=failed,
            data_source_final=data_source_final,
            fallback_chain=fallback_chain,
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()


if __name__ == "__main__":
    from core.db import load_mysql_config

    cfg = load_mysql_config()
    stats = run_stock_financial_collection(cfg, mode="test", params={"test_stock": "600519.SH"})

    _log(f"\n任务统计: 处理股票数={stats.items_processed}, 写入行数={stats.rows_written}, "
         f"失败股票={len(stats.failed_items)}, 数据源={stats.data_source_final}, 消息={stats.message}")
