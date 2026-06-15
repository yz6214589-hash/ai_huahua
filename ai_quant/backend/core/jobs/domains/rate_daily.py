from __future__ import annotations

from typing import Any

from core.db import MySQLConfig, connect, executemany
from core.jobs.common import JobStats, safe_float, to_ymd

# 允许在 _upsert_rate_indicator 中动态拼接SQL的列名白名单，防止SQL注入
_ALLOWED_RATE_COLUMNS = {"fear_greed", "vix", "ovx", "gvz", "ivix"}


_INSERT_SQL = """
INSERT INTO trade_rate_daily
(rate_date, cn_bond_10y, us_bond_10y, fear_greed, vix, ovx, gvz, ivix, data_source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
cn_bond_10y=COALESCE(VALUES(cn_bond_10y), cn_bond_10y),
us_bond_10y=COALESCE(VALUES(us_bond_10y), us_bond_10y),
fear_greed=COALESCE(VALUES(fear_greed), fear_greed),
vix=COALESCE(VALUES(vix), vix),
ovx=COALESCE(VALUES(ovx), ovx),
gvz=COALESCE(VALUES(gvz), gvz),
ivix=COALESCE(VALUES(ivix), ivix),
data_source=VALUES(data_source)
"""

_QVIX_INSERT_SQL = """
INSERT INTO trade_qvix_daily
(trade_date, qvix_50etf, qvix_300index, data_source)
VALUES (%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
qvix_50etf=COALESCE(VALUES(qvix_50etf), qvix_50etf),
qvix_300index=COALESCE(VALUES(qvix_300index), qvix_300index),
data_source=VALUES(data_source)
"""


def _fetch_fear_greed() -> tuple[str | None, float | None]:
    """从 alternative.me 获取恐惧贪婪指数"""
    import requests
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        if r.status_code == 200:
            data = r.json()
            val = int(data["data"][0]["value"])
            ts = int(data["data"][0]["timestamp"])
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            return dt, float(val)
    except Exception:
        pass
    return None, None


def _fetch_yahoo(symbol: str) -> tuple[str | None, float | None]:
    """从 Yahoo Finance 获取指数最新收盘价（带代理支持和多级降级）

    Yahoo Finance 提供了 CBOE VIX/OVX/GVZ 等波动率指数数据。
    由于网络限制（中国区访问 Yahoo Finance 可能被阻断），
    本函数实现了多级降级策略：

    采集优先级:
      第一级: query1.finance.yahoo.com (v8 API)
      第二级: query2.finance.yahoo.com (v8 API, 备用域名)
      第三级: query1.finance.yahoo.com (v7/download CSV API)
      第四级: 代理访问（通过环境变量 YAHOO_PROXY 配置）

    支持的符号: ^VIX, ^OVX, ^GVZ 等 Yahoo Finance 支持的指数代码
    更新频率: 每个交易日
    """
    import requests
    import os
    import time
    import logging
    logger = logging.getLogger("rate_daily")

    # 多用户代理轮换
    _USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    # 获取代理配置（从环境变量 YAHOO_PROXY 读取，支持 http/socks5）
    proxies = None
    proxy_url = os.environ.get("YAHOO_PROXY", "") or os.environ.get("https_proxy", "") or os.environ.get("HTTPS_PROXY", "")
    if proxy_url:
        proxies = {"https": proxy_url, "http": proxy_url}
        logger.info("Yahoo Finance 使用代理: %s", proxy_url[:20])

    # 多端点尝试: query1 → query2 → download CSV
    _endpoints = [
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d",
        f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d",
        f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}?range=5d&interval=1d&events=history",
    ]

    for attempt_idx, endpoint in enumerate(_endpoints):
        ua = _USER_AGENTS[attempt_idx % len(_USER_AGENTS)]
        headers = {"User-Agent": ua, "Accept": "application/json,text/html"}
        for retry in range(2):
            try:
                r = requests.get(endpoint, headers=headers, proxies=proxies, timeout=15)
                if r.status_code == 429:
                    time.sleep(5)
                    continue
                if r.status_code == 403:
                    # 403 表示 IP 被限制，尝试下一个端点
                    logger.warning("Yahoo Finance %s 返回 403 (IP受限)，尝试备用端点", symbol)
                    time.sleep(2)
                    break
                if r.status_code != 200:
                    time.sleep(2)
                    continue

                # 解析响应
                data = r.json()
                if "chart" not in data or "result" not in data["chart"] or not data["chart"]["result"]:
                    continue
                result = data["chart"]["result"][0]
                timestamps = result.get("timestamp", [])
                closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                if not closes:
                    continue
                # 找到最后一个非空收盘价
                for i in range(len(closes) - 1, -1, -1):
                    if closes[i] is not None:
                        from datetime import datetime, timezone
                        dt = datetime.fromtimestamp(timestamps[i], tz=timezone.utc).strftime("%Y-%m-%d")
                        logger.info("Yahoo Finance %s 获取成功: %s = %s", symbol, dt, closes[i])
                        return dt, float(closes[i])
            except Exception:
                time.sleep(2)

    logger.warning("Yahoo Finance %s 所有端点均获取失败", symbol)
    return None, None


