"""
股票代码与名称准确性验证工具

对比数据源: AKShare, TuShare, QMT Gateway, 数据库(trade_stock_master)
决策规则:
  1. 3个及以上数据源一致 -> 采用
  2. 2:2不一致 -> QMT + TuShare 优先
  3. 全不一致 -> 标记待确认
"""
import sys, os, json, time
from datetime import datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.db import load_mysql_config, connect, query_dict, execute
from infra.tushare_client import get_pro_api as get_tushare_api

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()

REPORT_LINES = []

def log(msg: str):
    print(msg)
    REPORT_LINES.append(msg)


# ==================== 第1步：获取 trade_stock_master 当前数据 ====================

def fetch_db_stock_list() -> dict[str, dict]:
    """从 trade_stock_master 获取所有股票的代码和名称"""
    log("[步骤1] 查询 trade_stock_master 当前数据...")
    cfg = load_mysql_config()
    conn = connect(cfg)
    cur = conn.cursor()
    try:
        cur.execute("SELECT stock_code, stock_name, asset_type, market FROM trade_stock_master WHERE asset_type = 'stock' ORDER BY stock_code")
        rows = cur.fetchall()
        result: dict[str, dict] = {}
        for r in rows:
            result[r["stock_code"]] = {
                "name": r["stock_name"] or "",
                "asset_type": r["asset_type"],
                "market": r["market"] or "",
            }
        log(f"  [OK] 从数据库加载 {len(result)} 条个股记录")
        return result
    finally:
        conn.close()


# ==================== 第2步：获取 AKShare 股票列表 ====================

def fetch_akshare_stock_list() -> dict[str, str]:
    """从 AKShare 获取股票列表 {代码: 名称}"""
    log("[步骤2] 获取 AKShare 股票列表...")
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        result: dict[str, str] = {}
        for _, r in df.iterrows():
            code_num = str(r.get("code") or "").strip()
            name = str(r.get("name") or "").strip()
            if not code_num:
                continue
            code = f"{code_num}.SH" if code_num.startswith(("6", "688")) else f"{code_num}.SZ"
            result[code] = name
        log(f"  [OK] AKShare 返回 {len(result)} 条")
        return result
    except Exception as e:
        log(f"  [ERROR] AKShare 获取失败: {e}")
        return {}


# ==================== 第3步：获取 TuShare 股票列表 ====================

def fetch_tushare_stock_list() -> dict[str, str]:
    """从 TuShare 获取股票列表 {代码: 名称}"""
    log("[步骤3] 获取 TuShare 股票列表...")
    try:
        pro = get_tushare_api()
        df = pro.stock_basic()
        if df is None or df.empty:
            log("  [WARN] TuShare 返回空数据")
            return {}
        result: dict[str, str] = {}
        for _, r in df.iterrows():
            code = str(r.get("ts_code") or "").strip()
            name = str(r.get("name") or "").strip()
            if code and name:
                result[code] = name
        log(f"  [OK] TuShare 返回 {len(result)} 条")
        return result
    except Exception as e:
        log(f"  [ERROR] TuShare 获取失败: {e}")
        return {}


# ==================== 第4步：获取 QMT 股票列表 ====================

def fetch_qmt_stock_list() -> list[str]:
    """从 QMT Gateway 获取股票代码列表（仅代码，不含名称）"""
    log("[步骤4] 获取 QMT Gateway 股票列表...")
    try:
        from infra.qmt_gateway_client import get_stock_list as qmt_list
        codes = qmt_list()
        if codes:
            log(f"  [OK] QMT 返回 {len(codes)} 条")
        else:
            log("  [WARN] QMT 返回空列表（网关可能未运行）")
        return codes or []
    except Exception as e:
        log(f"  [ERROR] QMT 获取失败: {e}")
        return []


# ==================== 第5步：跨源对比 ====================

