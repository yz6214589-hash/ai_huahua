"""
股票代码与名称准确性验证工具 - 独立版
对比数据源: 数据库(trade_stock_master), AKShare, TuShare
使用方法:
  cd /Users/apple/Desktop/ai_huahua/ai_quant
  source venv/bin/activate
  WUCAI_SQL_HOST="bj-cdb-6zjqetya.sql.tencentcdb.com" WUCAI_SQL_PORT="25341" WUCAI_SQL_USERNAME="root" WUCAI_SQL_PASSWORD="huahua1688" WUCAI_SQL_DB="huahua_trade" python3 backend/scripts/validate_stock_standalone.py
"""
import os
import sys
from datetime import datetime
import pymysql
import akshare as ak
import tushare as ts

REPORT_LINES = []

def log(msg):
    print(msg)
    REPORT_LINES.append(msg)

def load_mysql_config():
    host = os.getenv("WUCAI_SQL_HOST") or os.getenv("DB_HOST") or "127.0.0.1"
    raw_port = os.getenv("WUCAI_SQL_PORT") or os.getenv("DB_PORT") or "3306"
    try:
        port = int(str(raw_port).strip())
    except Exception:
        port = 3306
    user = os.getenv("WUCAI_SQL_USERNAME") or os.getenv("DB_USER") or "root"
    password = os.getenv("WUCAI_SQL_PASSWORD") or os.getenv("DB_PASSWORD") or ""
    database = os.getenv("WUCAI_SQL_DB") or os.getenv("DB_NAME") or "huahua_trade"
    return {
        "host": str(host).strip() or "127.0.0.1",
        "port": port,
        "user": str(user).strip() or "root",
        "password": password,
        "database": str(database).strip() or "huahua_trade",
    }

def fetch_db_stock_list():
    """从 trade_stock_master 获取所有股票的代码和名称"""
    log("[步骤1] 查询 trade_stock_master 当前数据...")
    cfg = load_mysql_config()
    conn = pymysql.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"], database=cfg["database"],
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stock_code, stock_name, asset_type, market "
                "FROM trade_stock_master WHERE asset_type = 'stock' "
                "ORDER BY stock_code"
            )
            rows = cur.fetchall()
            result = {}
            for r in rows:
                result[r["stock_code"]] = {
                    "name": r["stock_name"] or "",
                    "asset_type": r["asset_type"],
                    "market": r["market"] or "",
                }
            log(f"  [OK] 数据库加载 {len(result)} 条个股记录")
            return result
    finally:
        conn.close()

def fetch_akshare_stock_list():
    """从 AKShare 获取股票列表 {代码: 名称}"""
    log("[步骤2] 获取 AKShare 股票列表...")
    try:
        df = ak.stock_info_a_code_name()
        result = {}
        for _, r in df.iterrows():
            code_num = str(r.get("code") or "").strip()
            name = str(r.get("name") or "").strip()
            if not code_num:
                continue
            if code_num.startswith(("6", "688")):
                code = f"{code_num}.SH"
            else:
                code = f"{code_num}.SZ"
            result[code] = name
        log(f"  [OK] AKShare 返回 {len(result)} 条")
        return result
    except Exception as e:
        log(f"  [ERROR] AKShare 获取失败: {e}")
        return {}

def fetch_tushare_stock_list():
    """从 TuShare 获取股票列表 {代码: 名称}"""
    log("[步骤3] 获取 TuShare 股票列表...")
    try:
        token = os.getenv("AI_QUANT_TUSHARE_TOKEN") or "e72ed2b49c50facc5169ab83dc2873d4217bce94244768449742e870"
        pro = ts.pro_api(token)
        pro._DataApi__http_url = "http://a.sszhixia.cn/"
        df = pro.stock_basic()
        if df is None or df.empty:
            log("  [WARN] TuShare 返回空数据")
            return {}
        result = {}
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