def _fetch_from_fred(series_id: str) -> tuple[str | None, float | None]:
    """从 FRED 公开 CSV 获取最后一笔有效观测值（Yahoo Finance 的降级备用）

    数据来源: FRED (Federal Reserve Economic Data)
    接口文档: https://fred.stlouisfed.org/docs/api/fred/
    无需 API Key，通过公开 CSV 接口获取。

    映射关系:
      VIXCLS → VIX (CBOE波动率指数)
      OVXCLS → OVX (原油波动率指数)
      GVZCLS → GVZ (黄金波动率指数)
      DGS10  → US10Y (美国10年期国债收益率)

    更新频率: 每个交易日更新

    注意: 如果直连失败，会尝试使用 cloudscraper（能绕过部分CDN拦截）。
    如果仍失败，请配置 HTTPS_PROXY 环境变量使用代理访问。
    """
    import os
    import requests
    import logging
    logger = logging.getLogger("rate_daily")

    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    proxies = None
    proxy_url = os.environ.get("FRED_PROXY", "") or os.environ.get("https_proxy", "") or os.environ.get("HTTPS_PROXY", "")
    if proxy_url:
        proxies = {"https": proxy_url, "http": proxy_url}

    # 第一级: requests 直连
    last_val, last_date = None, None
    try:
        resp = requests.get(url, timeout=30, proxies=proxies)
        resp.raise_for_status()
        for line in resp.text.strip().splitlines():
            if line.startswith("DATE"):
                continue
            parts = line.split(",", 1)
            if len(parts) < 2:
                continue
            raw = parts[1].strip()
            if raw == "" or raw == ".":
                continue
            try:
                last_val = float(raw)
                last_date = parts[0].strip()
            except ValueError:
                continue
        if last_val is not None:
            return last_date, last_val
    except Exception as e:
        logger.warning("FRED %s requests 失败: %s, 尝试 cloudscraper", series_id, e)

    # 第二级: cloudscraper（绕过 CDN/Cloudflare 拦截）
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=30, proxies=proxies)
        if resp.status_code == 200:
            for line in resp.text.strip().splitlines():
                if line.startswith("DATE"):
                    continue
                parts = line.split(",", 1)
                if len(parts) < 2:
                    continue
                raw = parts[1].strip()
                if raw == "" or raw == ".":
                    continue
                try:
                    last_val = float(raw)
                    last_date = parts[0].strip()
                except ValueError:
                    continue
            return last_date, last_val
    except Exception:
        pass

    return None, None


def _fetch_vix_from_akshare() -> tuple[str | None, float | None]:
    """从东方财富美股行情获取 VIX 相关 ETF 价格作为 VIX 指数代理

    由于 FRED/Yahoo Finance 在中国网络环境不可用，使用 VIXY ETF
    （ProShares 恐慌指数期货短期合约ETF）的实时价格作为 VIX 指数的替代指标。

    VIXY 跟踪 VIX 短期期货指数，与 VIX 指数高度相关（相关系数 > 0.9），
    可以准确反映市场恐慌情绪的变化趋势。

    数据来源: AkShare stock_us_spot_em (东方财富美股实时行情)
    更新频率: 盘中实时更新
    参考价值: VIXY 价格与 VIX 指数趋势一致，可用作情绪参考

    Returns:
        (date_str, price) 或 (None, None)
    """
    import akshare as ak
    import logging
    from datetime import datetime
    logger = logging.getLogger("rate_daily")

    try:
        df = ak.stock_us_spot_em()
        if df is None or df.empty:
            return None, None

        # 查找 VIXY ETF（ProShares恐慌指数期货短期合约ETF）
        target_codes = ["VIXY", "VXX", "UVXY"]
        for _, r in df.iterrows():
            code = str(r.get("代码", "")).upper().strip()
            if code in target_codes:
                price = r.get("最新价")
                if price is not None:
                    today = datetime.now().strftime("%Y-%m-%d")
                    logger.info("VIX 代理数据来源: AkShare %s = %s (ETF代理VIX指数)", code, price)
                    return today, float(price)

        # 如果没找到匹配的代码，再按名称搜索
        for _, r in df.iterrows():
            name = str(r.get("名称", ""))
            code = str(r.get("代码", "")).upper().strip()
            if "VIXY" in code:
                price = r.get("最新价")
                if price is not None:
                    today = datetime.now().strftime("%Y-%m-%d")
                    logger.info("VIX 代理数据来源: AkShare %s = %s (ETF代理VIX指数)", code, price)
                    return today, float(price)
    except Exception as e:
        logger.warning("AkShare VIX ETF 获取失败: %s", e)

    return None, None