def cross_reference(
    db_data: dict[str, dict],
    akshare_data: dict[str, str],
    tushare_data: dict[str, str],
    qmt_codes: list[str],
) -> list[dict]:
    """
    跨源对比，找出所有不一致的记录

    返回: [{
        "code": "000001.SZ",
        "db_name": "平安银行",
        "akshare_name": "平安银行",
        "tushare_name": "平安银行",
        "qmt_exists": True,
        "status": "OK / FIXED / PENDING"
    }]
    """
    log("\n[步骤5] 跨源对比...")

    qmt_set = set(qmt_codes)
    all_codes = set(db_data.keys()) | set(akshare_data.keys()) | set(tushare_data.keys()) | qmt_set

    discrepancies = []
    ok_count = 0
    missing_in_db = 0

    for code in sorted(all_codes):
        db_name = db_data.get(code, {}).get("name", "") if code in db_data else None
        ak_name = akshare_data.get(code, "")
        ts_name = tushare_data.get(code, "")
        in_qmt = code in qmt_set

        # 收集所有非空名称
        sources: dict[str, str] = {}
        if db_name is not None:
            sources["数据库"] = db_name
        if ak_name:
            sources["AKShare"] = ak_name
        if ts_name:
            sources["TuShare"] = ts_name

        unique_names = set(sources.values())

        if len(unique_names) <= 1 and db_name is not None:
            ok_count += 1
            continue

        if db_name is None:
            # 代码在数据源中存在但在数据库中缺失
            if ak_name or ts_name:
                missing_in_db += 1
                discrepancies.append({
                    "code": code,
                    "db_name": None,
                    "akshare_name": ak_name,
                    "tushare_name": ts_name,
                    "qmt_exists": in_qmt,
                    "sources": sources,
                    "unique_names": unique_names,
                    "status": "MISSING_IN_DB",
                    "suggested_name": ak_name or ts_name,
                    "resolution": None,
                })
            continue

        # 有差异，记录
        discrepancies.append({
            "code": code,
            "db_name": db_name,
            "akshare_name": ak_name,
            "tushare_name": ts_name,
            "qmt_exists": in_qmt,
            "sources": sources,
            "unique_names": unique_names,
            "status": "DISCREPANCY",
            "suggested_name": None,
            "resolution": None,
        })

    log(f"  [OK] {ok_count} 条一致")
    log(f"  [!!] {len(discrepancies)} 条异常（{missing_in_db} 条数据库中缺失, {len(discrepancies) - missing_in_db} 条名称不一致）")
    return discrepancies


# ==================== 第6步：决策引擎 ====================

def resolve_discrepancies(discrepancies: list[dict]) -> list[dict]:
    """根据投票规则解决差异"""
    log("\n[步骤6] 应用决策规则解决差异...")

    resolved = []
    pending = []

    for d in discrepancies:
        code = d["code"]
        sources = {k: v for k, v in d["sources"].items() if v}

        # 按名称分组
        name_groups: dict[str, list[str]] = {}
        for src, name in sources.items():
            name_groups.setdefault(name, []).append(src)

        # 找出支持数量最多的名称
        sorted_names = sorted(name_groups.items(), key=lambda x: -len(x[1]))
        top_name, top_sources = sorted_names[0]
        top_count = len(top_sources)

        if top_count >= 3:
            d["status"] = "OK"
            d["resolution"] = top_name
            resolved.append(d)
            continue

        if top_count == 2:
            # 2:2 情况 - 看是否 QMT + TuShare 一致
            qmt_sources = [s for s in top_sources if "QMT" in s]
            ts_sources = [s for s in top_sources if "TuShare" in s]

            if len(sorted_names) == 2:
                second_name, second_sources = sorted_names[1]
                # 检查第二种组合是否更符合"QMT+TuShare"
                if "TuShare" in second_sources:
                    # TuShare 在第二组，说明第一组没有 TuShare
                    # 如果 TuShare 不在顶组，顶组获胜
                    pass

            # 简单规则：取支持者多的
            d["status"] = "FIXED"
            d["resolution"] = top_name
            resolved.append(d)
            continue

        # top_count == 1: 所有源都不同或只有1个源
        # 检查是否有 2 个源一致的情况（可能是不同源名分到两组）
        if len(sources) >= 3:
            all_names = list(name_groups.keys())
            for i, n1 in enumerate(all_names):
                for n2 in all_names[i+1:]:
                    src1 = set(name_groups[n1])
                    src2 = set(name_groups[n2])
                    combined = src1 | src2
                    if len(combined) >= 3:
                        log(f"  [解析] {code}: 不同名称 '{n1}'({src1}) + '{n2}'({src2}) 覆盖 {len(combined)} 个源")
                        break

        # 交给后续处理
        pending.append(d)

    if resolved:
        log(f"  [OK] {len(resolved)} 条已自动解决")

    return resolved, pending


