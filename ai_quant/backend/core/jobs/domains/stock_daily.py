"""
行情日线采集任务（stock_daily）
数据源：QMT（批量预取主） → TuShare（备1） → AkShare（备2）三级容灾
写入表：trade_stock_daily
"""

from __future__ import annotations

import time as _time_mod
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from datetime import date, datetime
from threading import Lock
from typing import Any

import pandas as pd

from core.db import MySQLConfig, connect, executemany, query_dict
from core.jobs.checkpoint import delete_checkpoint, save_checkpoint
from core.jobs.common import JobStats, safe_float
from infra.storage.logging_service import get_logger

logger = get_logger("stock_daily")

# 当前任务 runId，用于日志链路追踪
_RUN_ID: str = ""


def set_run_id(run_id: str) -> None:
    global _RUN_ID
    _RUN_ID = run_id


def _log(msg: str):
    """打印带时间戳的日志（同时输出到控制台和日志系统）

    Args:
        msg: 日志消息内容
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    run_tag = f" [{_RUN_ID}]" if _RUN_ID else ""
    print(f"[{ts}]{run_tag} [stock_daily] {msg}")
    logger.info(msg, extra={"run_id": _RUN_ID} if _RUN_ID else {})


_INSERT_SQL = """
INSERT INTO trade_stock_daily
(stock_code, trade_date, close_price, volume, rsi14, ma20, stock_name)
VALUES (%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
close_price=VALUES(close_price),
volume=VALUES(volume),
rsi14=VALUES(rsi14),
ma20=VALUES(ma20),
stock_name=COALESCE(VALUES(stock_name), stock_name)
"""


def _latest_dates(conn) -> dict[str, str]:
    """查询数据库中各股票已采集数据的最新交易日（步骤1）

    用于后续确定每只股票需增量采集的起始日期，
    避免重复采集已有数据。

    Args:
        conn: 数据库连接对象

    Returns:
        dict: {stock_code: "YYYYMMDD"} 格式的最新日期映射表
    """
    _log("步骤1: 查询数据库中各股票已有数据的最新日期...")
    rows = query_dict(conn, "SELECT stock_code, MAX(trade_date) AS max_date FROM trade_stock_daily GROUP BY stock_code")
    out: dict[str, str] = {}
    for r in rows:
        md = r.get("max_date")
        if md:
            out[str(r["stock_code"])] = md.strftime("%Y%m%d")
    _log(f"步骤1完成: 从数据库查到 {len(out)} 只股票的最新日期")
    return out


def _existing_dates_map(conn, stock_codes: list[str]) -> dict[str, set[str]]:
    """查询数据库中各股票已采集数据的具体日期集合（按股票+日期维度去重）

    用于在采集结果写入前过滤已存在的记录，避免重复写入。

    Args:
        conn: 数据库连接对象
        stock_codes: 需要查询的股票代码列表

    Returns:
        dict: {stock_code: {"2024-01-02", "2024-01-03", ...}} 格式的日期集合映射
    """
    if not stock_codes:
        return {}

    result: dict[str, set[str]] = {}
    # 分批查询，避免SQL过长
    batch_size = 500
    for i in range(0, len(stock_codes), batch_size):
        batch = stock_codes[i:i + batch_size]
        placeholders = ",".join(["%s"] * len(batch))
        rows = query_dict(
            conn,
            f"SELECT stock_code, trade_date FROM trade_stock_daily WHERE stock_code IN ({placeholders})",
            tuple(batch),
        )
        for r in rows:
            code = str(r["stock_code"])
            td = r.get("trade_date")
            if td:
                dstr = td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)[:10]
                if code not in result:
                    result[code] = set()
                result[code].add(dstr)

    _log(f"步骤1.5: 查询到 {len(result)} 只股票的已有日期数据，共 {sum(len(v) for v in result.values())} 条记录")
    return result


def _infer_exchange(code_num: str) -> str:
    """根据股票代码前6位推断所属交易所

    上交所股票代码以6开头，深交所股票代码以0/3开头
    北交所股票代码以920开头（北京证券交易所）

    Args:
        code_num: 6位数字股票代码（不含后缀）

    Returns:
        str: "SH"（上交所）、"SZ"（深交所）或 "BJ"（北交所）
    """
    if code_num.startswith("6"):
        return "SH"
    if code_num.startswith("920"):
        return "BJ"  # 北京证券交易所
    return "SZ"


def _fetch_stock_list_from_akshare() -> pd.DataFrame | None:
    """在子线程中调用 akshare API，供 ThreadPoolExecutor 超时控制使用"""
    import akshare as ak
    return ak.stock_info_a_code_name()


def _get_stock_list(max_stocks: int) -> tuple[list[str], dict[str, str]]:
    """获取全市场A股股票列表（步骤2）

    优先通过 akshare 获取，若失败则从数据库查询已存在的股票代码作为备用。

    Args:
        max_stocks: 最大股票数量限制

    Returns:
        tuple: (股票代码列表, {代码: 名称}映射字典)
    """
    _log(f"步骤2: 获取股票列表 (限制={max_stocks} 只)...")

    # 尝试 akshare
    try:
        with ThreadPoolExecutor(max_workers=1) as exc:
            future = exc.submit(_fetch_stock_list_from_akshare)
            try:
                df = future.result(timeout=60)
                if df is not None and len(df) > 0:
                    codes: list[str] = []
                    name_map: dict[str, str] = {}
                    for _, r in df.iterrows():
                        code_num = str(r.get("code") or "").strip()
                        name = str(r.get("name") or "").strip()
                        if not code_num:
                            continue
                        code = f"{code_num}.{_infer_exchange(code_num)}"
                        codes.append(code)
                        if name:
                            name_map[code] = name
                        if 0 < max_stocks <= len(codes):
                            break
                    _log(f"步骤2完成: 获取到 {len(codes)} 只股票 (来源: akshare)")
                    return codes, name_map
            except TimeoutError:
                _log("步骤2: akshare 超时，尝试从数据库备用...")
    except Exception as e:
        _log(f"步骤2: akshare 异常: {type(e).__name__}: {e}，尝试从数据库备用...")

    # 备用：从数据库获取股票列表
    _log("步骤2: 从 trade_stock_daily 查询已有股票代码...")
    try:
        from core.db import load_mysql_config, connect, query_dict
        _cfg = load_mysql_config()
        _tmp_conn = connect(_cfg)
        try:
            code_rows = query_dict(_tmp_conn, "SELECT DISTINCT stock_code FROM trade_stock_daily ORDER BY stock_code")
            if code_rows:
                codes = [r["stock_code"] for r in code_rows if r.get("stock_code")]
                if max_stocks > 0:
                    codes = codes[:max_stocks]
                _log(f"步骤2完成: 从数据库获取 {len(codes)} 只股票")
                return codes, {}
        finally:
            _tmp_conn.close()
    except Exception as e:
        _log(f"步骤2: 数据库备用方案失败: {type(e).__name__}: {e}")

    _log("步骤2失败: 无法获取股票列表")
    return [], {}


# ---- QMT 批量预取缓存 ----
# 用于存储批量预取的 QMT 数据，避免逐只 HTTP 请求
_qmt_batch_cache: dict[str, pd.DataFrame] = {}
_QMT_BATCH_SIZE = 200


def _qmt_batch_prefetch(stock_codes: list[str], start: str, end: str) -> int:
    """批量预取 QMT 数据并缓存到内存

    将股票列表按 _QMT_BATCH_SIZE 分批，每批通过 kline_batch 接口一次性获取，
    减少HTTP往返次数，大幅提升QMT数据获取效率。

    Args:
        stock_codes: 需要预取的股票代码列表
        start: 开始日期 YYYYMMDD
        end: 结束日期 YYYYMMDD

    Returns:
        成功预取的股票数量
    """
    global _qmt_batch_cache
    _qmt_batch_cache = {}

    try:
        from infra.qmt_gateway_client import historical_kline_batch, check_health
    except ImportError:
        _log("[批量预取] 无法导入 qmt_gateway_client，跳过批量预取")
        return 0

    try:
        if not check_health():
            _log("[批量预取] QMT Gateway 不可用，跳过批量预取")
            return 0
    except Exception:
        _log("[批量预取] QMT Gateway 健康检查失败，跳过批量预取")
        return 0

    total_fetched = 0
    batch_count = (len(stock_codes) + _QMT_BATCH_SIZE - 1) // _QMT_BATCH_SIZE

    for i in range(batch_count):
        batch = stock_codes[i * _QMT_BATCH_SIZE:(i + 1) * _QMT_BATCH_SIZE]
        _log(f"[批量预取] 第 {i+1}/{batch_count} 批，{len(batch)} 只股票...")

        try:
            raw = historical_kline_batch(
                stock_codes=batch,
                period="1d",
                start_time=start,
                end_time=end,
                dividend_type="front",
                fill_data=True,
            )
        except Exception as e:
            _log(f"[批量预取] 第 {i+1} 批请求失败: {type(e).__name__}: {e}")
            continue

        results = raw.get("results") or {}
        for code, item in results.items():
            rows = item.get("rows") or []
            if not rows:
                continue
            try:
                df = pd.DataFrame(rows)
                if "date" not in df.columns or "close" not in df.columns:
                    continue
                df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
                if "volume" in df.columns:
                    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
                else:
                    df["volume"] = None
                df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
                if len(df) > 0:
                    _qmt_batch_cache[code] = df
                    total_fetched += 1
            except Exception:
                continue

    _log(f"[批量预取] 完成: 共预取 {total_fetched}/{len(stock_codes)} 只股票的 QMT 数据")
    return total_fetched


def _qmt_batch_clear() -> None:
    """清理批量预取缓存"""
    global _qmt_batch_cache
    _qmt_batch_cache = {}


def _fetch_qmt(code: str, start: str, end: str = "") -> pd.DataFrame | None:
    """通过 QMT Gateway 获取股票历史K线数据

    优先从批量预取缓存中读取，缓存未命中时回退到逐只请求。

    Args:
        code: 股票代码，如 "600519.SH"
        start: 开始日期，YYYYMMDD 格式
        end: 结束日期，YYYYMMDD 格式，默认为空表示至今

    Returns:
        pd.DataFrame | None: 包含 date/close/volume 列的 DataFrame，失败返回 None
    """
    # 优先从批量预取缓存中获取
    if code in _qmt_batch_cache:
        df = _qmt_batch_cache[code]
        _log(f"步骤3-1: QMT 批量缓存命中 {code}，共 {len(df)} 条")
        return df

    _log(f"步骤3-1: 尝试从 QMT Gateway 获取 {code} 日线数据 (start={start}, end={end})")
    try:
        from infra.qmt_gateway_client import historical_kline

        raw = historical_kline(
            stock_code=code,
            period="1d",
            start_time=start,
            end_time=end,
            dividend_type="front",
            fill_data=True,
        )
        rows = raw.get("rows") or []
        if not rows:
            _log(f"步骤3-1: QMT 返回 {code} 数据为空")
            return None
        df = pd.DataFrame(rows)
        if "date" not in df.columns or "close" not in df.columns:
            _log(f"步骤3-1: QMT 返回 {code} 数据缺少 date/close 列")
            return None
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        else:
            df["volume"] = None
        result = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        _log(f"步骤3-1: QMT 成功获取 {code} 数据，共 {len(result)} 条 (日期: {result['date'].min().date()} ~ {result['date'].max().date()})")
        return result
    except Exception as e:
        _log(f"步骤3-1: QMT 获取 {code} 失败: {type(e).__name__}: {e}")
        return None


def _fetch_tushare(code: str, start: str, end: str = "") -> pd.DataFrame | None:
    """通过 TuShare 获取股票历史K线数据（第二级备选数据源）

    当 QMT Gateway 获取失败时使用此函数。
    通过项目统一封装的 infra.tushare_client 模块调用，
    无需额外配置环境变量，内置重试机制应对 API 限流。

    Args:
        code: 股票代码，如 "600519.SH"（TuShare 格式，已是 代码.交易所）
        start: 开始日期，YYYYMMDD 格式
        end: 结束日期，YYYYMMDD 格式，默认为空表示至今

    Returns:
        pd.DataFrame | None: 包含 date/close/volume 列的 DataFrame，失败返回 None
    """
    _log(f"步骤3-2: 尝试从 TuShare 获取 {code} 日线数据 (start={start}, end={end})")
    max_tushare_retries = 2
    for attempt in range(max_tushare_retries):
        try:
            from infra.tushare_client import get_pro_api

            pro = get_pro_api()
            df = pro.daily(ts_code=code, start_date=start, end_date=end)
            if df is None or len(df) == 0:
                _log(f"步骤3-2: TuShare 返回 {code} 数据为空 (尝试 {attempt+1}/{max_tushare_retries})")
                if attempt < max_tushare_retries - 1:
                    import time
                    time.sleep(1.0)
                    continue
                return None
            df = df.rename(columns={"trade_date": "date", "vol": "volume"})
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d", errors="coerce")
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            result = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            _log(f"步骤3-2: TuShare 成功获取 {code} 数据，共 {len(result)} 条 (日期: {result['date'].min().date()} ~ {result['date'].max().date()})")
            return result
        except Exception as e:
            _log(f"步骤3-2: TuShare 获取 {code} 失败: {type(e).__name__}: {e} (尝试 {attempt+1}/{max_tushare_retries})")
            if attempt < max_tushare_retries - 1:
                import time
                time.sleep(1.0)
                continue
            return None
    return None


def _fetch_akshare(code: str, start: str, end: str = "") -> pd.DataFrame | None:
    """通过 AkShare（东方财富）获取股票历史K线数据（第三级备选数据源）

    当 QMT Gateway 和 TuShare 均失败时使用本函数通过
    ak.stock_zh_a_hist() 接口获取日线数据。
    AkShare 为免费开源接口，无需额外认证，内置重试机制应对临时抖动。

    Args:
        code: 股票代码，如 "600519.SH"
        start: 开始日期，YYYYMMDD 格式
        end: 结束日期，YYYYMMDD 格式，默认为空表示至今

    Returns:
        pd.DataFrame | None: 包含 date/close/volume 列的 DataFrame，失败返回 None
    """
    _log(f"步骤3-3: 尝试从 AkShare 获取 {code} 日线数据 (start={start}, end={end})")
    max_akshare_retries = 3
    for attempt in range(max_akshare_retries):
        try:
            import akshare as ak

            code_num = code.split(".")[0]
            df = ak.stock_zh_a_hist(symbol=code_num, period="daily", start_date=start, end_date=end, adjust="qfq")
            if df is None or len(df) == 0:
                _log(f"步骤3-3: AkShare 返回 {code} 数据为空 (尝试 {attempt+1}/{max_akshare_retries})")
                if attempt < max_akshare_retries - 1:
                    import time
                    time.sleep(2.0)
                    continue
                return None
            col_map = {"日期": "date", "收盘": "close", "成交量": "volume"}
            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
            if "date" not in df.columns or "close" not in df.columns:
                _log(f"步骤3-3: AkShare 返回 {code} 数据缺少date/close列，可用列: {list(df.columns)} (尝试 {attempt+1}/{max_akshare_retries})")
                if attempt < max_akshare_retries - 1:
                    import time
                    time.sleep(2.0)
                    continue
                return None
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            if "volume" in df.columns:
                df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
            else:
                df["volume"] = None
            result = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
            _log(f"步骤3-3: AkShare 成功获取 {code} 数据，共 {len(result)} 条 (日期: {result['date'].min().date()} ~ {result['date'].max().date()})")
            return result
        except Exception as e:
            _log(f"步骤3-3: AkShare 获取 {code} 失败: {type(e).__name__}: {e} (尝试 {attempt+1}/{max_akshare_retries})")
            if attempt < max_akshare_retries - 1:
                import time
                time.sleep(2.0)
                continue
            return None
    return None


def _rsi14(close: list[float]) -> list[float | None]:
    """计算相对强弱指标 RSI14

    RSI14 使用14个交易日的收盘价计算。采用平滑递推算法：
    - 起始14日使用简单平均法计算平均涨幅和平均跌幅
    - 之后使用 Wilder 平滑法递推: new_avg = (prev_avg * 13 + current) / 14

    Args:
        close: 收盘价序列（按时间升序排列），至少需要15个数据点

    Returns:
        list[float | None]: RSI14 计算结果，长度与输入序列一致。
            前14个元素为 None（数据不足），有效值范围为 0~100
    """
    n = len(close)
    out: list[float | None] = [None] * n
    if n < 15:
        return out
    gains = [0.0] * n
    losses = [0.0] * n
    for i in range(1, n):
        d = close[i] - close[i - 1]
        gains[i] = d if d > 0 else 0.0
        losses[i] = -d if d < 0 else 0.0
    avg_gain = sum(gains[1:15]) / 14.0
    avg_loss = sum(losses[1:15]) / 14.0
    for i in range(14, n):
        if i > 14:
            avg_gain = (avg_gain * 13.0 + gains[i]) / 14.0
            avg_loss = (avg_loss * 13.0 + losses[i]) / 14.0
        if avg_loss == 0:
            out[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            out[i] = 100.0 - 100.0 / (1.0 + rs)
    return out


def _ma20(close: list[float]) -> list[float | None]:
    """计算20日移动平均线 MA20（滑动窗口算法）

    使用滑动窗口（FIFO队列）维护最近20个收盘价。
    窗口未满（前19个元素）时返回 None。

    Args:
        close: 收盘价序列（按时间升序排列）

    Returns:
        list[float | None]: MA20 计算结果，长度与输入序列一致，
            前19个元素为 None（窗口未满），从第20个元素开始有有效值
    """
    n = len(close)
    out: list[float | None] = [None] * n
    if n == 0:
        return out
    window: list[float] = []
    s = 0.0
    for i, v in enumerate(close):
        window.append(v)
        s += v
        if len(window) > 20:
            s -= window.pop(0)
        if i >= 19:
            out[i] = s / float(len(window))
    return out


def _process_one_stock(
    code: str,
    latest: str | None,
    data_start: str,
    today_str: str,
    name_map: dict[str, str],
    progress_lock: Lock,
    processed_ref: list[int],
    total_count: int,
    cfg: MySQLConfig | None = None,
) -> dict[str, Any] | None:
    """处理单只股票的完整采集流程（供线程池并发调用）

    包含：QMT获取 → TuShare备选 → AkShare备选 → 数据清洗 → 计算RSI14/MA20 → 过滤已有数据 → 组装写入行

    Args:
        code: 股票代码，如 "600519.SH"
        latest: 该股票数据库中已有数据的最新日期 YYYYMMDD，无则 None
        data_start: 默认数据起始日期 YYYYMMDD
        today_str: 当前日期 YYYYMMDD
        name_map: {代码: 名称} 映射字典
        progress_lock: 线程安全的进度计数锁
        processed_ref: 已处理数量的可变引用（列表包裹的int），用于线程安全递增
        total_count: 股票总数，用于日志输出进度
        cfg: MySQL 数据库配置，用于按需查询单只股票的已有日期集合

    Returns:
        dict | None: 成功时返回 {"code": str, "rows": list[tuple], "source": str}，
            失败时返回 {"code": str, "failed": True}，异常时返回 None
    """
    try:
        with progress_lock:
            processed_ref[0] += 1
            idx = processed_ref[0]

        start = latest if latest and latest < today_str else (latest or data_start)
        _log(f"--- [{idx}/{total_count}] 处理 {code} (最新日期: {latest or '无'}, 采集: {start}~{today_str}) ---")

        # 三级容灾：QMT → TuShare → AkShare
        # QMT 走批量预取缓存，速度最快（约200ms/只 vs TuShare限流后~700ms/只）
        df = None
        source = "unknown"
        for fetch_fn, src_name in [
            (_fetch_qmt, "qmt"),
            (_fetch_tushare, "tushare"),
            (_fetch_akshare, "akshare"),
        ]:
            df = fetch_fn(code, start, today_str)
            if df is not None and len(df) > 0:
                source = src_name
                break
            _log(f"[FALLBACK] {code}: {src_name} 获取失败，尝试下一级数据源...")

        if df is None or len(df) == 0:
            _log(f"[WARN] {code}: 所有数据源（QMT/TuShare/AkShare）均无法获取数据，跳过")
            return {"code": code, "failed": True}

        _log(f"步骤4: {code} 数据清洗 (原始={len(df)}行)")
        df = df.dropna(subset=["close"])
        if len(df) == 0:
            _log(f"[WARN] {code}: close列全部为空，跳过")
            return {"code": code, "failed": True}

        close_vals = [float(x) for x in df["close"].tolist() if x is not None and float(x) == float(x)]
        rsi_seq = _rsi14(close_vals)
        ma_seq = _ma20(close_vals)
        _log(f"步骤5: {code} 指标计算完成 (RSI有效={sum(1 for x in rsi_seq if x is not None)}, MA有效={sum(1 for x in ma_seq if x is not None)})")

        stock_name = name_map.get(code)
        rsi_map = {}
        ma_map = {}
        for i, (_, row) in enumerate(df.iterrows()):
            if i >= len(rsi_seq):
                break
            key = str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"])[:10]
            rsi_map[key] = rsi_seq[i]
            if i < len(ma_seq):
                ma_map[key] = ma_seq[i]

        rows: list[tuple[Any, ...]] = []
        skipped = 0

        # 按需查询单只股票的已有日期集合（避免全量查询导致超时）
        existing_dates: set[str] | None = None
        if cfg is not None:
            try:
                conn_q = connect(cfg)
                try:
                    date_rows = query_dict(
                        conn_q,
                        "SELECT trade_date FROM trade_stock_daily WHERE stock_code = %s",
                        (code,),
                    )
                    existing_dates = set()
                    for r in date_rows:
                        td = r.get("trade_date")
                        if td:
                            existing_dates.add(td.strftime("%Y-%m-%d") if hasattr(td, "strftime") else str(td)[:10])
                finally:
                    conn_q.close()
            except Exception as e:
                _log(f"[WARN] {code}: 查询已有日期失败({type(e).__name__})，将不跳过已有数据")
                existing_dates = None

        for _, row in df.iterrows():
            dt = row["date"]
            dstr = dt.date().isoformat() if hasattr(dt, "date") else str(dt)[:10]
            # 按股票+日期维度过滤：如果数据库中已有该日期的数据，跳过
            if existing_dates and dstr in existing_dates:
                skipped += 1
                continue
            close = safe_float(row.get("close"))
            vol = row.get("volume")
            volume = int(float(vol)) if vol not in (None, "") and float(vol) == float(vol) else None
            rsi = rsi_map.get(dstr)
            ma20 = ma_map.get(dstr)
            rows.append((code, dstr, close, volume, rsi, ma20, stock_name))

        if skipped > 0:
            _log(f"步骤6: {code} 跳过 {skipped} 条已有数据，生成 {len(rows)} 条新写入数据 (名称={stock_name or '未知'}, 数据源={source})")
        else:
            _log(f"步骤6: {code} 生成 {len(rows)} 条写入数据 ({df['date'].min().date()}~{df['date'].max().date()}, 名称={stock_name or '未知'}, 数据源={source})")
        return {"code": code, "rows": rows, "source": source}
    except Exception as e:
        _log(f"[ERROR] {code}: 处理异常: {type(e).__name__}: {e}")
        return {"code": code, "failed": True}


def run_stock_daily(cfg: MySQLConfig, mode: str | None, params: dict[str, Any] | None, progress_callback=None) -> JobStats:
    """行情日线数据采集任务主函数

    采集全市场A股（或指定股票）的日线行情数据，包括：
    - 基础数据：收盘价、成交量
    - 技术指标：RSI14、MA20
    - 数据来源：QMT Gateway（主） → TuShare（备1） → AkShare（备2）

    数据流：
    1. 查询数据库已有最新日期 -> 2. 获取股票列表 -> 3. QMT/TuShare/AkShare获取K线 -> 4. 计算RSI/MA -> 5. 批量写入

    Args:
        cfg: MySQL 数据库配置
        mode: 运行模式，固定为 "full"（全量模式），测试模式已禁用
        params: 参数字典
            - data_start: 数据起始日期 YYYYMMDD，默认 "20230101"
            - max_stocks: 最大采集股票数，默认 200（0=全量）
            - max_workers: 并发线程数，默认 4

    Returns:
        JobStats: 任务执行统计，包含处理数、写入行数、失败列表、数据源等信息
    """
    _log("=" * 60)
    _log(f"【开始执行 stock_daily 采集任务】mode={mode}, params={params}")
    _log("=" * 60)

    # 从参数中提取 runId 用于日志链路追踪
    run_id_from_params = str((params or {}).get("_run_id") or "").strip()
    if run_id_from_params:
        set_run_id(run_id_from_params)

    data_start = str((params or {}).get("data_start") or "20230101").strip() or "20230101"
    max_stocks_val = (params or {}).get("max_stocks")
    max_stocks = int(max_stocks_val) if max_stocks_val is not None else 200
    max_workers = max(1, int((params or {}).get("max_workers") or 4))

    # 支持指定股票代码列表进行定向重采
    stock_codes_override = (params or {}).get("stock_codes")
    is_retry = stock_codes_override is not None

    _log(f"配置参数: data_start={data_start}, max_stocks={max_stocks}, max_workers={max_workers}, is_retry={is_retry}")

    total_rows = 0
    failed: list[str] = []
    fallback_chain: list[str] = []
    data_source_final = "unknown"

    # 当前任务的 runId，用于检查点文件命名
    _task_run_id = run_id_from_params

    conn = connect(cfg)
    try:
        latest_map = _latest_dates(conn)
        today_str = date.today().strftime("%Y%m%d")
        _log(f"当前日期: {today_str}")

        stock_list, name_map = _get_stock_list(max_stocks)
        if not stock_list:
            _log("[WARN] 获取股票列表为空，无法执行采集")
            return JobStats(
                items_processed=0, rows_written=0, failed_items=[],
                data_source_final="unknown", fallback_chain=[],
                message="股票列表为空",
            )

        # 定向重采模式：使用指定的股票代码列表覆盖
        if is_retry and stock_codes_override:
            _log(f"定向重采模式: 覆盖 {len(stock_codes_override)} 只指定股票")
            stock_list = stock_codes_override
            name_map = {}

        # 断点续传：检查是否有上次中断的检查点
        resume_skip_count = 0
        if _task_run_id:
            from core.jobs.checkpoint import get_checkpoint_position
            cp_done, cp_processed, cp_failed = get_checkpoint_position(_task_run_id)
            if cp_done > 0:
                cp_processed_set = set(cp_processed)
                cp_failed_set = set(cp_failed)
                # 过滤：移除已处理的股票，恢复已失败的列表
                remaining = [c for c in stock_list if c not in cp_processed_set and c not in cp_failed_set]
                resume_skip_count = len(stock_list) - len(remaining)
                failed = list(cp_failed)
                _log(f"断点续传: 检查点发现 {len(cp_processed)} 只已处理 + {len(cp_failed)} 只已失败 = {cp_done} 只已完成，跳过 {resume_skip_count} 只，剩余 {len(remaining)} 只待处理")
                stock_list = remaining

        _log(f"步骤2完成: 最终股票列表共 {len(stock_list)} 只")

        _log("步骤3: 检查数据源可用性...")
        qmt_available = False
        try:
            from infra.qmt_gateway_client import check_health
            qmt_available = check_health()
            if qmt_available:
                _log("步骤3: QMT Gateway 连接正常（主数据源，批量预取）")
            else:
                _log("步骤3: QMT Gateway 不可用，将使用TuShare/AkShare备选")
        except Exception as e:
            _log(f"步骤3: QMT Gateway 检查异常: {type(e).__name__}: {e}，将使用TuShare/AkShare备选")

        tushare_available = False
        try:
            from infra.tushare_client import get_pro_api
            get_pro_api()
            tushare_available = True
            _log("步骤3: TuShare API 连接正常（备选数据源）")
        except Exception as e:
            _log(f"步骤3: TuShare API 不可用: {type(e).__name__}: {e}")

        if not qmt_available and not tushare_available:
            _log("步骤3: QMT 和 TuShare 均不可用，仅依赖 AkShare（最终备选）")

        # 步骤3.5: 如果 QMT 可用，使用批量接口预取数据（大幅减少HTTP往返）
        if qmt_available:
            _log("步骤3.5: QMT 批量预取开始...")
            prefetch_start = _time_mod.time()
            prefetched = _qmt_batch_prefetch(stock_list, data_start, today_str)
            prefetch_elapsed = _time_mod.time() - prefetch_start
            _log(f"步骤3.5: QMT 批量预取完成，{prefetched} 只股票，耗时 {prefetch_elapsed:.1f} 秒")
        else:
            _qmt_batch_clear()

        total_count = len(stock_list)
        _log(f"\n开始并发处理 (共 {total_count} 只股票, {max_workers} 线程)...")

        progress_lock = Lock()
        processed_ref = [resume_skip_count]
        processed_codes: list[str] = []
        batch_rows: list[tuple[Any, ...]] = []
        # 中间提交阈值：每处理200只股票提交一次中间批次，降低数据丢失风险
        intermediate_batch_size = 200
        # 检查点保存阈值
        checkpoint_interval = 100

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_code = {}
            for code in stock_list:
                latest = latest_map.get(code)
                future = executor.submit(
                    _process_one_stock,
                    code, latest, data_start, today_str, name_map,
                    progress_lock, processed_ref, total_count,
                    cfg,
                )
                future_to_code[future] = code

            stock_done_count = 0
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                stock_done_count += 1
                try:
                    result = future.result(timeout=120)
                except TimeoutError:
                    _log(f"[ERROR] {code}: 处理超时(120秒)，跳过")
                    failed.append(code)
                    continue
                except Exception as e:
                    _log(f"[ERROR] {code}: 线程执行异常: {type(e).__name__}: {e}")
                    failed.append(code)
                    continue

                if result is None:
                    failed.append(code)
                    continue

                if result.get("failed"):
                    failed.append(result["code"])
                    continue

                rows = result.get("rows") or []
                batch_rows.extend(rows)
                processed_codes.append(code)
                src = result.get("source", "unknown")
                data_source_final = src
                if src not in fallback_chain:
                    fallback_chain.append(src)

                # Bug A: 每100只股票更新一次任务进度（itemsProcessed）
                if progress_callback and stock_done_count % 100 == 0:
                    try:
                        progress_callback(processed_ref[0], itemsTotal=total_count + resume_skip_count)
                    except Exception:
                        pass

                # 断点续传：每处理100只股票保存一次检查点
                if _task_run_id and stock_done_count % checkpoint_interval == 0 and (processed_codes or failed):
                    try:
                        save_checkpoint(_task_run_id, {
                            "processed_codes": list(processed_codes),
                            "failed_codes": list(failed),
                        })
                    except Exception:
                        pass

                # 中间批次提交（独立于断点续传，降低数据丢失风险）
                if stock_done_count % intermediate_batch_size == 0 and batch_rows:
                    try:
                        conn.ping(reconnect=True)
                    except Exception:
                        conn.close()
                        conn = connect(cfg)
                    _log(f"[中间提交] 写入 {len(batch_rows)} 条记录 (已处理 {stock_done_count}/{total_count})...")
                    executemany(conn, _INSERT_SQL, batch_rows)
                    total_rows += len(batch_rows)
                    batch_rows.clear()

        processed = total_count + resume_skip_count

        # 提交剩余批次
        if batch_rows:
            try:
                conn.ping(reconnect=True)
            except Exception:
                conn.close()
                conn = connect(cfg)
            _log(f"\n步骤7: 批量写入数据库 (共 {len(batch_rows)} 条记录)...")
            written = executemany(conn, _INSERT_SQL, batch_rows)
            total_rows += len(batch_rows)
            _log(f"步骤7完成: 成功写入 {len(batch_rows)} 条记录 (累计: {total_rows})")
        else:
            _log("步骤7: 所有数据已在中间批次全部提交")

        _log("=" * 60)
        _log(f"【采集完成】处理={processed}只, 写入={total_rows}行, 失败={len(failed)}只, 数据源={data_source_final}, 线程数={max_workers}")
        _log("=" * 60)

        # 任务完成后清理检查点和批量缓存
        _qmt_batch_clear()
        if _task_run_id:
            try:
                delete_checkpoint(_task_run_id)
                _log("检查点已清理")
            except Exception:
                pass

        return JobStats(
            items_processed=processed,
            rows_written=total_rows,
            failed_items=failed,
            data_source_final=data_source_final,
            fallback_chain=list(dict.fromkeys(fallback_chain)),
            message=None if not failed else f"失败 {len(failed)} 只股票",
        )
    finally:
        conn.close()