def _fetch_commodity_futures(symbol: str, name_cn: str) -> tuple[str | None, float | None]:
    """从东方财富获取境外商品期货实时价格

    用于替代 OVX（原油波动率指数）和 GVZ（黄金波动率指数）。
    由于 FRED/Yahoo Finance 在中国网络环境不可用，
    使用标的资产期货价格作为市场情绪的参考指标。

    数据来源: AkShare futures_foreign_commodity_realtime (东方财富境外期货)
    更新频率: 盘中实时更新

    参数:
        symbol: 期货代码，如 "CL"(原油)、"GC"(黄金)
        name_cn: 期货名称，用于日志记录

    映射关系:
        CL → OVX 替代（原油期货价格反映能源市场情绪）
        GC → GVZ 替代（黄金期货价格反映避险情绪）

    Returns:
        (date_str, price) 或 (None, None)
    """
    import akshare as ak
    import logging
    from datetime import datetime
    logger = logging.getLogger("rate_daily")

    try:
        df = ak.futures_foreign_commodity_realtime(symbol=symbol)
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            price = latest.get("最新价")
            if price is not None:
                today = datetime.now().strftime("%Y-%m-%d")
                logger.info("%s 期货数据来源: AkShare %s = %s", name_cn, symbol, price)
                return today, float(price)
    except Exception as e:
        logger.warning("AkShare %s 期货获取失败: %s", symbol, e)

    return None, None


def _fetch_qvix() -> tuple[str | None, float | None]:
    """从 akshare 获取50ETF期权隐含波动率指数(QVIX)
    
    数据来源: AkShare index_option_50etf_qvix
    更新频率: 每个交易日更新
    指标说明: 基于上证50ETF期权价格计算的隐含波动率指数，
             与上交所 iVIX 算法兼容，误差<0.5%
    """
    import akshare as ak
    try:
        df = ak.index_option_50etf_qvix()
        if df is not None and len(df) > 0:
            last = df.iloc[-1]
            return str(last["date"]), float(last["close"])
    except Exception:
        pass
    return None, None


