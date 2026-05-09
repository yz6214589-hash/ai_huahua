from __future__ import annotations

import os
import queue
import threading
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from ai_quant_api.runtime.report_store import create_task, delete_task, get_task, list_tasks, now_iso, update_task
from ai_quant_api.services.charles.integration import search_stocks
from ai_quant_api.services.reports.rag import (
    build_faiss_index,
    get_rag_settings,
    ingest_pdfs,
    rag_query,
    rag_status,
    resolve_stock_name_by_code,
)


def _project_root() -> Path:
    """返回项目根目录路径（backend/ai_quant_api/api/ -> 项目根目录）。"""
    return Path(__file__).resolve().parents[3]


_REPORT_LOG_FILE = _project_root() / ".ai_quant" / "reports_worker.log"


def _report_log(*args, **kwargs) -> None:
    """
    统一日志输出函数，同时打印到 stdout 和写入 reports_worker.log 文件。
    每行日志自动追加时间戳前缀，便于追踪研报生成过程中的异常。
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = " ".join(str(a) for a in args)
    msg = f"[{ts}] {line}"
    print(msg, **kwargs)
    try:
        _REPORT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_REPORT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


router = APIRouter(prefix="/api/reports", tags=["reports"])

_TASK_QUEUE: queue.Queue[str] = queue.Queue()
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()
_DEFAULT_REPORT_TIMEOUT_SECONDS = 300


class ReportTaskCreateRequest(BaseModel):
    """创建研报任务的请求体。"""
    model: str
    stock_codes: list[str]
    use_rag: bool = True


def _parse_date(v: str) -> date | None:
    """将 YYYY-MM-DD 格式字符串解析为 date 对象，解析失败返回 None。"""
    s = (v or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _resolve_stock_names(stock_codes: list[str]) -> list[str]:
    """
    根据股票代码列表解析出对应的中文名称。
    优先从 RAG 服务获取名称（resolve_stock_name_by_code），若未命中则通过 search_stocks 查询。
    """
    names: list[str] = []
    for code in stock_codes:
        text = str(code or "").strip()
        if not text:
            continue
        rag_name = resolve_stock_name_by_code(text)
        if rag_name:
            names.append(rag_name)
            continue
        r = search_stocks(q=text, limit=1)
        items = r.get("items") if isinstance(r, dict) else None
        name = None
        if isinstance(items, list) and items:
            first = items[0] if isinstance(items[0], dict) else {}
            name = first.get("name")
        names.append(str(name or text))
    while len(names) < len(stock_codes):
        names.append(str(stock_codes[len(names)]))
    return names


class RagIngestRequest(BaseModel):
    """RAG 索引构建请求体。"""
    rebuild: bool = False
    limit: int | None = None


@router.get("/rag/status")
def reports_rag_status() -> dict[str, Any]:
    """查询当前 RAG 索引状态（索引目录、文件是否存在、文档数量等）。"""
    return rag_status()


@router.post("/rag/ingest")
def reports_rag_ingest(req: RagIngestRequest) -> dict[str, Any]:
    """
    触发 PDF 文档解析与 RAG FAISS 索引构建。
    - rebuild=True 时强制重建索引；rebuild=False 时增量追加。
    - limit 参数控制本次最多处理多少个 PDF。
    """
    ingest = ingest_pdfs(rebuild=bool(req.rebuild), limit=req.limit)
    built = build_faiss_index(rebuild=bool(req.rebuild))
    return {"ingest": ingest, "index": built}


@router.get("/rag/query")
def reports_rag_query(q: str = Query(default=""), stock: str = Query(default=""), k: int = Query(default=6)) -> dict[str, Any]:
    """
    向 RAG 索引发起语义检索，返回与查询最相关的 k 条文档片段。
    - q: 检索查询文本（如公司名、财报关键词）
    - stock: 限定只检索指定股票的文档
    - k: 返回结果数量上限
    """
    return rag_query(q=q, stock=stock, k=k)


def _case_root() -> Path:
    """CASE 智能研报生成脚本的根目录（已废弃，仅作占位保留）。"""
    return _project_root() / "CASE-智能研报生成"


def _dashscope_generate(*, model_name: str, api_key: str, system_prompt: str, user_prompt: str) -> str:
    """
    调用阿里云 DashScope API 生成文本内容。
    在独立后台线程中执行 HTTP 请求，支持通过 AI_QUANT_REPORT_LLM_TIMEOUT_SECONDS 配置超时时间（默认 90 秒）。
    返回 LLM 生成的文本字符串；若返回为空或请求失败则抛出异常。
    响应数据兼容新版 output.text 与旧版 output.choices 两种格式。
    """
    import dashscope

    timeout_s = 90
    try:
        timeout_s = max(10, int(str(os.getenv("AI_QUANT_REPORT_LLM_TIMEOUT_SECONDS", "90")).strip() or "90"))
    except Exception:
        timeout_s = 90

    box: dict[str, object] = {}

    def _call():
        try:
            box["resp"] = dashscope.Generation.call(
                model=model_name,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                top_p=0.8,
                max_tokens=4096,
            )
        except Exception as exc:
            box["exc"] = exc
            box["tb"] = traceback.format_exc()

    t = threading.Thread(target=_call, name="reports-llm-call", daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise TimeoutError(f"LLM 调用超时（>{timeout_s}s）")
    if "exc" in box:
        _report_log("[reports] llm_call_failed", str(box.get("exc") or ""))
        if box.get("tb"):
            _report_log(str(box.get("tb")))
        raise box["exc"]  # type: ignore[misc]

    resp = box.get("resp")

    text = ""
    out = resp.get("output") if isinstance(resp, dict) else None
    if isinstance(out, dict):
        if isinstance(out.get("text"), str):
            text = out.get("text") or ""
        else:
            choices = out.get("choices")
            if isinstance(choices, list) and choices:
                msg = (choices[0] or {}).get("message") if isinstance(choices[0], dict) else None
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    text = msg.get("content") or ""
    text = str(text or "").strip()
    if not text:
        raise RuntimeError("LLM 返回为空")
    return text


def _builtin_report_markdown(model: str, stock_code: str, stock_name: str, warning: str | None = None) -> str:
    """
    内置模板研报生成函数（现已降级为 fallback，不作为默认路径）。
    从 MySQL trade_stock_daily 表读取最近 30 个交易日行情数据，
    生成包含完整章节结构的标准 Markdown 研报骨架，
    用于环境配置不完整时的兜底输出。
    """
    data_note = ""
    data_block = ""
    try:
        from ai_quant_api.db import connect, load_mysql_config, query_dict

        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                "SELECT trade_date, close_price FROM trade_stock_daily WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 30",
                (stock_code,),
            )
        finally:
            conn.close()

        items = []
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            d = str(r.get("trade_date") or "").strip()
            c = r.get("close_price")
            try:
                c2 = float(c) if c is not None else None
            except Exception:
                c2 = None
            if d and c2 is not None:
                items.append((d[:10], c2))

        if items:
            latest_date, latest_close = items[0]
            prev_close = items[1][1] if len(items) > 1 else None
            ch = (latest_close - prev_close) if prev_close is not None else None
            pct = (ch / prev_close * 100.0) if (ch is not None and prev_close not in (None, 0.0)) else None
            head = [
                f"- 最新交易日：{latest_date}",
                f"- 最新收盘价：{latest_close:.2f}",
            ]
            if ch is not None and pct is not None:
                head.append(f"- 日涨跌：{ch:+.2f}（{pct:+.2f}%）")
            data_note = "\n".join(head)

            table = ["| 交易日 | 收盘价 |", "| --- | ---: |"]
            for d, c in items[:20]:
                table.append(f"| {d} | {c:.2f} |")
            data_block = "\n".join(table)
        else:
            data_note = "- 行情数据：未查询到 trade_stock_daily 记录"
    except Exception as exc:
        data_note = f"- 行情数据：读取失败（{str(exc).strip() or type(exc).__name__}）"

    title = f"# 智能研报：{stock_name}（{stock_code}）"
    meta = [
        f"- 生成时间：{now_iso()}",
        f"- 模型：{model}",
        "- 生成方式：内置模板",
    ]
    if warning:
        meta.append(f"- 提示：{warning}")
    meta_block = "\n".join(meta)

    sections = [
        title,
        "",
        "## 生成信息",
        meta_block,
        "",
        "## 数据快照",
        data_note or "- 行情数据：未知",
        "",
        (data_block or "暂无行情表格数据"),
        "",
        "## 摘要",
        "本研报基于系统内置模板生成，覆盖核心章节结构，便于联调与回归验证。若需启用 LLM+RAG，请检查环境变量与索引文件配置。",
        "",
        "## 一、公司与业务概览",
        "- 公司简介：待补充（可由研报生成模型自动补全）",
        "- 核心业务：待补充",
        "- 竞争格局：待补充",
        "",
        "## 二、财务与基本面（要点）",
        "- 收入与利润：待补充",
        "- 现金流：待补充",
        "- 估值水平：待补充",
        "",
        "## 三、技术面与交易结构（要点）",
        "- 趋势与关键位：待补充",
        "- 量价结构：待补充",
        "- 风险点：待补充",
        "",
        "## 四、事件与催化",
        "- 近期公告/新闻：待补充",
        "- 未来催化：待补充",
        "",
        "## 五、风险清单与应对",
        "- 经营风险：待补充",
        "- 政策风险：待补充",
        "- 市场风险：待补充",
        "",
        "## 六、结论与建议",
        "- 核心结论：待补充",
        "- 操作建议：待补充（仓位/止损/止盈/跟踪指标）",
        "",
    ]
    return "\n".join(sections).strip() + "\n"


def _generate_report_markdown(model: str, stock_code: str, stock_name: str, use_rag: bool = True) -> str:
    """
    单只股票的研报生成核心逻辑（严格 LLM 模式）。

    流程：
    1. 前置校验：检查 AI_QUANT_REPORT_USE_LLM 和 DASHSCOPE_API_KEY 环境变量。
    2. 从 MySQL 读取日线行情、财务报告期、最新新闻等数据快照。
    3. 若 FAISS 索引已构建则执行 RAG 检索，补充研报背景材料。
    4. 构造 system_prompt（角色设定）+ user_prompt（数据 + 结构要求），调用 DashScope LLM。
    5. 返回 LLM 生成的 Markdown 研报全文。

    若任一步骤失败则抛出异常，不使用内置模板兜底（满足"严格 LLM 成功才算验收"的要求）。
    """
    _report_log(
        "[reports] _generate_report_markdown enter"
        f" model={model} stock_code={stock_code} stock_name={stock_name}"
        f" use_llm={str(os.getenv('AI_QUANT_REPORT_USE_LLM', '')).strip()}"
        f" use_rag={bool(use_rag)}"
    )
    env_use_llm = str(os.getenv("AI_QUANT_REPORT_USE_LLM", "")).strip() in ("1", "true", "True")
    if not env_use_llm:
        raise RuntimeError("LLM 未启用，请设置 AI_QUANT_REPORT_USE_LLM=1")
    api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("missing env: DASHSCOPE_API_KEY")

    model_name = {"qwen-max": "qwen-max", "deepseek": "deepseek-v3"}.get(model, model)

    daily_rows: list[dict[str, Any]] = []
    fin_latest = ""
    news_rows: list[dict[str, Any]] = []
    try:
        from ai_quant_api.db import connect, load_mysql_config, query_dict

        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            daily_rows = query_dict(
                conn,
                "SELECT trade_date, close_price, volume, amount FROM trade_stock_daily WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 60",
                (stock_code,),
            )
            fin = query_dict(conn, "SELECT MAX(report_date) AS d FROM trade_stock_financial WHERE stock_code=%s", (stock_code,))
            fin_latest = str((fin[0] if fin else {}).get("d") or "").strip()
            news_rows = query_dict(
                conn,
                "SELECT published_at, title, news_type, url FROM trade_stock_news WHERE stock_code=%s ORDER BY published_at DESC LIMIT 30",
                (stock_code,),
            )
        finally:
            conn.close()
    except Exception as exc:
        _report_log("[reports] mysql snapshot failed", str(exc).strip() or type(exc).__name__)

    # RAG 语义检索：若索引文件已就位则查询相关文档作为研报背景材料
    rag_context = ""
    try:
        if bool(use_rag):
            s = get_rag_settings()
            idx_f = s.index_dir / "index.faiss"
            idx_p = s.index_dir / "index.pkl"
            if idx_f.exists() and idx_p.exists():
                r = rag_query(q=f"{stock_name} {stock_code} 研报 财报 经营 风险", stock=stock_code, k=6)
                items = r.get("items") if isinstance(r, dict) else None
                if isinstance(items, list) and items:
                    parts = []
                    for it in items[:6]:
                        if not isinstance(it, dict):
                            continue
                        meta = it.get("meta") if isinstance(it.get("meta"), dict) else {}
                        title = str(meta.get("title") or "").strip()
                        source = str(meta.get("source") or "").strip()
                        page = meta.get("page")
                        content = str(it.get("content") or "").strip()
                        head = f"[{source or 'RAG'}] {title}".strip()
                        if page:
                            head = f"{head} (page {page})"
                        if content:
                            parts.append(head + "\n" + content)
                    rag_context = "\n\n---\n\n".join(parts).strip()
    except Exception as exc:
        _report_log("[reports] rag_query failed", str(exc).strip() or type(exc).__name__)
        rag_context = ""

    def _fmt_table(rows: list[dict[str, Any]]) -> str:
        """将日线行情数据格式化为 Markdown 表格，最多显示 20 行。"""
        items = []
        for r in rows or []:
            if not isinstance(r, dict):
                continue
            d = str(r.get("trade_date") or "").strip()[:10]
            c = r.get("close_price")
            try:
                c2 = float(c) if c is not None else None
            except Exception:
                c2 = None
            if d and c2 is not None:
                items.append((d, c2))
        if not items:
            return ""
        lines = ["| 交易日 | 收盘价 |", "| --- | ---: |"]
        for d, c2 in items[:20]:
            lines.append(f"| {d} | {c2:.2f} |")
        return "\n".join(lines)

    daily_table = _fmt_table(daily_rows)
    news_lines = []
    for r in news_rows[:10]:
        if not isinstance(r, dict):
            continue
        t = str(r.get("title") or "").strip()
        if not t:
            continue
        d = str(r.get("published_at") or "").strip()[:19]
        nt = str(r.get("news_type") or "").strip()
        news_lines.append(f"- {d} {nt} {t}".strip())
    news_block = "\n".join(news_lines)

    # system_prompt：设定 LLM 以资深买方研究员身份输出严谨结构化研报
    system_prompt = (
        "你是资深买方研究员与投资经理助理。"
        "请基于用户提供的数据快照与RAG材料，生成一份严谨、结构化、可读性强的中文个股研报。"
        "必须输出 Markdown，包含所有章节；不要输出与任务无关的解释。"
    )

    # user_prompt：将数据快照、格式要求、输出规范组装为 LLM 用户输入
    user_prompt = "\n".join(
        [
            f"目标：生成 {stock_name}（{stock_code}）的完整研报。",
            "",
            "强制格式要求：",
            "1) 使用以下一级标题顺序：摘要、公司与业务概览、财务与基本面、行业与竞争格局、技术面与交易结构、催化与事件、风险清单与应对、结论与建议、附录（数据与假设）",
            "2) 至少包含：一张行情表格（使用提供的日线数据），一个图表（用 mermaid 或 ASCII 图均可），以及清晰的投资结论（包含逻辑链）。",
            "3) 结论与建议必须包含：观点（看多/看空/中性）、关键假设、触发条件、止损/风控要点。",
            "",
            f"研报模型标识：{model_name}",
            f"财务数据最近报告期（如有）：{fin_latest or '未知'}",
            "",
            "日线行情（最近20行表格优先使用）：",
            daily_table or "无可用日线行情数据",
            "",
            "新闻快照（最近10条）：",
            news_block or "无可用新闻数据",
            "",
            "RAG材料（若为空可忽略，但要在研报里说明信息不足的影响）：",
            rag_context or "（无）",
            "",
            "输出要求：直接输出研报 Markdown 正文。",
        ]
    )

    text = _dashscope_generate(model_name=model_name, api_key=api_key, system_prompt=system_prompt, user_prompt=user_prompt)
    return text + "\n"


def _map_report_error_message(msg: str) -> str:
    """
    将后端异常消息映射为用户友好的前端提示文案。
    目前覆盖 DASHSCOPE_API_KEY 未配置、索引未就绪两类常见错误。
    """
    text = str(msg or "").strip()
    if not text:
        return "研报生成失败"
    if "missing env: DASHSCOPE_API_KEY" in text:
        return "API Key 未配置或无效，请检查 DASHSCOPE_API_KEY"
    if "研报索引未就绪" in text:
        return "请先上传 PDF 构建索引后再生成研报"
    return text


def _process_task(task_id: str) -> None:
    """
    后台 worker 线程中执行单个研报任务的完整生成流程。
    步骤：
    1. 从持久化存储中读取任务记录。
    2. 更新状态为 running（含 started_at）。
    3. 对每只股票调用 _generate_report_markdown 生成内容。
    4. 多只股票结果用分隔线拼接，写入 report_outputs/{task_id}.md。
    5. 更新任务状态为 success 并存储报告正文。
    6. 捕获所有异常，写入日志并将状态更新为 failed（含错误提示）。
    """
    task = get_task(task_id)
    if task is None:
        return
    update_task(task_id, status="running", started_at=now_iso(), finished_at=None, error_message=None)
    try:
        if not task.stock_codes:
            raise RuntimeError("任务缺少股票信息（stock_codes 为空）")
        parts = []
        for code, name in zip(task.stock_codes, task.stock_names):
            parts.append(_generate_report_markdown(model=task.model, stock_code=code, stock_name=name, use_rag=bool(getattr(task, "use_rag", True))))
        report_md = "\n\n---\n\n".join(parts)
        if not str(report_md or "").strip():
            raise RuntimeError("研报内容为空")
        out_dir = Path(str(os.getenv("AI_QUANT_REPORT_OUTPUT_DIR", "") or "").strip() or (_project_root() / ".ai_quant" / "report_outputs"))
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"{task_id}.md"
        out_file.write_text(report_md, encoding="utf-8")
        _report_log(f"[reports] report_saved file={out_file}")
        update_task(task_id, status="success", finished_at=now_iso(), report_markdown=report_md, report_path=str(out_file))
    except BaseException as exc:
        msg = str(exc) if str(exc).strip() else f"{type(exc).__name__}"
        if isinstance(exc, SystemExit):
            msg = "研报生成被终止（请检查 DASHSCOPE_API_KEY、索引文件等配置）"
        err_loc = None
        try:
            tb = traceback.extract_tb(exc.__traceback__)
            if tb:
                last = tb[-1]
                err_loc = f"{Path(last.filename).name}:{last.lineno}"
        except Exception:
            err_loc = None
        _report_log("[reports] task_failed", f"task_id={task_id}", msg)
        _report_log(traceback.format_exc())
        update_task(task_id, status="failed", finished_at=now_iso(), error_message=_map_report_error_message(msg), error_location=err_loc)


def _worker_loop() -> None:
    """
    研报后台 worker 的主循环。
    从任务队列持续取出 task_id 并调用 _process_task 执行生成。
    使用 queue.Queue 线程安全队列，支持多任务并发调度（当前仅单 worker）。
    """
    while True:
        task_id = _TASK_QUEUE.get()
        try:
            _process_task(task_id)
        except BaseException:
            update_task(task_id, status="failed", finished_at=now_iso(), error_message="worker_failed")
        finally:
            _TASK_QUEUE.task_done()


def _ensure_worker_started() -> None:
    """
    确保后台 worker 线程仅启动一次（双重检查锁定模式）。
    首次调用时创建 daemon 线程，执行 _worker_loop；后续调用直接返回。
    """
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return
        t = threading.Thread(target=_worker_loop, name="reports-worker", daemon=True)
        t.start()
        _WORKER_STARTED = True


def _enqueue_task(task_id: str) -> None:
    """
    将任务 task_id 推入后台队列，等待 worker 消费。
    若 worker 尚未启动则先触发启动。
    """
    _ensure_worker_started()
    _TASK_QUEUE.put(task_id)


@router.get("/tasks")
def reports_list_tasks(
    limit: int = Query(default=100),
    q: str = Query(default=""),
    created_start: str = Query(default=""),
    created_end: str = Query(default=""),
) -> dict[str, Any]:
    """
    查询研报任务列表，支持分页、关键词过滤、时间范围过滤。
    同时对所有 running 状态的任务进行超时检测：
    - 若任务 started_at 距今超过 AI_QUANT_REPORT_TIMEOUT_SECONDS（默认 300s），
      自动将状态更新为 failed（超时），防止僵尸任务堆积。
    """
    n = max(1, min(int(limit), 200))
    start_d = _parse_date(created_start)
    end_d = _parse_date(created_end)
    text = (q or "").strip().lower()
    timeout_s = max(5, int(os.getenv("AI_QUANT_REPORT_TIMEOUT_SECONDS", str(_DEFAULT_REPORT_TIMEOUT_SECONDS)) or _DEFAULT_REPORT_TIMEOUT_SECONDS))

    items = list_tasks()
    out: list[dict[str, Any]] = []
    for it in items:
        if str(it.get("status") or "") == "running":
            started_at = str(it.get("started_at") or "").strip()
            if started_at:
                try:
                    started_dt = datetime.strptime(started_at[:19], "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    started_dt = None
                if started_dt is not None:
                    age = (datetime.now() - started_dt).total_seconds()
                    if age > timeout_s:
                        task_id = str(it.get("task_id") or "").strip()
                        if task_id:
                            update_task(task_id, status="failed", finished_at=now_iso(), error_message="研报生成超时，请稍后重试")
                            it["status"] = "failed"
                            it["finished_at"] = now_iso()
                            it["error_message"] = "研报生成超时，请稍后重试"
        if text:
            hay = " ".join([str(x or "") for x in (it.get("stock_codes") or []) + (it.get("stock_names") or [])]).lower()
            if text not in hay:
                continue
        created = str(it.get("created_at") or "")
        d = None
        try:
            d = datetime.strptime(created[:10], "%Y-%m-%d").date()
        except Exception:
            d = None
        if start_d and d and d < start_d:
            continue
        if end_d and d and d > end_d:
            continue
        out.append(it)
        if len(out) >= n:
            break
    return {"tasks": out}


@router.post("/tasks")
def reports_create_task(req: ReportTaskCreateRequest) -> dict[str, Any]:
    """
    创建研报生成任务。
    - model：支持 qwen-max / deepseek 两种 LLM 模型。
    - stock_codes：至少选择一只股票。
    - 内部会先通过 RAG 或 search_stocks 解析股票中文名称。
    - 任务创建后立即推入后台队列异步生成，返回任务记录（含 task_id）。
    """
    model = str(req.model or "").strip()
    stock_codes = [str(x or "").strip() for x in (req.stock_codes or []) if str(x or "").strip()]
    if model not in ("qwen-max", "deepseek"):
        raise HTTPException(status_code=400, detail="unknown model")
    if not stock_codes:
        raise HTTPException(status_code=400, detail="请选择至少一只股票")

    stock_names = _resolve_stock_names(stock_codes)
    rec = create_task(model=model, stock_codes=stock_codes, stock_names=stock_names, use_rag=bool(req.use_rag))
    payload = dict(rec.__dict__)
    _enqueue_task(rec.task_id)
    return {"task": payload}


@router.delete("/tasks/{task_id}")
def reports_delete_task(task_id: str) -> dict[str, Any]:
    """删除指定 task_id 的研报任务记录及对应的本地 .md 文件。"""
    ok = delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="task not found")
    return {"ok": True}


@router.post("/tasks/{task_id}/retry")
def reports_retry_task(task_id: str) -> dict[str, Any]:
    """
    重试失败的研报任务。
    - 任务不存在时返回 404。
    - 任务处于 running 状态时返回 409（防止并发重复生成）。
    - 将状态重置为 waiting 后重新推入后台队列。
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if str(task.status) in ("running",):
        raise HTTPException(status_code=409, detail="task is running")
    update_task(task_id, status="waiting", started_at=None, finished_at=None, error_message=None, report_markdown=None)
    _enqueue_task(task_id)
    return {"ok": True}


@router.get("/tasks/{task_id}/view")
def reports_view_task(task_id: str) -> Response:
    """
    查看研报任务生成的报告内容。
    - 任务成功（有 report_markdown）：返回 200，媒体类型为 text/markdown。
    - 任务失败：返回 500，内容为错误提示文案（前端直接展示）。
    - 任务进行中或不存在：返回 409 / 404。
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    out_dir = Path(str(os.getenv("AI_QUANT_REPORT_OUTPUT_DIR", "") or "").strip() or (_project_root() / ".ai_quant" / "report_outputs"))
    out_file = out_dir / f"{task_id}.md"
    if out_file.exists():
        try:
            return Response(content=out_file.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")
        except Exception:
            pass
    if task.report_markdown:
        return Response(content=task.report_markdown, media_type="text/markdown; charset=utf-8")
    if task.status == "failed":
        return Response(content=str(task.error_message or ""), media_type="text/plain; charset=utf-8", status_code=500)
    return Response(content="report not ready", media_type="text/plain; charset=utf-8", status_code=409)