def cross_reference(db_data, akshare_data, tushare_data):
    """跨源对比，找出所有不一致的记录"""
    log("\n[步骤4] 跨源对比...")
    all_codes = set(db_data.keys()) | set(akshare_data.keys()) | set(tushare_data.keys())
    discrepancies = []
    ok_count = 0
    missing_in_db = 0

    for code in sorted(all_codes):
        db_entry = db_data.get(code)
        db_name = db_entry["name"] if db_entry else None
        ak_name = akshare_data.get(code, "")
        ts_name = tushare_data.get(code, "")

        sources = {}
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
            if ak_name or ts_name:
                missing_in_db += 1
                discrepancies.append({
                    "code": code,
                    "db_name": None,
                    "akshare_name": ak_name,
                    "tushare_name": ts_name,
                    "status": "MISSING_IN_DB",
                    "suggested_name": ak_name or ts_name,
                })
            continue

        discrepancies.append({
            "code": code,
            "db_name": db_name,
            "akshare_name": ak_name,
            "tushare_name": ts_name,
            "status": "DISCREPANCY",
        })

    log(f"  [OK] {ok_count} 条一致")
    log(f"  [!!] {len(discrepancies)} 条异常 "
        f"({missing_in_db} 条数据库中缺失, "
        f"{len(discrepancies) - missing_in_db} 条名称不一致)")
    return discrepancies

def main():
    log("=" * 70)
    log("股票代码与名称准确性验证报告")
    log(f"验证时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("数据源: trade_stock_master, AKShare, TuShare")
    log("=" * 70)

    db_data = fetch_db_stock_list()
    akshare_data = fetch_akshare_stock_list()
    tushare_data = fetch_tushare_stock_list()

    log(f"\n--- 数据汇总 ---")
    log(f"  trade_stock_master: {len(db_data)} 条")
    log(f"  AKShare:           {len(akshare_data)} 条")
    log(f"  TuShare:           {len(tushare_data)} 条")

    discrepancies = cross_reference(db_data, akshare_data, tushare_data)

    if not discrepancies:
        log("\n[结果] 所有股票代码与名称完全一致，无需修正")
        return

    log("\n" + "=" * 70)
    log("名称不一致记录明细")
    log("=" * 70)

    missing_items = [d for d in discrepancies if d["status"] == "MISSING_IN_DB"]
    conflict_items = [d for d in discrepancies if d["status"] == "DISCREPANCY"]

    if missing_items:
        log(f"\n--- 数据库中缺失的股票 ({len(missing_items)} 条) ---")
        log(f"  {'代码':<12} {'AKShare名称':<12} {'TuShare名称':<12}")
        log(f"  {'-'*12} {'-'*12} {'-'*12}")
        for d in missing_items:
            ak_n = d["akshare_name"] or "(无)"
            ts_n = d["tushare_name"] or "(无)"
            log(f"  {d['code']:<12} {ak_n:<12} {ts_n:<12}")

    if conflict_items:
        log(f"\n--- 名称不一致的记录 ({len(conflict_items)} 条) ---")
        log(f"  {'代码':<12} {'数据库名称':<12} {'AKShare名称':<12} {'TuShare名称':<12}")
        log(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*12}")
        for d in conflict_items:
            db_n = d["db_name"] or "(缺失)"
            ak_n = d["akshare_name"] or "(无)"
            ts_n = d["tushare_name"] or "(无)"
            log(f"  {d['code']:<12} {db_n:<12} {ak_n:<12} {ts_n:<12}")

    log("\n" + "=" * 70)
    log("建议修正方案")
    log("=" * 70)

    if missing_items:
        log(f"\n1. 数据库中缺失 {len(missing_items)} 支股票代码，建议:")
        log(f"   对于同时被 AKShare 和 TuShare 确认的代码，应补充到 trade_stock_master 表中")
        log(f"   INSERT INTO trade_stock_master (stock_code, stock_name, asset_type)")
        log(f"   VALUES")

    if conflict_items:
        log(f"\n2. 名称不一致 {len(conflict_items)} 条，决策规则:")
        log(f"   - 3个及以上数据源一致 -> 采用")
        log(f"   - 2:2不一致 -> AKShare + TuShare 优先于数据库")
        log(f"   - 全部不一致 -> 标记待人工确认")
        log(f"\n   建议执行 UPDATE 更新数据库名称:")
        log(f"   UPDATE trade_stock_master SET stock_name = '正确名称'")
        log(f"   WHERE stock_code = '代码';")

    log(f"\n3. 人工确认步骤:")
    log(f"   - 对标记为 MISSING_IN_DB 的代码，确认是否需要补充到数据库")
    log(f"   - 对标记为 DISCREPANCY 的代码，以 AKShare 和 TuShare 两个源同时一致的名称为准")
    log(f"   - 两个源仍不一致的，需通过官方渠道核实")

    log("\n" + "=" * 70)
    log("报告结束")
    log("=" * 70)

if __name__ == "__main__":
    main()