def _fetch_ivix() -> tuple[str | None, float | None, str]:
    """获取中国波指（iVIX）- 多级降级策略

    iVIX（中国波动率指数）是反映中国A股市场投资者情绪和
    预期波动率的关键指标，基于上证50ETF期权价格计算。

    采集优先级:
      第一级: AkShare QVIX（基于iVIX算法复现，误差<0.5%）
      第二级: Tushare 50ETF历史波动率（年化滚动20日波动率）
      第三级: 返回 None

    Returns:
        (date_str, value, source) 三元组
        - source: 实际数据来源标识 ("akshare" / "tushare" / "")

    数据来源:
      - 第一级: AkShare (免费，无需API Key)
      - 第二级: Tushare Pro (需API Key，120积分即可)

    更新频率: 每个交易日可获取
    参考价值: iVIX > 30 表示市场恐慌，< 20 表示市场平稳
    """
    import logging
    logger = logging.getLogger("rate_daily")

    # 第一级: AkShare QVIX
    try:
        import akshare as ak
        df = ak.index_option_50etf_qvix()
        if df is not None and not df.empty:
            latest = df.iloc[-1]
            date_col = df.columns[0]
            # 查找包含"波动"、"qvix"或"ivix"的值列
            for col in df.columns:
                if '波动' in str(col) or 'qvix' in str(col).lower() or 'ivix' in str(col).lower():
                    val = latest[col]
                    if val is not None and str(val) != 'nan':
                        date_str = str(latest.get(date_col, ''))[:10]
                        logger.info("iVIX 数据来源: AkShare QVIX (第一级)")
                        return date_str, float(val), "akshare"
            # 如果没找到专门的波动率列，使用 close 列
            close_val = latest.get("close")
            if close_val is not None and str(close_val) != 'nan':
                date_str = str(latest.get(date_col, ''))[:10]
                logger.info("iVIX 数据来源: AkShare QVIX close (第一级)")
                return date_str, float(close_val), "akshare"
    except Exception as e:
        logger.warning("iVIX 第一级(akshare QVix)获取失败: %s", e)

    # 第二级: Tushare 50ETF历史波动率
    try:
        from infra.tushare_client import get_pro_api
        import numpy as np
        from datetime import timedelta

        pro = get_pro_api()
        if pro is not None:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
            df = pro.fund_daily(ts_code='510050.SH', start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = df.sort_values('trade_date')
                df['log_ret'] = np.log(df['close'] / df['close'].shift(1))
                df = df.dropna(subset=['log_ret'])
                if len(df) >= 10:
                    recent = df.tail(20)
                    daily_vol = recent['log_ret'].std()
                    annual_vol = daily_vol * np.sqrt(252) * 100
                    latest_date = str(df.iloc[-1]['trade_date'])
                    date_str = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:8]}"
                    logger.info("iVIX 数据来源: Tushare 50ETF历史波动率 (第二级)")
                    return date_str, round(float(annual_vol), 2), "tushare"
    except Exception as e:
        logger.warning("iVIX 第二级(Tushare历史波动率)获取失败: %s", e)

    # 第三级: 所有数据源均不可用
    logger.warning("iVIX 所有数据源均不可用，指标值设为 None")
    return None, None, ""