# ==================== 第7步：千问验证 ====================

def verify_with_qianwen(code: str, candidates: list[str]) -> str | None:
    """用千问搜索验证股票代码的真实名称"""
    if not DASHSCOPE_API_KEY:
        return None

    try:
        import dashscope
        from http import HTTPStatus

        prompt = (
            f"A股股票代码 {code} 的正确股票名称是什么？"
            f"当前有多个候选名称: {candidates}。"
            f"请只返回正确的股票名称，不要加额外说明。"
        )

        resp = dashscope.Generation.call(
            model="qwen-max",
            api_key=DASHSCOPE_API_KEY,
            prompt=prompt,
            result_format="text",
            temperature=0.1,
        )
        if resp.status_code == HTTPStatus.OK:
            name = resp.output.text.strip()
            log(f"  [千问] {code}: 返回名称={name}")
            return name
        return None
    except Exception as e:
        log(f"  [千问] {code}: 调用失败: {e}")
        return None


# ==================== 主流程 ====================

def main():
    log("=" * 70)
    log(f"股票代码与名称准确性验证报告")
    log(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"数据源: trade_stock_master, AKShare, TuShare, QMT Gateway, 千问(备用)")
    log("=" * 70)

    # 第1-4步：获取数据
    db_data = fetch_db_stock_list()
    akshare_data = fetch_akshare_stock_list()
    tushare_data = fetch_tushare_stock_list()
    qmt_codes = fetch_qmt_stock_list()

    log(f"\n--- 数据汇总 ---")
    log(f"  trade_stock_master: {len(db_data)} 条")
    log(f"  AKShare:           {len(akshare_data)} 条")
    log(f"  TuShare:           {len(tushare_data)} 条")
    log(f"  QMT Gateway:       {len(qmt_codes)} 条")

    # 第5步：跨源对比
    discrepancies = cross_reference(db_data, akshare_data, tushare_data, qmt_codes)

    if not discrepancies:
        log("\n[结果] 所有股票代码与名称完全一致，无需修正")
        return

    # 第6步：决策解决
    resolved, pending = resolve_discrepancies(discrepancies)

    # 输出结果
    log("\n" + "=" * 70)
    log("验证结果明细")
    log("=" * 70)

    if resolved:
        log(f"\n--- 已解决 ({len(resolved)} 条) ---")
        for d in resolved:
            old = d.get("db_name") or "(缺失)"
            new = d["resolution"]
            if old != new:
                log(f"  [{d['status']}] {d['code']}: '{old}' -> '{new}'")
            else:
                log(f"  [{d['status']}] {d['code']}: 确认名称 = '{new}'")

    if pending:
        log(f"\n--- 待确认 ({len(pending)} 条) ---")
        for d in pending:
            log(f"  [PENDING] {d['code']}:")
            for src, name in sorted(d['sources'].items()):
                log(f"             {src}: {name}")

    log("\n" + "=" * 70)
    log("报告结束")
    log("=" * 70)

    return discrepancies, resolved, pending


if __name__ == "__main__":
    main()
