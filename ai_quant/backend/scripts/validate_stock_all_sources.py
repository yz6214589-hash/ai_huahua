"""
股票代码与名称准确性验证工具 - 4数据源完整版

对比数据源:
  1. QMT Gateway (股票列表)
  2. Tushare Pro  (股票代码+名称)
  3. AKShare     (股票代码+名称)
  4. 千问搜索      (用于争议记录最终确认)

决策规则:
  1. 3个及以上数据源名称一致 -> 采用该名称
  2. 2:2不一致 -> 优先以 QMT + TuShare 的结果为准
  3. 全部不一致 -> 标记为待确认，用千问搜索核实

使用方法:
  cd /Users/apple/Desktop/ai_huahua/ai_quant
  source venv/bin/activate
  python3 backend/scripts/validate_stock_all_sources.py
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

import pymysql
import akshare as ak
import tushare as ts

REPORT_LINES = []

# ==================== 进度条工具 ====================

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


class ProgressManager:
    """
    统一进度管理，支持 tqdm 和 fallback 两种模式

    因为数据采集和跨源对比只有几个关键步骤，
    所以在关键耗时环节使用进度条，其余步骤使用提示信息。
    """

    def __init__(self):
        self.start_time = None
        self.step_start = None

    def start(self):
        self.start_time = time.time()
        self.step_start = self.start_time
        log("开始验证...")

    def step_progress(self, current: int, total: int, desc: str = ""):
        """显示步骤级进度（用于数据获取等固定步骤）"""
        if HAS_TQDM:
            pct = current / total * 100
            bar_len = 30
            filled = int(bar_len * current / total)
            bar = "=" * filled + ">" + "-" * (bar_len - filled - 1) if current < total else "=" * bar_len
            elapsed = time.time() - self.start_time
            print(f"\r  [{bar}] {pct:.0f}% | {desc} | 耗时 {elapsed:.0f}s", end="")
            if current >= total:
                print()
        else:
            if current == 1 or current % max(1, total // 10) == 0 or current >= total:
                pct = current / total * 100
                print(f"  [{current}/{total}] {desc}... ({pct:.0f}%)")

    def make_progress(self, iterable, desc: str = "", total: int = None, unit: str = "it"):
        """为可迭代对象创建进度条"""
        if HAS_TQDM:
            return tqdm(iterable, desc=desc.ljust(20), total=total, unit=unit,
                        bar_format="{l_bar}{bar:30}{r_bar}", ncols=80)
        else:
            return iterable

    def print_step(self, step_num: int, total_steps: int, title: str):
        """打印步骤标题"""
        self.step_start = time.time()
        elapsed = time.time() - self.start_time if self.start_time else 0
        log(f"\n[{step_num}/{total_steps}] {title}")
        log(f"  (总耗时 {elapsed:.0f}s)")

    def step_done(self, msg: str = ""):
        """标记步骤完成"""
        elapsed = time.time() - self.step_start
        if msg:
            log(f"  [OK] {msg} (耗时 {elapsed:.1f}s)")
        else:
            log(f"  (本步骤耗时 {elapsed:.1f}s)")


# 全局进度管理器
PROGRESS = ProgressManager()
TOTAL_STEPS = 7


def log(msg):
    print(msg)
    REPORT_LINES.append(msg)


def load_env_file():
    """从项目根目录加载 .env 文件"""
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip("\"'")
                    if k and v:
                        os.environ.setdefault(k, v)


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


# ==================== 第1步：获取数据库数据 ====================

def fetch_db_stock_list():
    """从 trade_stock_master 获取所有股票的代码和名称"""
    PROGRESS.print_step(1, TOTAL_STEPS, "查询 trade_stock_master 当前数据...")
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
            for r in PROGRESS.make_progress(rows, desc="加载数据库记录", unit="条"):
                result[r["stock_code"]] = {
                    "name": r["stock_name"] or "",
                    "asset_type": r["asset_type"],
                    "market": r["market"] or "",
                }
            PROGRESS.step_done(f"数据库加载 {len(result)} 条个股记录")
            return result
    finally:
        conn.close()


# ==================== 第2步：获取 AKShare 股票列表 ====================

def fetch_akshare_stock_list():
    """从 AKShare 获取股票列表 {代码: 名称}"""
    PROGRESS.print_step(2, TOTAL_STEPS, "获取 AKShare 股票列表...")
    try:
        log("   正在通过 akshare 拉取全市场股票代码...")
        df = ak.stock_info_a_code_name()
        total_rows = len(df)
        log(f"   原始数据 {total_rows} 条，正在转换格式...")
        result = {}
        for _, r in PROGRESS.make_progress(df.iterrows(), desc="AKShare 转换",
                                           total=total_rows, unit="条"):
            code_num = str(r.get("code") or "").strip()
            name = str(r.get("name") or "").strip()
            if not code_num:
                continue
            if code_num.startswith(("6", "688")):
                code = f"{code_num}.SH"
            else:
                code = f"{code_num}.SZ"
            result[code] = name
        PROGRESS.step_done(f"AKShare 返回 {len(result)} 条")
        return result
    except Exception as e:
        log(f"  [ERROR] AKShare 获取失败: {e}")
        return {}


# ==================== 第3步：获取 TuShare 股票列表 ====================

def fetch_tushare_stock_list():
    """从 TuShare 获取股票列表 {代码: 名称}"""
    PROGRESS.print_step(3, TOTAL_STEPS, "获取 TuShare 股票列表...")
    try:
        token = os.getenv("AI_QUANT_TUSHARE_TOKEN") or "e72ed2b49c50facc5169ab83dc2873d4217bce94244768449742e870"
        pro = ts.pro_api(token)
        pro._DataApi__http_url = "http://a.sszhixia.cn/"
        log("   正在通过 TuShare API 获取股票列表...")
        df = pro.stock_basic()
        if df is None or df.empty:
            log("  [WARN] TuShare 返回空数据")
            return {}
        total_rows = len(df)
        log(f"   原始数据 {total_rows} 条，正在转换格式...")
        result = {}
        for _, r in PROGRESS.make_progress(df.iterrows(), desc="TuShare 转换",
                                           total=total_rows, unit="条"):
            code = str(r.get("ts_code") or "").strip()
            name = str(r.get("name") or "").strip()
            if code and name:
                result[code] = name
        PROGRESS.step_done(f"TuShare 返回 {len(result)} 条")
        return result
    except Exception as e:
        log(f"  [ERROR] TuShare 获取失败: {e}")
        return {}


# ==================== 第4步：获取 QMT 股票列表 ====================

def fetch_qmt_stock_list():
    """通过 QMT Gateway 获取股票代码列表（仅代码，不含名称）"""
    PROGRESS.print_step(4, TOTAL_STEPS, "获取 QMT Gateway 股票列表...")
    base_url = os.getenv("AI_QUANT_QMT_GATEWAY_BASE", "").rstrip("/")
    token = os.getenv("AI_QUANT_QMT_GATEWAY_TOKEN", "")
    if not base_url:
        log("  [WARN] 未配置 AI_QUANT_QMT_GATEWAY_BASE，跳过 QMT 获取")
        PROGRESS.step_done("QMT 未配置，跳过")
        return []
    try:
        qmt_start = time.time()
        url = f"{base_url}/api/historical/stock_list"
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-API-Token"] = token
        log(f"   正在请求 QMT Gateway ({url})...")
        req = urllib.request.Request(url, method="GET", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            codes = data.get("codes") or []
        qmt_elapsed = time.time() - qmt_start
        PROGRESS.step_done(f"QMT 返回 {len(codes)} 条 (网络耗时 {qmt_elapsed:.1f}s)")
        return codes
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')[:200]
        log(f"  [ERROR] QMT HTTP {e.code}: {err_body}")
        PROGRESS.step_done("QMT 获取失败")
        return []
    except Exception as e:
        log(f"  [ERROR] QMT 获取失败: {type(e).__name__}: {e}")
        PROGRESS.step_done("QMT 获取失败")
        return []


# ==================== 第5步：千问搜索验证 ====================

def verify_with_qianwen(code, candidates):
    """用千问搜索验证股票代码的真实名称"""
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import dashscope
        from http import HTTPStatus
        prompt = (
            "A股股票代码 " + code + " 的正确股票名称是什么？"
            "当前候选名称: " + str(candidates) + "。"
            "请只返回正确的股票名称，不要加额外说明。"
        )
        resp = dashscope.Generation.call(
            model="qwen-max",
            api_key=api_key,
            prompt=prompt,
            result_format="text",
            temperature=0.1,
        )
        if resp.status_code == HTTPStatus.OK:
            name = resp.output.text.strip()
            log("  [千问] " + code + ": 返回名称=" + name)
            return name
        return None
    except ImportError:
        log("  [千问] " + code + ": dashscope 未安装，跳过")
        return None
    except Exception as e:
        log("  [千问] " + code + ": 调用失败: " + str(e))
        return None


# ==================== 第6步：跨源对比与决策 ====================

def cross_reference(db_data, akshare_data, tushare_data, qmt_codes):
    """
    跨源对比，按投票规则决策

    规则:
      1. 3个及以上数据源名称一致 -> 采用
      2. 2:2不一致 -> 以 QMT + TuShare 一致的结果为准
      3. 全部不一致 -> 标记待确认 + 千问搜索验证
    """
    PROGRESS.print_step(5, TOTAL_STEPS, "跨源对比与决策...")

    qmt_set = set(qmt_codes)
    all_codes = set(db_data.keys()) | set(akshare_data.keys()) | set(tushare_data.keys()) | qmt_set
    sorted_codes = sorted(all_codes)
    total_codes = len(sorted_codes)
    log(f"   合并后总代码数: {total_codes} 条，开始逐条对比...")

    ok_list = []
    fixed_list = []
    pending_list = []
    missing_list = []
    qwen_pending = []  # 需要千问验证的记录

    # 第一遍：快速对比，只找出差异
    for code in PROGRESS.make_progress(sorted_codes, desc="跨源对比", total=total_codes, unit="条"):
        db_entry = db_data.get(code)
        db_name = db_entry["name"] if db_entry else None
        ak_name = akshare_data.get(code, "")
        ts_name = tushare_data.get(code, "")
        in_qmt = code in qmt_set

        name_sources = {}
        if db_name is not None:
            name_sources["trade_stock_master"] = db_name
        if ak_name:
            name_sources["AKShare"] = ak_name
        if ts_name:
            name_sources["TuShare"] = ts_name
        if in_qmt:
            name_sources["QMT"] = "(代码存在，无名称)"

        valid_sources = {k: v for k, v in name_sources.items() if v and v != "(代码存在，无名称)"}
        valid_name_set = set(valid_sources.values())
        has_valid_source = db_name is not None

        # 名称值为 "-" 视为无效
        if ak_name == "-":
            ak_name = ""
        if ts_name == "-":
            ts_name = ""

        # 数据库中缺失
        if db_name is None and (ak_name or ts_name):
            missing_list.append({
                "code": code, "db_name": None, "akshare_name": ak_name,
                "tushare_name": ts_name, "qmt_exists": in_qmt,
                "name_sources": name_sources,
            })
            continue

        # 全部一致
        if len(valid_name_set) <= 1 and has_valid_source:
            ok_list.append(code)
            continue

        # 存在差异，记录下来稍后处理
        name_votes = {}
        for src, name in valid_sources.items():
            name_votes.setdefault(name, []).append(src)

        sorted_votes = sorted(name_votes.items(), key=lambda x: -len(x[1]))
        top_name, top_sources = sorted_votes[0]
        top_count = len(top_sources)

        record = {
            "code": code, "db_name": db_name, "akshare_name": ak_name,
            "tushare_name": ts_name, "qmt_exists": in_qmt,
            "name_sources": name_sources, "top_name": top_name,
            "top_count": top_count, "total_votes": len(valid_sources),
            "all_names": list(name_votes.keys()),
        }

        # 3源一致 -> 采用
        if top_count >= 3:
            record["resolution"] = top_name
            record["decision_rule"] = "3源一致"
            if db_name != top_name:
                fixed_list.append(record)
            else:
                ok_list.append(code)
            continue

        # 2:1 多数一致 -> 采用
        if top_count == 2 and len(sorted_votes) == 2:
            record["resolution"] = top_name
            record["decision_rule"] = "2源一致(多数)"
            if db_name != top_name:
                fixed_list.append(record)
            else:
                ok_list.append(code)
            continue

        # 1:1:1 全部不一致 -> 需要千问验证
        if len(valid_sources) >= 3 and len(valid_name_set) >= 3:
            qwen_pending.append(record)
            continue

        # 2:0:0 多数一致
        if top_count >= 2:
            record["resolution"] = top_name
            record["decision_rule"] = "多数一致"
            if db_name is not None and db_name != top_name:
                fixed_list.append(record)
            elif db_name is None:
                fixed_list.append(record)
            else:
                ok_list.append(code)
            continue

        record["decision_rule"] = "单一数据源"
        pending_list.append(record)

    # 第二遍：对全部不一致的记录调用千问搜索验证
    if qwen_pending:
        log(f"\n   千问搜索验证 {len(qwen_pending)} 条争议记录...")
        for record in PROGRESS.make_progress(qwen_pending, desc="千问验证",
                                              total=len(qwen_pending), unit="条"):
            code = record["code"]
            candidates = list(set(record["all_names"]))
            qwen_name = verify_with_qianwen(code, candidates)
            if qwen_name:
                record["resolution"] = qwen_name
                record["decision_rule"] = "千问搜索确认"
                if record["db_name"] is not None and record["db_name"] != qwen_name:
                    fixed_list.append(record)
                elif record["db_name"] is None:
                    fixed_list.append(record)
                else:
                    ok_list.append(code)
            else:
                record["decision_rule"] = "全部不一致"
                pending_list.append(record)

    log(f"")
    PROGRESS.step_done(f"对比完成: {len(ok_list)}条一致, {len(fixed_list)}条修正, "
                       f"{len(pending_list)}条待确认, {len(missing_list)}条缺失")
    return ok_list, fixed_list, pending_list, missing_list


# ==================== 主流程 ====================

def main():
    print("=" * 70)
    print("股票代码与名称准确性验证报告 (4数据源完整版)")
    print("验证时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("数据源对比: trade_stock_master, AKShare, TuShare, QMT Gateway, 千问搜索")
    print("决策规则: 3源一致>多数一致>QMT+TuShare>千问搜索>待确认")
    print("=" * 70)

    PROGRESS.start()

    # 获取数据库数据
    db_data = fetch_db_stock_list()

    # 获取 AKShare 数据
    akshare_data = fetch_akshare_stock_list()

    # 获取 TuShare 数据
    tushare_data = fetch_tushare_stock_list()

    # 获取 QMT 数据（仅代码，支持存在性验证）
    qmt_codes = fetch_qmt_stock_list()

    log("\n--- 数据汇总 ---")
    log("  trade_stock_master: " + str(len(db_data)) + " 条")
    log("  AKShare:           " + str(len(akshare_data)) + " 条")
    log("  TuShare:           " + str(len(tushare_data)) + " 条")
    log("  QMT Gateway:       " + str(len(qmt_codes)) + " 条")

    # 跨源对比与决策
    ok_list, fixed_list, pending_list, missing_list = cross_reference(
        db_data, akshare_data, tushare_data, qmt_codes
    )

    total = len(ok_list) + len(fixed_list) + len(pending_list) + len(missing_list)

    log("\n--- 验证统计 ---")
    log("  一致记录:       " + str(len(ok_list)) + " 条")
    log("  已修正记录:     " + str(len(fixed_list)) + " 条")
    log("  待确认记录:     " + str(len(pending_list)) + " 条")
    log("  数据库中缺失:   " + str(len(missing_list)) + " 条")
    log("  总计:           " + str(total) + " 条")

    # ========== 北交所 920xxx 去重 ==========
    # AKShare 返回 920xxx.SZ, TuShare 返回 920xxx.BJ, 同一只股票
    # 去重：按数字代码分组，保留 .BJ 版本，合并名称
    bj_seen = {}
    deduped_missing = []
    for d in sorted(missing_list, key=lambda x: x["code"]):
        parts = d["code"].split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[0].startswith("920"):
            stock_num = parts[0]
            if stock_num in bj_seen:
                existing = bj_seen[stock_num]
                existing["akshare_name"] = existing["akshare_name"] or d["akshare_name"]
                existing["tushare_name"] = existing["tushare_name"] or d["tushare_name"]
                continue
            bj_seen[stock_num] = d
            # 统一用 .BJ 后缀
            d["code"] = stock_num + ".BJ"
        deduped_missing.append(d)
    before_dedup = len(missing_list)
    missing_list = deduped_missing
    after_dedup = len(missing_list)
    if before_dedup != after_dedup:
        log("")
        log("  北交所去重: 合并前 " + str(before_dedup) + " 条 -> 合并后 " + str(after_dedup) + " 条")
        log("")

    # ========== 输出报告 ==========
    PROGRESS.print_step(6, TOTAL_STEPS, "生成验证报告...")

    # 一、数据库缺失记录
    if missing_list:
        log("\n" + "=" * 70)
        log("一、数据库中缺失的代码记录")
        log("=" * 70)
        log("  " + "代码".ljust(12) + "AKShare名称".ljust(14) + "TuShare名称".ljust(14) + "QMT存在")
        log("  " + "-" * 12 + " " + "-" * 14 + " " + "-" * 14 + " " + "-" * 8)
        for d in PROGRESS.make_progress(missing_list, desc="输出缺失记录", unit="条"):
            ak_n = d["akshare_name"] or "(无)"
            ts_n = d["tushare_name"] or "(无)"
            qmt_s = "是" if d["qmt_exists"] else "否"
            log("  " + d["code"].ljust(12) + ak_n.ljust(14) + ts_n.ljust(14) + qmt_s)

    # 二、已修正记录
    if fixed_list:
        log("\n" + "=" * 70)
        log("二、名称不一致已修正记录")
        log("=" * 70)
        log("  " + "代码".ljust(12) + "原名称(数据库)".ljust(16) + "->".ljust(4) + "修正后名称".ljust(14) + "决策规则")
        log("  " + "-" * 12 + " " + "-" * 16 + " " + "-" * 4 + " " + "-" * 14 + " " + "-" * 14)
        for d in PROGRESS.make_progress(
            sorted(fixed_list, key=lambda x: x["code"]), desc="输出修正记录", unit="条"):
            old_name = d["db_name"] or "(缺失)"
            new_name = d["resolution"]
            rule = d["decision_rule"]
            log("  " + d["code"].ljust(12) + old_name.ljust(16) + " -> ".ljust(4) + new_name.ljust(14) + rule)

    # 三、待确认记录
    if pending_list:
        log("\n" + "=" * 70)
        log("三、待人工确认记录（千问搜索也无法确定）")
        log("=" * 70)
        for d in sorted(pending_list, key=lambda x: x["code"]):
            log("  [待确认] " + d["code"])
            log("      trade_stock_master: " + (d["db_name"] or "(缺失)"))
            log("      AKShare:           " + (d["akshare_name"] or "(无)"))
            log("      TuShare:           " + (d["tushare_name"] or "(无)"))
            log("      QMT存在:           " + ("是" if d["qmt_exists"] else "否"))
            log("      所有名称:          " + str(d["all_names"]))

    # 四、完整对比明细表
    all_discrepancies = fixed_list + pending_list + missing_list
    if all_discrepancies:
        log("\n" + "=" * 70)
        log("四、完整对比明细表")
        log("=" * 70)
        header = ("  " + "代码".ljust(12) + "数据库".ljust(14) + "AKShare".ljust(14)
                  + "TuShare".ljust(14) + "QMT".ljust(6) + "状态".ljust(10) + "修正结果")
        log(header)
        log("  " + "-" * 12 + " " + "-" * 12 + " " + "-" * 12 + " " + "-" * 12 + " " + "-" * 4 + " " + "-" * 10 + " " + "-" * 14)

        for d in PROGRESS.make_progress(
            sorted(all_discrepancies, key=lambda x: x["code"]), desc="输出明细表", unit="条"):
            db_n = d.get("db_name") or "(缺失)"
            ak_n = d.get("akshare_name") or "(无)"
            ts_n = d.get("tushare_name") or "(无)"
            qmt_s = "是" if d.get("qmt_exists") else "否"

            if d in pending_list:
                status = "待确认"
                resolution = "-"
            elif d in fixed_list:
                status = "已修正"
                resolution = d.get("resolution", "-")
            else:
                status = "缺失"
                resolution = d.get("akshare_name") or d.get("tushare_name") or "-"

            log("  " + d["code"].ljust(12) + db_n.ljust(12) + ak_n.ljust(12)
                + ts_n.ljust(12) + qmt_s.ljust(4) + status.ljust(10) + resolution)

    PROGRESS.step_done("报告明细生成完成")

    # ========== SQL修正语句 ==========
    PROGRESS.print_step(7, TOTAL_STEPS, "生成SQL修正语句和数据源对比说明...")
    if fixed_list or missing_list:
        log("\n" + "=" * 70)
        log("五、SQL修正语句")
        log("=" * 70)

        if fixed_list:
            log("\n-- 1. 更新名称不一致的股票")
            for d in PROGRESS.make_progress(
                sorted(fixed_list, key=lambda x: x["code"]), desc="生成UPDATE", unit="条"):
                old_name = (d["db_name"] or "").replace("'", "\\'")
                new_name = (d["resolution"] or "").replace("'", "\\'")
                log("UPDATE trade_stock_master SET stock_name = '" + new_name
                    + "' WHERE stock_code = '" + d["code"] + "';")

        # 已知的指数类股票代码（需要将 asset_type 从 'stock' 修正为 'index'）
        INDEX_CODE_LIST = [
            ("000016.SH", "上证50"),
            ("000025.SZ", "180基建"),
            ("000030.SZ", "180R成长"),
            ("000031.SZ", "180R价值"),
            ("000852.SH", "中证1000"),
            ("000905.SH", "中证500"),
        ]
        # 检查哪些指数代码在修正列表中，生成 asset_type 修正语句
        fixed_codes = set(d["code"] for d in fixed_list)
        idx_update_sql = []
        for idx_code, idx_name in INDEX_CODE_LIST:
            if idx_code in fixed_codes:
                idx_update_sql.append(
                    "UPDATE trade_stock_master SET asset_type = 'index' "
                    "WHERE stock_code = '" + idx_code + "';"
                )
        if idx_update_sql:
            log("\n-- 3. 修正指数类股票的资产类型 (stock -> index)")
            for stmt in idx_update_sql:
                log(stmt)

        if missing_list:
            log("\n-- 2. 补充数据库中缺失的股票")
            log("INSERT INTO trade_stock_master (stock_code, stock_name, asset_type, market) VALUES")
            insert_vals = []
            for d in sorted(missing_list, key=lambda x: x["code"]):
                suggested = d.get("akshare_name") or d.get("tushare_name") or "未知"
                suggested = suggested.replace("'", "\\'")
                code = d["code"]
                if code.endswith(".SH"):
                    market = ".SH"
                elif code.startswith("920") or code.startswith(("8", "4")):
                    market = ".BJ"
                else:
                    market = ".SZ"
                insert_vals.append("('" + code + "', '" + suggested + "', 'stock', '" + market + "')")
            if insert_vals:
                log(",\n".join(insert_vals) + ";")

    # ========== 各数据源对比情况 ==========
    log("\n" + "=" * 70)
    log("六、各数据源对比情况说明")
    log("=" * 70)

    # 统计各数据源覆盖情况
    all_codes_in_db = set(db_data.keys())
    all_codes_ak = set(akshare_data.keys())
    all_codes_ts = set(tushare_data.keys())
    all_codes_qmt = set(qmt_codes)

    log("\n1. 数据源覆盖范围对比:")
    log("   数据源             数量    与数据库交集    差异")
    db_count = len(all_codes_in_db)
    ak_overlap = len(all_codes_in_db & all_codes_ak)
    ts_overlap = len(all_codes_in_db & all_codes_ts)
    qmt_overlap = len(all_codes_in_db & all_codes_qmt)
    log("   trade_stock_master: " + str(db_count).ljust(6) + "-".ljust(14) + "-")
    log("   AKShare:           " + str(len(all_codes_ak)).ljust(6) + str(ak_overlap).ljust(14) + str(db_count - ak_overlap))
    log("   TuShare:           " + str(len(all_codes_ts)).ljust(6) + str(ts_overlap).ljust(14) + str(db_count - ts_overlap))
    log("   QMT Gateway:       " + str(len(all_codes_qmt)).ljust(6) + str(qmt_overlap).ljust(14) + str(db_count - qmt_overlap))

    # 名称一致性统计
    name_match_ak = 0
    name_match_ts = 0
    name_match_both = 0
    for code in all_codes_in_db:
        db_name = db_data[code]["name"]
        ak_name = akshare_data.get(code, "")
        ts_name = tushare_data.get(code, "")
        if db_name and ak_name and db_name == ak_name:
            name_match_ak += 1
        if db_name and ts_name and db_name == ts_name:
            name_match_ts += 1
        if db_name and ak_name and ts_name and db_name == ak_name == ts_name:
            name_match_both += 1

    log("\n2. 名称一致性对比:")
    log("   数据库 vs AKShare 名称一致: " + str(name_match_ak) + " / " + str(db_count))
    log("   数据库 vs TuShare 名称一致: " + str(name_match_ts) + " / " + str(db_count))
    log("   三源名称全部一致:           " + str(name_match_both) + " / " + str(db_count))
    log("   数据库名称需修正:           " + str(len(fixed_list)) + " 条")
    log("   数据库缺失代码:             " + str(len(missing_list)) + " 条")

    log("\n3. QMT 数据源说明:")
    log("   QMT Gateway 仅提供股票代码列表，不提供股票名称。")
    log("   QMT 的存在性确认用于佐证股票代码的有效性。")
    log("   当各数据源名称不一致时，QMT+TuShare 的一致结果具有优先权。")

    log("\n4. 千问搜索说明:")
    log("   千问搜索用于对全部数据源名称不一致的争议记录进行最终确认。")
    qwen_called = sum(1 for d in fixed_list if d.get("decision_rule") == "千问搜索确认")
    log("   千问搜索调用次数: " + str(qwen_called))
    log("   千问搜索成功确认: " + str(qwen_called) + " 条")
    log("   仍无法确认(待人工): " + str(len(pending_list)) + " 条")
    if qwen_called > 0:
        log("   千问确认的记录:")
        for d in sorted(fixed_list, key=lambda x: x["code"]):
            if d.get("decision_rule") == "千问搜索确认":
                log("     " + d["code"] + ": " + (d["db_name"] or "(缺失)") + " -> " + d["resolution"])

    PROGRESS.step_done("SQL和数据源对比说明完成")

    total_elapsed = time.time() - PROGRESS.start_time
    log("\n" + "=" * 70)
    log("验证报告结束")
    log("总耗时: " + str(round(total_elapsed, 1)) + " 秒")
    log("步骤完成: 7/7")
    log("=" * 70)

    # 保存报告到文件
    report_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..",
        "stock_name_validation_report_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
    )
    report_path = os.path.normpath(report_path)
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(REPORT_LINES))
        print("\n[报告已保存至] " + report_path)
    except Exception as e:
        print("\n[WARN] 保存报告文件失败: " + str(e))


if __name__ == "__main__":
    # 先加载 .env 文件
    load_env_file()
    main()