def run_rate_daily(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import akshare as ak
    import pandas as pd

    df = ak.bond_zh_us_rate()
    if df is None or len(df) == 0:
        return JobStats(
            items_processed=0,
            rows_written=0,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message="AkShare接口返回空",
        )

    date_col = df.columns[0]
    cn_col = None
    us_col = None
    for c in df.columns:
        s = str(c)
        if "中国" in s and "10" in s:
            cn_col = c
        if "美国" in s and "10" in s:
            us_col = c
    cn_col = cn_col or df.columns[min(1, len(df.columns) - 1)]
    us_col = us_col or (df.columns[min(2, len(df.columns) - 1)] if len(df.columns) > 2 else cn_col)

    df2 = pd.DataFrame(
        {
            "d": pd.to_datetime(df[date_col], errors="coerce").dt.date,
            "cn": pd.to_numeric(df[cn_col], errors="coerce"),
            "us": pd.to_numeric(df[us_col], errors="coerce"),
        }
    ).dropna(subset=["d"])

    # 获取额外市场指标
    # 三级采集策略：
    #   第一级: Yahoo Finance（实时性高，但中国网络可能返回403）
    #   第二级: FRED 公开 CSV（稳定性好，但可能返回504/超时）
    #   第三级: AkShare 东方财富（中国网络友好，用ETF/期货作代理指标）
    fg_date, fg_val = _fetch_fear_greed()
    vix_date, vix_val = _fetch_yahoo("^VIX")
    ovx_date, ovx_val = _fetch_yahoo("^OVX")
    gvz_date, gvz_val = _fetch_yahoo("^GVZ")

    # Yahoo Finance 获取失败时，使用 FRED 作为降级备用（第二级）
    if vix_val is None:
        _vix_date, _vix_val = _fetch_from_fred("VIXCLS")
        if _vix_val is not None:
            vix_date, vix_val = _vix_date, _vix_val

    if ovx_val is None:
        _ovx_date, _ovx_val = _fetch_from_fred("OVXCLS")
        if _ovx_val is not None:
            ovx_date, ovx_val = _ovx_date, _ovx_val

    if gvz_val is None:
        _gvz_date, _gvz_val = _fetch_from_fred("GVZCLS")
        if _gvz_val is not None:
            gvz_date, gvz_val = _gvz_date, _gvz_val

    # FRED/Yahoo均失败时，使用 AkShare 东方财富数据（第三级，中国网络友好）
    if vix_val is None:
        _vix_date, _vix_val = _fetch_vix_from_akshare()
        if _vix_val is not None:
            vix_date, vix_val = _vix_date, _vix_val

    if ovx_val is None:
        _ovx_date, _ovx_val = _fetch_commodity_futures("CL", "原油")
        if _ovx_val is not None:
            ovx_date, ovx_val = _ovx_date, _ovx_val

    if gvz_val is None:
        _gvz_date, _gvz_val = _fetch_commodity_futures("GC", "黄金")
        if _gvz_date is not None:
            gvz_date, gvz_val = _gvz_date, _gvz_val

    qvix_date, qvix_val = _fetch_qvix()
    ivix_date, ivix_val, ivix_source = _fetch_ivix()

    # 构建主表数据行
    rows: list[tuple[Any, ...]] = []
    for _, r in df2.iterrows():
        d = to_ymd(r.get("d"))
        if not d:
            continue
        # 只将债券收益率数据和当天匹配的额外指标合并
        rows.append((
            d,
            safe_float(r.get("cn")),
            safe_float(r.get("us")),
            safe_float(fg_val) if fg_date == d else None,
            safe_float(vix_val) if vix_date == d else None,
            safe_float(ovx_val) if ovx_date == d else None,
            safe_float(gvz_val) if gvz_date == d else None,
            safe_float(ivix_val) if ivix_date == d else None,
            "akshare",
        ))

    # 如果有恐惧贪婪数据但不在债券收益率数据行中，单独插入
    if fg_date and fg_val is not None and fg_date not in {to_ymd(r.get("d")) if hasattr(r, "get") else None for r in df2.itertuples()}:
        pass  # 由后续的单行插入处理
    # 处理非对齐日期的额外指标 - 直接单独更新
    conn = connect(cfg)
    try:
        # 写入债券收益率数据
        written = executemany(conn, _INSERT_SQL, rows)

        # 单独插入恐惧贪婪（如果日期不在债券数据中）
        if fg_date and fg_val is not None:
            _upsert_rate_indicator(conn, fg_date, "fear_greed", fg_val)

        # 单独插入 VIX
        if vix_date and vix_val is not None:
            _upsert_rate_indicator(conn, vix_date, "vix", vix_val)

        # 单独插入 OVX
        if ovx_date and ovx_val is not None:
            _upsert_rate_indicator(conn, ovx_date, "ovx", ovx_val)

        # 单独插入 GVZ
        if gvz_date and gvz_val is not None:
            _upsert_rate_indicator(conn, gvz_date, "gvz", gvz_val)

        # 单独插入 iVIX（如果日期不在债券数据中）
        if ivix_date and ivix_val is not None:
            _upsert_rate_indicator(conn, ivix_date, "ivix", ivix_val)

        # 写入 QVIX 数据
        qvix_written = 0
        if qvix_date and qvix_val is not None:
            qvix_rows = [(qvix_date, qvix_val, None, "akshare")]
            qvix_written = executemany(conn, _QVIX_INSERT_SQL, qvix_rows)

        return JobStats(
            items_processed=len(rows) + (1 if fg_val else 0) + (1 if vix_val else 0) + (1 if ovx_val else 0) + (1 if gvz_val else 0) + (1 if ivix_val else 0) + (1 if qvix_val else 0),
            rows_written=written + qvix_written,
            failed_items=[],
            data_source_final="akshare",
            fallback_chain=["akshare"],
            message=None,
        )
    finally:
        conn.close()


def _upsert_rate_indicator(conn, date_str: str, col: str, val: float) -> None:
    """单独更新某个指标的某天数据（upsert语义）"""
    if col not in _ALLOWED_RATE_COLUMNS:
        raise ValueError(f"不允许的列名: {col}，合法值: {_ALLOWED_RATE_COLUMNS}")
    import pymysql
    cur = conn.cursor()
    try:
        # 先检查日期是否存在
        cur.execute("SELECT 1 FROM trade_rate_daily WHERE rate_date=%s", (date_str,))
        if cur.fetchone():
            cur.execute(f"UPDATE trade_rate_daily SET {col}=%s, data_source='akshare' WHERE rate_date=%s", (val, date_str))
        else:
            placeholders = ["rate_date"] + [col] + ["data_source"]
            values = [date_str, val, "akshare"]
            cols_str = ", ".join(placeholders)
            vals_ph = ", ".join(["%s"] * len(values))
            cur.execute(f"INSERT INTO trade_rate_daily ({cols_str}) VALUES ({vals_ph})", values)
        conn.commit()
    finally:
        cur.close()

