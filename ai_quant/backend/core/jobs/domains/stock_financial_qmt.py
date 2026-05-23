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


def _log(msg: str):
    """打印带时间戳的日志（同时输出到控制台和日志系统）

    Args:
        msg: 日志消息内容
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [stock_financial] {msg}")
    logger.info(msg)


_INSERT_SQL = """
INSERT INTO trade_stock_financial
(stock_code, report_date, revenue, net_profit, eps, roe, roa, gross_margin, net_margin,
 debt_ratio, current_ratio, operating_cashflow, total_assets, total_equity,
 pe_ttm, pb, market_cap, float_market_cap, data_source, created_at)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW())
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
data_source=VALUES(data_source)
"""


def _infer_exchange(code_num: str) -> str:
    """根据股票代码推断交易所"""
    if code_num.startswith("6"):
        return "SH"
    return "SZ"


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
            return [r["stock_code"] for r in rows]
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
        _log(f"获取到 {len(all_codes)} 只股票，取前 {len(norm_codes)} 只")
        return norm_codes
    except Exception as e:
        _log(f"QMT Gateway 获取股票列表失败: {type(e).__name__}: {e}")
        return []


def _get_market_data_qmt(stock_code: str) -> Optional[dict[str, Any]]:
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
    _log("正在通过 akshare 批量获取全市场行情数据（超时30秒）...")
    code_num_map = _run_with_timeout(_get_market_data_from_akshare, timeout=30)
    if not code_num_map:
        _log("akshare 批量获取市场数据失败或超时，尝试 TuShare 备选...")
        tushare_map = _get_market_data_from_tushare(stock_codes)
        if tushare_map:
            _log(f"TuShare 备选成功，获取到 {len(tushare_map)} 只股票的市场数据")
            return tushare_map
        _log("TuShare 备选也失败，返回空数据")
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
            results.append({
                "report_date": str(r.get("end_date") or "")[:10],
                "revenue": r.get("revenue"),
                "net_profit": r.get("net_profit"),
                "eps": r.get("eps"),
                "roe": r.get("roe"),
                "roa": r.get("roa"),
                "gross_margin": r.get("gross_margin"),
                "net_margin": r.get("net_margin"),
                "debt_ratio": r.get("debt_ratio"),
                "current_ratio": r.get("current_ratio"),
                "operating_cashflow": r.get("operating_cashflow"),
                "total_assets": r.get("total_assets"),
                "total_equity": r.get("total_equity"),
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

            results.append({
                "report_date": report_date,
                "revenue": safe_float(payload.get("营业总收入") or payload.get("REVENUE")),
                "net_profit": safe_float(payload.get("净利润") or payload.get("NET_PROFIT")),
                "eps": safe_float(payload.get("每股收益") or payload.get("BASIC_EPS")),
                "roe": safe_float(payload.get("净资产收益率") or payload.get("WEIGHT_AVG_ROE")),
                "roa": safe_float(payload.get("总资产净利率") or payload.get("ROA")),
                "gross_margin": safe_float(payload.get("销售毛利率") or payload.get("GROSS_PROFIT_RATIO")),
                "net_margin": safe_float(payload.get("销售净利率") or payload.get("NET_PROFIT_RATIO")),
                "debt_ratio": safe_float(payload.get("资产负债率") or payload.get("DEBT_ASSET_RATIO")),
                "current_ratio": safe_float(payload.get("流动比率") or payload.get("CURRENT_RATIO")),
                "operating_cashflow": safe_float(payload.get("经营活动产生的现金流量净额") or payload.get("OPERATE_CASH_FLOW")),
                "total_assets": safe_float(payload.get("总资产") or payload.get("TOTAL_ASSETS")),
                "total_equity": safe_float(payload.get("所有者权益合计") or payload.get("TOTAL_EQUITY")),
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
                return x / 100.0
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

    数据源优先级：QMT Gateway > TuShare > AkShare > 数据库回退。
    支持多线程并发采集和断点续传。

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

    # 断点续传：跳过已有数据的股票
    if resume and not test_mode:
        _log("断点续传模式: 查询已有数据的股票...")
        try:
            conn_check = connect(cfg)
            try:
                existing_rows = query_dict(conn_check,
                    "SELECT stock_code FROM trade_stock_financial "
                    "GROUP BY stock_code HAVING COUNT(*) >= %s",
                    (max_rows_per_stock,))
                existing_codes = {r["stock_code"] for r in existing_rows}
                if existing_codes:
                    before = len(codes)
                    codes = [c for c in codes if c not in existing_codes]
                    skipped = before - len(codes)
                    _log(f"断点续传: 跳过 {skipped} 只已有数据的股票, 待处理 {len(codes)} 只")
            finally:
                conn_check.close()
        except Exception as e:
            _log(f"断点续传查询失败: {type(e).__name__}: {e}, 将全量处理")

    if not codes:
        _log("所有股票已有完整数据，无需处理")
        return JobStats(
            items_processed=0, rows_written=0, failed_items=[],
            data_source_final="qmt", fallback_chain=["qmt"],
            message="所有股票已有数据，跳过",
        )

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

    def _process_one(code: str) -> tuple[str, list[tuple], str, bool]:
        """单线程处理一只股票，返回 (code, rows, source, is_failed)"""
        try:
            market_data = _get_market_data_qmt(code)
            if not market_data:
                market_data = {}

            pe = market_data.get("pe")
            pb = market_data.get("pb")
            market_cap = market_data.get("market_cap")
            float_market_cap = market_data.get("float_market_cap")

            # 获取财务数据：QMT → TuShare → AkShare → 数据库回退
            financial_data = _get_financial_data_qmt(code, max_rows_per_stock)
            fin_source = "qmt"

            if not financial_data:
                _log(f"  [{code}] QMT 无财务数据，尝试 TuShare 备选...")
                financial_data = _get_financial_data_tushare(code, max_rows_per_stock)
                if financial_data:
                    fin_source = "tushare"

            if not financial_data:
                _log(f"  [{code}] TuShare 也无财务数据，尝试 AkShare 备选...")
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

            rows: list[tuple] = []
            for fin in financial_data:
                rows.append((
                    code, fin["report_date"],
                    fin["revenue"], fin["net_profit"], fin["eps"],
                    fin["roe"], fin["roa"], fin["gross_margin"], fin["net_margin"],
                    fin["debt_ratio"], fin["current_ratio"],
                    fin["operating_cashflow"], fin["total_assets"], fin["total_equity"],
                    pe, pb, market_cap, float_market_cap, fin_source
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
        _log(f"[完成] 总耗时 {total_elapsed:.0f}s, 处理 {processed} 只, "
             f"写入 {rows_written} 行, 失败 {len(failed)} 只")
        if failed:
            _log(f"[完成] 失败列表前10: {failed[:10]}")

        # 构建数据源链和最终数据源
        source_order = ["qmt", "tushare", "akshare", "db"]
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
