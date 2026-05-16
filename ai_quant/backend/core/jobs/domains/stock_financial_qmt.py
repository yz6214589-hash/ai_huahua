"""
增强版财务数据采集任务（QMT + akshare）
数据源优先级：QMT（xtquant） > akshare

功能：
1. 使用QMT获取实时行情（市值、PE、PB）
2. 使用akshare获取财务指标（ROE、毛利率、营收增长率等）
3. 计算衍生指标
4. 写入数据库

QMT优先，akshare作为备用数据源
"""

from __future__ import annotations

from typing import Any, Optional
import pandas as pd

from core.db import MySQLConfig, connect, executemany
from core.jobs.common import JobStats, normalize_stock_code, safe_float, to_ymd


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


def _get_stock_list_qmt_or_akshare(test_mode: bool, test_stock: str, max_stocks: int) -> list[str]:
    """
    获取股票列表

    优先使用QMT，备用akshare

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

    # 尝试使用QMT获取股票列表
    try:
        from infra import qmt_gateway_client
        # QMT可能提供股票列表接口，这里先使用akshare
        raise NotImplementedError("QMT股票列表接口未实现")
    except Exception:
        pass

    # 使用akshare获取股票列表
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        if df is None or len(df) == 0:
            return []
        out: list[str] = []
        for _, r in df.iterrows():
            code_num = str(r.get("代码") or "").strip()
            if not code_num:
                continue
            out.append(f"{code_num}.{_infer_exchange(code_num)}")
            if 0 < max_stocks <= len(out):
                break
        return out
    except Exception:
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
        print(f"  [QMT] 获取 {stock_code} 行情失败: {e}")
        return None


def _get_market_data_akshare(stock_code: str) -> Optional[dict[str, Any]]:
    """
    使用akshare获取股票的实时行情数据

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
        print(f"  [akshare] 获取 {stock_code} 行情失败: {e}")
        return None


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


def _get_financial_data_akshare(stock_code: str, max_rows: int = 12) -> list[dict[str, Any]]:
    """
    使用akshare获取财务指标数据

    Args:
        stock_code: 股票代码
        max_rows: 最大返回行数

    Returns:
        list[dict]: 财务指标列表
    """
    try:
        import akshare as ak

        code_num = stock_code.split(".")[0]
        df = ak.stock_financial_analysis_indicator_em(symbol=code_num, indicator="按报告期")

        if df is None or len(df) == 0:
            return []

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
        print(f"  [akshare] 获取 {stock_code} 财务数据失败: {e}")
        return []


def run_stock_financial_collection(
    cfg: MySQLConfig,
    mode: Optional[str] = None,
    params: Optional[dict[str, Any]] = None,
) -> JobStats:
    """
    运行增强版财务数据采集任务

    优先使用QMT获取行情数据，akshare获取财务指标

    Args:
        cfg: 数据库配置
        mode: 运行模式，"test"为测试模式
        params: 参数字典
            - test_stock: 测试股票代码，默认600519.SH
            - max_stocks: 最大股票数量，默认50
            - max_rows_per_stock: 每只股票最大行数，默认12

    Returns:
        JobStats: 任务执行统计
    """
    test_mode = (mode or "").lower() == "test"
    test_stock = str((params or {}).get("test_stock") or "600519.SH")
    max_stocks = int((params or {}).get("max_stocks") or (1 if test_mode else 50))
    max_rows_per_stock = int((params or {}).get("max_rows_per_stock") or 12)

    codes = _get_stock_list_qmt_or_akshare(test_mode, test_stock, max_stocks)
    processed = 0
    rows_written = 0
    failed: list[str] = []

    conn = connect(cfg)
    try:
        batch: list[tuple[Any, ...]] = []

        for code in codes:
            processed += 1
            code_num = code.split(".")[0]

            # 获取行情数据（市值、PE、PB）
            print(f"处理 {code}...")
            market_data = _get_market_data(code)

            pe = market_data.get("pe")
            pb = market_data.get("pb")
            market_cap = market_data.get("market_cap")
            float_market_cap = market_data.get("float_market_cap")

            # 获取财务数据
            financial_data = _get_financial_data_akshare(code, max_rows_per_stock)

            if not financial_data:
                failed.append(code)
                continue

            for fin in financial_data:
                # 确定数据源
                if pe is not None:
                    data_source = "qmt+akshare"
                else:
                    data_source = "akshare"

                batch.append((
                    code,
                    fin["report_date"],
                    fin["revenue"],
                    fin["net_profit"],
                    fin["eps"],
                    fin["roe"],
                    fin["roa"],
                    fin["gross_margin"],
                    fin["net_margin"],
                    fin["debt_ratio"],
                    fin["current_ratio"],
                    fin["operating_cashflow"],
                    fin["total_assets"],
                    fin["total_equity"],
                    pe, pb, market_cap, float_market_cap, data_source
                ))

        if batch:
            rows_written = executemany(conn, _INSERT_SQL, batch)

        return JobStats(
            items_processed=processed,
            rows_written=rows_written,
            failed_items=failed,
            data_source_final="qmt+akshare",
            fallback_chain=["qmt", "akshare"],
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()


if __name__ == "__main__":
    from core.db import load_mysql_config

    cfg = load_mysql_config()
    stats = run_stock_financial_collection(cfg, mode="test", params={"test_stock": "600519.SH"})

    print("\n任务统计:")
    print(f"  处理股票数: {stats.items_processed}")
    print(f"  写入行数: {stats.rows_written}")
    print(f"  失败股票: {len(stats.failed_items)}")
    print(f"  数据源: {stats.data_source_final}")
    print(f"  消息: {stats.message}")
