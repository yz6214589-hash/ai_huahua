"""
研报生成API模块
提供智能研报生成的核心功能，包括任务管理、RAG检索、LLM调用等
支持通过DashScope API调用通义千问或DeepSeek模型生成结构化研报
"""

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

from common.response import ok

from agents.report_agent import run_report_agent, ReportAgentResult
from infra.storage.report_store import create_task, delete_task, get_task, list_tasks, now_iso, update_task
from infra.storage.logging_service import get_logger
from core.data import search_stocks
from infra.reports.rag import (
    build_faiss_index,
    get_rag_settings,
    ingest_pdfs,
    rag_query,
    rag_status,
    resolve_stock_name_by_code,
)

logger = get_logger("reports")


def _do_mysql_upsert_with_rollback(
    task_id: str,
    report_path: str | None,
    status: str,
    finished_at: str,
    error_msg: str | None = None,
) -> None:
    """
    将任务写入 report_tasks 表，实现"文件存在 ↔ 表记录存在"强一致性。

    策略：文件先写入 → DB 写入（report_tasks）→ 失败则删除文件并回滚状态。
    使用 update_task 回滚状态到 waiting（而非保留 failed，避免混淆重试逻辑）。

    Args:
        task_id:      任务 ID
        report_path:  报告文件路径（成功时非空，失败时传 None）
        status:       最终状态（success / failed）
        finished_at:  完成时间（ISO 字符串）
        error_msg:    错误信息（失败时传入）
    """
    try:
        from infra.storage.report_store import _mysql_upsert_report_tasks
        from infra.storage.report_store import get_task
    except Exception:
        return

    task = get_task(task_id)
    if task is None:
        return

    task.report_path = report_path
    task.status = status
    task.finished_at = finished_at
    if error_msg:
        task.error_message = error_msg

    ok = _mysql_upsert_report_tasks(task)
    if not ok and report_path:
        try:
            Path(report_path).unlink(missing_ok=True)
            logger.warning("report_tasks 写入失败，已回滚删除文件: %s", report_path)
        except Exception:
            logger.error("文件回滚删除失败: %s", report_path)
        update_task(task_id, status="waiting", report_path=None, finished_at=None)


def _project_root() -> Path:
    """
    返回项目根目录路径
    
    通过向上查找目录层级确定项目根目录位置
    
    Returns:
        Path: 项目根目录路径
    """
    return Path(__file__).resolve().parents[3]


_REPORT_LOG_FILE = _project_root() / ".ai_quant" / "reports_worker.log"


def _report_log(*args, **kwargs) -> None:
    """
    统一日志输出函数
    
    同时打印到标准输出和写入reports_worker.log文件，每行日志自动追加时间戳前缀
    便于追踪研报生成过程中的异常和调试问题
    
    Args:
        *args: 日志内容参数
        **kwargs: 其他打印参数
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


router = APIRouter(prefix="/api/v1/reports", tags=["reports"])

_TASK_QUEUE: queue.Queue[str] = queue.Queue()
_WORKER_STARTED = False
_WORKER_LOCK = threading.Lock()
_WORKER_COUNT = 2
_DEFAULT_REPORT_TIMEOUT_SECONDS = 300


class ReportTaskCreateRequest(BaseModel):
    """
    创建研报任务的请求体数据模型
    
    Attributes:
        model: LLM模型名称，支持qwen-max和deepseek
        stock_codes: 股票代码列表
        use_rag: 是否启用本地RAG检索增强（默认 False）
        mode: 生成模式 - qwen（默认）、deepseek_with_web（DeepSeek + 联网搜索）
    """
    model: str
    stock_codes: list[str]
    use_rag: bool = False
    mode: str = "qwen"


def _parse_date(v: str) -> date | None:
    """
    解析日期字符串为date对象
    
    将YYYY-MM-DD格式的字符串解析为Python date对象
    
    Args:
        v: 日期字符串
        
    Returns:
        date对象或None（解析失败时）
    """
    s = (v or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _check_llm_available(mode: str) -> str | None:
    """
    检查 LLM 生成所需的环境配置是否就绪。
    
    在创建研报任务前进行前置校验，避免任务创建后因 LLM 不可用
    导致轮询超时。根据不同的生成模式检查对应的配置项。
    
    Args:
        mode: 生成模式 - qwen / deepseek / deepseek_with_web
        
    Returns:
        None 表示检查通过，非 None 字符串表示错误信息
    """
    if mode == "deepseek_with_web":
        api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
        if not api_key:
            return "DASHSCOPE_API_KEY 未配置，无法使用 deepseek_with_web 模式进行研报生成"
        return None

    env_use_llm = str(os.getenv("AI_QUANT_REPORT_USE_LLM", "")).strip() in ("1", "true", "True")
    if not env_use_llm:
        return "LLM 未启用，请设置环境变量 AI_QUANT_REPORT_USE_LLM=1 以启用 LLM 研报生成"

    api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
    if not api_key:
        return "DASHSCOPE_API_KEY 未配置，无法调用 LLM 生成研报"

    return None


def _resolve_stock_names(stock_codes: list[str]) -> list[str]:
    """
    根据股票代码列表解析对应的中文名称

    优先从RAG服务获取股票名称，若未命中则通过search_stocks查询
    确保返回的名称列表与输入的代码列表长度一致

    异常保护：RAG 数据库或 search_stocks 任一环节失败都优雅降级，
    保证创建研报任务的核心流程不被阻塞。

    Args:
        stock_codes: 股票代码列表

    Returns:
        对应的中文名称列表
    """
    names: list[str] = []
    for code in stock_codes:
        text = str(code or "").strip()
        if not text:
            continue
        # 优先从RAG服务获取名称（RAG 内部已做异常保护）
        rag_name = None
        try:
            rag_name = resolve_stock_name_by_code(text)
        except Exception:
            rag_name = None
        if rag_name:
            names.append(rag_name)
            continue
        # 通过搜索服务查询名称（DB 故障时降级为返回原始代码）
        try:
            r = search_stocks(q=text, limit=1)
            items = r.get("items") if isinstance(r, dict) else None
            name = None
            if isinstance(items, list) and items:
                first = items[0] if isinstance(items[0], dict) else {}
                name = first.get("name")
            names.append(str(name or text))
        except Exception:
            names.append(text)
    # 确保名称列表长度与代码列表一致
    while len(names) < len(stock_codes):
        names.append(str(stock_codes[len(names)]))
    return names


class RagIngestRequest(BaseModel):
    """
    RAG索引构建请求体
    
    Attributes:
        rebuild: 是否强制重建索引
        limit: 本次最多处理的PDF数量限制
    """
    rebuild: bool = False
    limit: int | None = None


@router.get("/rag/status")
def reports_rag_status() -> dict[str, Any]:
    """
    查询当前RAG索引状态
    
    返回索引目录、文件是否存在、文档数量等信息
    
    Returns:
        dict: RAG索引状态信息
    """
    return ok(rag_status())


@router.post("/rag/ingest")
def reports_rag_ingest(req: RagIngestRequest) -> dict[str, Any]:
    ingest = ingest_pdfs(rebuild=bool(req.rebuild), limit=req.limit)
    built = build_faiss_index(rebuild=bool(req.rebuild))
    return ok({"ingest": ingest, "index": built})


@router.get("/rag/query")
def reports_rag_query(q: str = Query(default=""), stock: str = Query(default=""), k: int = Query(default=6)) -> dict[str, Any]:
    """
    向RAG索引发起语义检索
    
    根据查询文本在向量索引中查找最相关的文档片段
    
    Args:
        q: 检索查询文本（如公司名、财报关键词）
        stock: 限定只检索指定股票的文档
        k: 返回结果数量上限
        
    Returns:
        dict: 包含k条最相关文档片段
    """
    return ok(rag_query(q=q, stock=stock, k=k))


def _case_root() -> Path:
    """
    CASE智能研报生成脚本的根目录（已废弃）
    
    仅作占位保留，不再使用
    
    Returns:
        Path: CASE脚本根目录路径
    """
    return _project_root() / "CASE-智能研报生成"


def _dashscope_generate(*, model_name: str, api_key: str, system_prompt: str, user_prompt: str) -> str:
    """
    调用阿里云DashScope API生成文本内容
    
    在独立后台线程中执行HTTP请求，支持配置超时时间（默认90秒）
    兼容新版output.text与旧版output.choices两种响应格式
    
    Args:
        model_name: 模型名称
        api_key: DashScope API密钥
        system_prompt: 系统提示词
        user_prompt: 用户输入提示词
        
    Returns:
        str: LLM生成的文本内容
        
    Raises:
        TimeoutError: LLM调用超时
        RuntimeError: LLM返回为空
        Exception: API调用失败
    """
    import dashscope

    timeout_s = 90
    try:
        timeout_s = max(10, int(str(os.getenv("AI_QUANT_REPORT_LLM_TIMEOUT_SECONDS", "90")).strip() or "90"))
    except Exception:
        timeout_s = 90

    box: dict[str, object] = {}

    def _call():
        """在线程中执行API调用"""
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
        logger.error("LLM 调用失败", extra={
            "model": model_name,
            "error": str(box.get("exc") or ""),
            "traceback": str(box.get("tb") or "")
        })
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
    内置模板研报生成函数
    
    作为fallback方案，当LLM不可用时使用此模板生成基础研报结构
    从MySQL读取最近30个交易日行情数据，生成标准Markdown研报骨架
    
    Args:
        model: LLM模型名称
        stock_code: 股票代码
        stock_name: 股票名称
        warning: 警告提示信息
        
    Returns:
        str: Markdown格式的研报文本
    """
    data_note = ""
    data_block = ""
    try:
        from core.db import connect, load_mysql_config, query_dict

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


def _generate_report_markdown(
    model: str,
    stock_code: str,
    stock_name: str,
    use_rag: bool = False,
    mode: str = "qwen",
) -> str:
    """
    单只股票的研报生成核心逻辑。

    完整流程：
    1. 前置校验：检查 API Key 环境变量
    2. deepseek_with_web 模式：调用 report_agent（联网搜索 + DeepSeek）
    3. qwen 模式：读取 MySQL 数据快照，调用 DashScope LLM
    4. 返回 Markdown 研报全文

    Args:
        model: LLM 模型名称
        stock_code: 股票代码
        stock_name: 股票名称
        use_rag: 是否使用本地 RAG
        mode: 生成模式 - qwen / deepseek_with_web

    Returns:
        Markdown 格式研报全文

    Raises:
        RuntimeError: 环境配置不完整或 LLM 调用失败
    """
    logger.info("研报生成开始", extra={
        "model": model,
        "stock_code": stock_code,
        "stock_name": stock_name,
        "use_rag": bool(use_rag),
        "mode": mode,
    })

    if mode == "deepseek_with_web":
        logger.info("使用 DeepAgent 模式", extra={
            "stock_code": stock_code,
            "stock_name": stock_name,
            "use_rag": bool(use_rag),
        })
        result = run_report_agent(
            stock_codes=[stock_code],
            stock_names=[stock_name],
            mode=mode,
            use_rag=bool(use_rag),
            model=model,
        )
        if result.error:
            raise RuntimeError(result.error)
        logger.info("DeepAgent 完成", extra={
            "stock_code": stock_code,
            "tools_used": result.tools_used,
            "text_len": len(result.text),
        })
        return result.text + "\n"

    env_use_llm = str(os.getenv("AI_QUANT_REPORT_USE_LLM", "")).strip() in ("1", "true", "True")
    if not env_use_llm:
        logger.warning("LLM 未启用", extra={
            "model": model,
            "stock_code": stock_code
        })
        raise RuntimeError("LLM 未启用，请设置 AI_QUANT_REPORT_USE_LLM=1")
    api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
    if not api_key:
        logger.error("DASHSCOPE_API_KEY 未配置", extra={
            "model": model,
            "stock_code": stock_code
        })
        raise RuntimeError("missing env: DASHSCOPE_API_KEY")

    model_name = {"qwen-max": "qwen-max", "deepseek": "deepseek-v3"}.get(model, model)
    logger.debug("LLM 调用开始", extra={
        "model": model_name,
        "stock_code": stock_code
    })

    daily_rows: list[dict[str, Any]] = []
    fin_latest = ""
    news_rows: list[dict[str, Any]] = []
    try:
        from core.db import connect, load_mysql_config, query_dict

        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            # 查询最近60个交易日行情数据
            daily_rows = query_dict(
                conn,
                "SELECT trade_date, close_price, volume, amount FROM trade_stock_daily WHERE stock_code=%s ORDER BY trade_date DESC LIMIT 60",
                (stock_code,),
            )
            # 查询最新财务报告期
            fin = query_dict(conn, "SELECT MAX(report_date) AS d FROM trade_stock_financial WHERE stock_code=%s", (stock_code,))
            fin_latest = str((fin[0] if fin else {}).get("d") or "").strip()
            # 查询最近30条新闻
            news_rows = query_dict(
                conn,
                "SELECT published_at, title, news_type, source_url FROM trade_stock_news WHERE stock_code=%s ORDER BY published_at DESC LIMIT 30",
                (stock_code,),
            )
        finally:
            conn.close()
    except Exception as exc:
        logger.error("数据库查询失败", extra={
            "model": model_name,
            "stock_code": stock_code,
            "error": str(exc)
        })

    # RAG语义检索：若索引文件已就位则查询相关文档作为研报背景材料
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
        logger.warning("RAG 检索失败", extra={
            "model": model_name,
            "stock_code": stock_code,
            "error": str(exc)
        })
        rag_context = ""

    def _fmt_table(rows: list[dict[str, Any]]) -> str:
        """
        将日线行情数据格式化为Markdown表格
        
        Args:
            rows: 日线行情数据列表
            
        Returns:
            str: Markdown格式的表格，最多显示20行
        """
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

    # system_prompt：设定LLM以资深买方研究员身份输出严谨结构化研报
    system_prompt = (
        "你是资深买方研究员与投资经理助理。"
        "请基于用户提供的数据快照与RAG材料，生成一份严谨、结构化、可读性强的中文个股研报。"
        "必须输出 Markdown，包含所有章节；不要输出与任务无关的解释。"
    )

    # user_prompt：将数据快照、格式要求、输出规范组装为LLM用户输入
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

    # 五步法开关：AI_QUANT_REPORT_USE_FIVE_STEP=1 启用（默认启用）
    use_five_step = str(os.getenv("AI_QUANT_REPORT_USE_FIVE_STEP", "1")).strip() not in ("0", "false", "False", "")
    if use_five_step:
        logger.info("使用国泰君安'五步法'生成研报", extra={
            "stock_code": stock_code,
            "model": model_name,
            "use_rag": bool(use_rag),
        })
        text = _five_step_generate_report(
            model_name=model_name,
            api_key=api_key,
            stock_code=stock_code,
            stock_name=stock_name,
            daily_table=daily_table or "",
            news_block=news_block or "",
            fin_latest=fin_latest or "",
            rag_context=rag_context or "",
        )
        return text

    # 单次 LLM 调用（保留作为兜底，关闭五步法时使用）
    text = _dashscope_generate(model_name=model_name, api_key=api_key, system_prompt=system_prompt, user_prompt=user_prompt)
    return text + "\n"


# ============================================================
# 国泰君安"五步法"研报生成实现
# ============================================================
# 五步法核心思想：信息差 → 逻辑差 → 预期差 → 催化剂 → 结论+风险闭环
# 每一步都基于前一步的输出做"递进式推理"，确保研报有清晰的逻辑链。
# 相比单次大调用，迭代式调用能让模型在每一步聚焦特定分析视角，
# 输出更聚焦、更具深度的研报内容。
# ============================================================

# 五步法每个步骤的 Prompt 模板（聚焦问题 + 数据注入槽位）
FIVE_STEP_PROMPTS: dict[str, dict[str, str]] = {
    "information_gap": {
        "name": "信息差",
        "title": "一、信息差 — 市场尚未充分关注的关键信息",
        "focus": "寻找'信息差'：市场尚未充分关注或被忽视的关键数据/事件/趋势",
        "template": (
            "你是一位资深买方研究员，正在为 {stock_name}（{stock_code}）撰写深度研报。"
            "当前是五步法分析框架的【第一步：信息差】。\n\n"
            "【本步骤核心问题】\n"
            "{focus}\n\n"
            "【可用数据】\n"
            "1. 日线行情快照（最近 60 个交易日，已抽取关键字段）：\n{daily_table}\n\n"
            "2. 新闻快照（最近 30 条）：\n{news_block}\n\n"
            "3. 本地 RAG 检索材料（财报/研报节选）：\n{rag_context}\n\n"
            "【输出要求】\n"
            "- 列出 3-5 个'市场可能忽视'的关键信息点（正面 / 负面各 1-3 条）\n"
            "- 每个信息点需附：具体数据支撑、为什么被忽视、对股价的潜在影响\n"
            "- 控制在 400 字以内，使用 Markdown 列表表达\n"
            "- 直接输出本步骤分析内容，不要包含其他章节标题或解释性文字"
        ),
    },
    "logic_gap": {
        "name": "逻辑差",
        "title": "二、逻辑差 — 市场对数据的推理错在哪里",
        "focus": "寻找'逻辑差'：市场对已知数据/事件的主流推理可能存在哪些错误",
        "template": (
            "你是一位资深买方研究员，正在为 {stock_name}（{stock_code}）撰写深度研报。"
            "当前是五步法分析框架的【第二步：逻辑差】。\n\n"
            "【本步骤核心问题】\n"
            "{focus}\n\n"
            "【上一步输出（信息差）】\n{previous_analysis}\n\n"
            "【补充 RAG 材料（业务/竞争/驱动因素）】\n{rag_context}\n\n"
            "【输出要求】\n"
            "- 指出 2-4 个市场主流逻辑可能存在的'推理偏差'\n"
            "- 给出正确的因果逻辑链（数据 A → 实际是 C，而非市场认为的 D）\n"
            "- 控制在 400 字以内，使用 Markdown 列表表达\n"
            "- 直接输出本步骤分析内容"
        ),
    },
    "expectation_gap": {
        "name": "预期差",
        "title": "三、预期差 — 一致预期 vs 实际的偏离方向与幅度",
        "focus": "寻找'预期差'：市场一致预期与公司实际/合理预期之间的偏离",
        "template": (
            "你是一位资深买方研究员，正在为 {stock_name}（{stock_code}）撰写深度研报。"
            "当前是五步法分析框架的【第三步：预期差】。\n\n"
            "【本步骤核心问题】\n"
            "{focus}\n\n"
            "【可用数据】\n"
            "1. 财务数据最近报告期：{fin_latest}\n"
            "2. 日线行情趋势（最近 60 日）：\n{daily_table}\n\n"
            "【前两步输出（信息差 + 逻辑差）】\n{previous_analysis}\n\n"
            "【输出要求】\n"
            "- 用 Markdown 表格对比'市场一致预期 vs 财报实际/合理估计'（覆盖营收增速、净利润增速、毛利率、ROE 等核心指标）\n"
            "- 说明预期差的驱动因素（一次性 vs 持续性）\n"
            "- 给出预期差的方向（正向 / 负向）与强度判断\n"
            "- 控制在 400 字以内\n"
            "- 直接输出本步骤分析内容"
        ),
    },
    "catalyst": {
        "name": "催化剂",
        "title": "四、催化剂 — 触发价值重估的事件与时间窗口",
        "focus": "识别'催化剂'：可能触发市场重新评估该公司价值的事件或时间节点",
        "template": (
            "你是一位资深买方研究员，正在为 {stock_name}（{stock_code}）撰写深度研报。"
            "当前是五步法分析框架的【第四步：催化剂】。\n\n"
            "【本步骤核心问题】\n"
            "{focus}\n\n"
            "【可用数据】\n"
            "1. 近期新闻：\n{news_block}\n"
            "2. 财务报告期：{fin_latest}\n\n"
            "【前三步输出（信息差 + 逻辑差 + 预期差）】\n{previous_analysis}\n\n"
            "【输出要求】\n"
            "- 列出短期催化剂（1-3 个月）3-5 个\n"
            "- 列出中期催化剂（3-12 个月）2-3 个\n"
            "- 列出潜在负面催化剂 1-2 个\n"
            "- 用时间线呈现：未来 1 / 3 / 6 / 12 个月最可能发生的催化剂\n"
            "- 控制在 400 字以内\n"
            "- 直接输出本步骤分析内容"
        ),
    },
    "conclusion": {
        "name": "结论与风险闭环",
        "title": "五、结论与风险闭环 — 投资建议 + 假设证伪风险",
        "focus": "综合前四步给出最终投资结论，并明确风险闭环（哪些假设失效会推翻结论）",
        "template": (
            "你是一位资深买方研究员，正在为 {stock_name}（{stock_code}）撰写深度研报的最终结论。"
            "当前是五步法分析框架的【第五步：结论与风险闭环】。\n\n"
            "【本步骤核心问题】\n"
            "{focus}\n\n"
            "【前四步分析（信息差 / 逻辑差 / 预期差 / 催化剂）】\n{previous_analysis}\n\n"
            "【输出要求 — 必须包含以下五段】\n"
            "1. 【核心观点】一句话总结（看多 / 看空 / 中性 + 核心逻辑）\n"
            "2. 【投资逻辑】3-5 个要点，引用前四步的结论\n"
            "3. 【投资评级】强烈推荐 / 推荐 / 中性 / 回避 + 评级依据\n"
            "4. 【关键假设与风险闭环】列出 2-3 个关键假设，并明确'若 XX 假设被证伪，结论将被推翻'\n"
            "5. 【关注指标】3-5 个需要持续跟踪的指标\n"
            "- 控制在 500 字以内\n"
            "- 直接输出本步骤分析内容"
        ),
    },
}


def _five_step_generate_report(
    *,
    model_name: str,
    api_key: str,
    stock_code: str,
    stock_name: str,
    daily_table: str,
    news_block: str,
    fin_latest: str,
    rag_context: str,
) -> str:
    """
    按国泰君安"五步法"迭代式生成研报。

    实现要点：
    1. 严格按"信息差 → 逻辑差 → 预期差 → 催化剂 → 结论"顺序逐次调用 LLM
    2. 每一步的输出作为下一步的 previous_analysis，形成递进式分析链
    3. 步骤失败时优雅降级：保留已有内容继续后续步骤，最终仍返回可用报告
    4. 最终报告以"摘要 + 五步法正文"形式组装

    Args:
        model_name: LLM 模型名（如 qwen-max / deepseek-v3）
        api_key: DashScope API Key
        stock_code: 股票代码
        stock_name: 股票名称
        daily_table: 行情表格 Markdown（已格式化）
        news_block: 新闻快照（多行字符串）
        fin_latest: 财务最近报告期
        rag_context: 本地 RAG 检索内容

    Returns:
        str: 完整 Markdown 研报
    """
    system_prompt = (
        "你是资深买方研究员与投资经理助理，正在使用国泰君安'五步法'（信息差→逻辑差→"
        "预期差→催化剂→结论+风险闭环）撰写中文个股研报。\n"
        "要求：\n"
        "1) 严格基于事实与提供的数据，不要编造数字；\n"
        "2) 数据缺失时明确说明，不要编造；\n"
        "3) 逻辑推理必须可追溯到前一步或原始数据；\n"
        "4) 结论必须包含风险闭环（假设证伪路径）。"
    )

    step_keys = ["information_gap", "logic_gap", "expectation_gap", "catalyst", "conclusion"]
    accumulated = ""
    step_results: list[tuple[str, str]] = []  # (title, content)

    for idx, key in enumerate(step_keys, start=1):
        cfg = FIVE_STEP_PROMPTS[key]
        user_prompt = cfg["template"].format(
            stock_name=stock_name,
            stock_code=stock_code,
            focus=cfg["focus"],
            daily_table=daily_table or "（无）",
            news_block=news_block or "（无）",
            rag_context=rag_context or "（无）",
            fin_latest=fin_latest or "未知",
            previous_analysis=accumulated or "（这是首步分析，无前置分析结果）",
        )
        logger.info("五步法研报：开始步骤", extra={
            "step_index": idx,
            "step_name": cfg["name"],
            "stock_code": stock_code,
            "model": model_name,
        })
        try:
            content = _dashscope_generate(
                model_name=model_name,
                api_key=api_key,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            content = str(content or "").strip()
        except Exception as exc:
            # 单步失败不阻塞整体任务：记录错误并以占位内容继续
            logger.warning("五步法研报：单步调用失败，使用占位内容继续", extra={
                "step_index": idx,
                "step_name": cfg["name"],
                "stock_code": stock_code,
                "error": str(exc),
            })
            content = f"_（本步骤因 {type(exc).__name__} 未能生成：{str(exc)[:200]}）_"

        step_results.append((cfg["title"], content))
        accumulated += f"\n\n### {cfg['title']}\n{content}"

    # 摘要：在五步分析完成后单独生成一段 100-150 字的摘要
    summary_prompt = (
        f"你已完成 {stock_name}（{stock_code}）的五步法分析。请基于以下五步输出，"
        f"撰写一段 100-150 字的'摘要'，包含：核心观点、投资逻辑要点、主要风险。\n\n"
        f"五步分析全文：\n{accumulated}\n\n"
        f"输出要求：直接输出摘要正文，不要任何前缀（如'摘要：'）。"
    )
    try:
        summary_text = _dashscope_generate(
            model_name=model_name,
            api_key=api_key,
            system_prompt=system_prompt,
            user_prompt=summary_prompt,
        ).strip()
    except Exception as exc:
        logger.warning("五步法研报：摘要生成失败，使用首步内容截取", extra={
            "stock_code": stock_code,
            "error": str(exc),
        })
        summary_text = (step_results[0][1] if step_results else "摘要生成失败")[:300]

    # 组装最终 Markdown 报告
    body_lines: list[str] = [
        f"# 深度研报：{stock_name}（{stock_code}）",
        "",
        "> 分析框架：国泰君安'五步法'（信息差 → 逻辑差 → 预期差 → 催化剂 → 结论+风险闭环）",
        f"> 生成模型：{model_name}",
        f"> 生成时间：{now_iso()}",
        "",
        "## 摘要",
        summary_text or "（摘要生成失败）",
        "",
    ]
    for title, content in step_results:
        body_lines.append(f"## {title}")
        body_lines.append("")
        body_lines.append(content or "（本步骤无内容）")
        body_lines.append("")

    # 风险提示与免责声明（标准尾部）
    body_lines.extend([
        "## 风险提示",
        "- 本报告由 AI 基于公开行情、新闻与本地 RAG 材料自动生成，可能存在遗漏或偏差。",
        "- 投资建议仅供参考，不构成投资决策依据；据此操作风险自担。",
        "- 市场环境、政策、公司经营等变化均可能导致结论失效。",
        "",
        "## 免责声明",
        "本报告由 AI 投研助手自动生成，仅供学习与研究参考，不构成任何投资建议。",
    ])

    return "\n".join(body_lines) + "\n"


def _map_report_error_message(msg: str) -> str:
    """
    将后端异常消息映射为用户友好的前端提示文案
    
    目前覆盖DASHSCOPE_API_KEY未配置、索引未就绪两类常见错误
    
    Args:
        msg: 原始错误消息
        
    Returns:
        str: 用户友好的错误提示
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
    后台 worker 线程中执行单个研报任务的完整生成流程

    步骤：
    1. 从持久化存储中读取任务记录
    2. 更新状态为 running（含 started_at）
    3. 对每只股票调用 _generate_report_markdown 生成内容
    4. 多只股票结果用分隔线拼接，写入 report_outputs/report_{YYYYMMDD}_{task_id}.md
    5. 尝试写入 report_tasks 表（事务一致性：DB 失败则删除文件并回滚状态）
    6. 更新任务状态为 success 并存储报告正文
    7. 捕获所有异常，写入日志并将状态更新为 failed（含错误提示）

    Args:
        task_id: 任务唯一标识符
    """
    task = get_task(task_id)
    if task is None:
        return
    update_task(task_id, status="running", started_at=now_iso(), finished_at=None, error_message=None)
    out_file: Path | None = None
    try:
        if not task.stock_codes:
            raise RuntimeError("任务缺少股票信息（stock_codes 为空）")
        parts = []
        for code, name in zip(task.stock_codes, task.stock_names):
            parts.append(_generate_report_markdown(
                model=task.model,
                stock_code=code,
                stock_name=name,
                use_rag=bool(getattr(task, "use_rag", False)),
                mode=getattr(task, "mode", "qwen"),
            ))
        report_md = "\n\n---\n\n".join(parts)
        if not str(report_md or "").strip():
            raise RuntimeError("研报内容为空")

        date_str = datetime.now().strftime("%Y%m%d")
        _default_out_dir = _project_root() / ".ai_quant" / "report_outputs"
        _env_out_dir = Path(str(os.getenv("AI_QUANT_REPORT_OUTPUT_DIR", "") or "").strip())
        out_dir = _env_out_dir if str(_env_out_dir) not in (".", "") else _default_out_dir

        # 输出目录创建失败（无写权限、磁盘满等）时依次降级到默认目录 / 系统临时目录
        # 避免因目录问题导致整个研报生成任务失败
        out_file: Path | None = None
        candidate_dirs: list[Path] = []
        if str(_env_out_dir) not in (".", ""):
            candidate_dirs.append(_env_out_dir)
        candidate_dirs.append(_default_out_dir)
        try:
            import tempfile
            tmp_dir = Path(tempfile.gettempdir()) / "ai_quant_reports"
            candidate_dirs.append(tmp_dir)
        except Exception:
            pass

        for cand in candidate_dirs:
            try:
                cand.mkdir(parents=True, exist_ok=True)
                out_file = cand / f"report_{date_str}_{task_id}.md"
                out_file.write_text(report_md, encoding="utf-8")
                out_dir = cand
                break
            except Exception as e:
                logger.warning("研报输出目录写入失败，尝试降级目录", extra={
                    "task_id": task_id,
                    "out_dir": str(cand),
                    "error": str(e),
                })
                out_file = None
                continue
        if out_file is None:
            raise RuntimeError("所有候选输出目录均不可写，请检查磁盘空间与目录权限")

        file_size = len(report_md.encode("utf-8"))
        logger.info("研报保存成功", extra={
            "task_id": task_id,
            "file_path": str(out_file),
            "file_size": file_size,
            "stocks_count": len(task.stock_codes),
            "use_web": bool(getattr(task, "use_web", False)),
        })

        finished_at = now_iso()
        updated = update_task(
            task_id,
            status="success",
            finished_at=finished_at,
            report_markdown=report_md,
            report_path=str(out_file),
        )
        if updated:
            rec = updated
        else:
            rec = None

        _do_mysql_upsert_with_rollback(task_id, str(out_file), "success", finished_at)

        update_task(task_id, status="success")

    except BaseException as exc:
        msg = str(exc) if str(exc).strip() else f"{type(exc).__name__}"
        if isinstance(exc, SystemExit):
            msg = "研报生成被终止（请检查 DASHSCOPE_API_KEY、索引文件等配置）"
        err_loc: str | None = None
        try:
            tb = traceback.extract_tb(exc.__traceback__)
            if tb:
                last = tb[-1]
                err_loc = f"{Path(last.filename).name}:{last.lineno}"
        except Exception:
            err_loc = None
        logger.error("任务执行失败", extra={
            "task_id": task_id,
            "error": msg,
            "error_location": err_loc,
            "traceback": traceback.format_exc(),
        })
        finished_at = now_iso()
        update_task(task_id, status="failed", finished_at=finished_at,
                    error_message=_map_report_error_message(msg), error_location=err_loc)
        _do_mysql_upsert_with_rollback(task_id, None, "failed", finished_at,
                                       error_msg=_map_report_error_message(msg))


def _worker_loop() -> None:
    """
    研报后台worker的主循环
    
    从任务队列持续取出task_id并调用_process_task执行生成
    使用queue.Queue线程安全队列，支持多任务并发调度（当前仅单worker）
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
    global _WORKER_STARTED
    if _WORKER_STARTED:
        return
    with _WORKER_LOCK:
        if _WORKER_STARTED:
            return
        for i in range(_WORKER_COUNT):
            t = threading.Thread(target=_worker_loop, name=f"reports-worker-{i}", daemon=True)
            t.start()
        _WORKER_STARTED = True


def _enqueue_task(task_id: str) -> None:
    """
    将任务task_id推入后台队列，等待worker消费
    
    若worker尚未启动则先触发启动
    
    Args:
        task_id: 任务唯一标识符
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
    查询研报任务列表
    
    支持分页、关键词过滤、时间范围过滤
    同时对所有running状态的任务进行超时检测：
    - 若任务started_at距今超过AI_QUANT_REPORT_TIMEOUT_SECONDS（默认300s），
      自动将状态更新为failed（超时），防止僵尸任务堆积
    
    Args:
        limit: 返回记录数量上限
        q: 关键词搜索（匹配股票代码或名称）
        created_start: 创建时间范围起点
        created_end: 创建时间范围终点
        
    Returns:
        dict: 包含任务列表
    """
    n = max(1, min(int(limit), 200))
    start_d = _parse_date(created_start)
    end_d = _parse_date(created_end)
    text = (q or "").strip().lower()
    timeout_s = max(5, int(os.getenv("AI_QUANT_REPORT_TIMEOUT_SECONDS", str(_DEFAULT_REPORT_TIMEOUT_SECONDS)) or _DEFAULT_REPORT_TIMEOUT_SECONDS))

    items = list_tasks()
    out: list[dict[str, Any]] = []
    for it in items:
        # 超时检测：自动标记超时任务为失败
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
        # 关键词过滤
        if text:
            hay = " ".join([str(x or "") for x in (it.get("stock_codes") or []) + (it.get("stock_names") or [])]).lower()
            if text not in hay:
                continue
        # 时间范围过滤
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
    return ok({"tasks": out})


@router.post("/tasks")
def reports_create_task(req: ReportTaskCreateRequest) -> dict[str, Any]:
    """
    创建研报生成任务

    - model：支持qwen-max/deepseek两种LLM模型
    - stock_codes：至少选择一只股票
    - 内部会先通过RAG或search_stocks解析股票中文名称
    - 任务创建前检查 LLM 环境配置是否就绪，避免轮询超时
    - 任务创建后立即推入后台队列异步生成，返回任务记录（含task_id）
    - 全局异常保护：捕获未预料的运行时错误（如依赖服务不可用、磁盘满等），
      转换为 500 错误并返回用户友好的错误信息

    Args:
        req: 任务创建请求参数

    Returns:
        dict: 包含创建的任务记录
    """
    model = str(req.model or "").strip()
    stock_codes = [str(x or "").strip() for x in (req.stock_codes or []) if str(x or "").strip()]
    if model not in ("qwen-max", "deepseek"):
        raise HTTPException(status_code=400, detail="unknown model")
    if not stock_codes:
        raise HTTPException(status_code=400, detail="请选择至少一只股票")

    mode_val = str(req.mode or "qwen")

    # LLM 前置检查：确认环境配置就绪，避免任务入队后因 LLM 不可用导致轮询超时
    check_result = _check_llm_available(mode_val)
    if check_result is not None:
        logger.error("创建任务前 LLM 检查失败", extra={"mode": mode_val, "error": check_result})
        raise HTTPException(status_code=400, detail=check_result)

    try:
        stock_names = _resolve_stock_names(stock_codes)
    except Exception as e:
        # 兜底：股票名称解析失败时用原始代码填充，保证任务可创建
        logger.warning("解析股票名称异常，使用原始代码兜底", extra={"error": str(e)})
        stock_names = list(stock_codes)

    try:
        rec = create_task(
            model=model,
            stock_codes=stock_codes,
            stock_names=stock_names,
            use_rag=bool(req.use_rag),
            mode=mode_val,
            use_web=(mode_val == "deepseek_with_web"),
        )
    except HTTPException:
        raise
    except Exception as e:
        # 任务创建失败（DB 连接、磁盘满等）转换为友好的 500 错误
        logger.error("创建研报任务失败", extra={"error": str(e), "traceback": traceback.format_exc()})
        raise HTTPException(
            status_code=500,
            detail=f"创建研报任务失败：{type(e).__name__}: {str(e)[:200] or '未知错误'}",
        )

    payload = dict(rec.__dict__)
    _enqueue_task(rec.task_id)
    return ok({"task": payload})


@router.delete("/tasks/{task_id}")
def reports_delete_task(task_id: str) -> dict[str, Any]:
    """
    删除指定研报任务
    
    删除任务记录及对应的本地.md文件
    
    Args:
        task_id: 任务唯一标识符
        
    Returns:
        dict: 操作结果
    """
    deleted = delete_task(task_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="task not found")
    return ok({"ok": True})


@router.get("/tasks/{task_id}/status")
def reports_task_status(task_id: str) -> dict[str, Any]:
    """
    查询研报任务状态（含超时熔断检测）
    
    返回任务当前状态、创建时间等信息。如果任务处于 waiting 状态
    且创建时间超过 5 分钟，自动标记为 timeout 状态并返回，
    避免前端无限期轮询等待。
    
    Args:
        task_id: 任务唯一标识符
        
    Returns:
        dict: 包含任务状态信息
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    status = str(task.status or "").strip()

    # 超时熔断检测：如果任务处于 waiting 或 running 状态且超过阈值，标记为超时
    timeout_seconds = 300  # 5 分钟
    if status in ("waiting", "running"):
        created_at = str(getattr(task, "created_at", "") or "").strip()
        if created_at:
            try:
                created_dt = datetime.strptime(created_at[:19], "%Y-%m-%dT%H:%M:%S")
                age = (datetime.now() - created_dt).total_seconds()
                if age > timeout_seconds:
                    logger.warning("任务超时熔断", extra={
                        "task_id": task_id,
                        "status": status,
                        "age_seconds": round(age, 1),
                    })
                    update_task(task_id, status="timeout", finished_at=now_iso(),
                                error_message="任务执行超时（超过5分钟），请稍后重试")
                    status = "timeout"
            except Exception:
                pass

    return ok({
        "task_id": task_id,
        "status": status,
        "created_at": str(getattr(task, "created_at", "") or ""),
        "started_at": str(getattr(task, "started_at", "") or ""),
        "finished_at": str(getattr(task, "finished_at", "") or ""),
        "error_message": str(getattr(task, "error_message", "") or ""),
    })


@router.post("/tasks/{task_id}/retry")
def reports_retry_task(task_id: str) -> dict[str, Any]:
    """
    重试失败的研报任务
    
    - 任务不存在时返回404
    - 任务处于running状态时返回409（防止并发重复生成）
    - 将状态重置为waiting后重新推入后台队列
    
    Args:
        task_id: 任务唯一标识符
        
    Returns:
        dict: 操作结果
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if str(task.status) in ("running",):
        raise HTTPException(status_code=409, detail="task is running")
    update_task(task_id, status="waiting", started_at=None, finished_at=None, error_message=None, report_markdown=None)
    _enqueue_task(task_id)
    return ok({"ok": True})


@router.get("/tasks/{task_id}/view")
def reports_view_task(task_id: str) -> Response:
    """
    查看研报任务生成的报告内容
    
    - 任务成功（有report_markdown）：返回200，媒体类型为text/markdown
    - 任务失败：返回500，内容为错误提示文案（前端直接展示）
    - 任务进行中或不存在：返回409/404
    
    Args:
        task_id: 任务唯一标识符
        
    Returns:
        Response: Markdown格式的研报内容或错误信息
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    _default_out_dir = _project_root() / ".ai_quant" / "report_outputs"
    _env_out_dir = Path(str(os.getenv("AI_QUANT_REPORT_OUTPUT_DIR", "") or "").strip())
    out_dir = _env_out_dir if _env_out_dir.exists() and os.access(_env_out_dir, os.W_OK) else _default_out_dir
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


@router.get("/report-tasks/query")
def reports_query_tasks(
    status: str = Query(default="", description="按状态精确过滤（success/failed/running/waiting）"),
    model: str = Query(default="", description="按模型模糊过滤（如 deepseek/qwen）"),
    created_start: str = Query(default="", description="创建时间起点（ISO 格式，如 2026-01-01）"),
    created_end: str = Query(default="", description="创建时间终点（ISO 格式）"),
    limit: int = Query(default=50, ge=1, le=500, description="最大返回条数"),
) -> dict[str, Any]:
    """
    从 MySQL report_tasks 表查询研报任务（支持多条件筛选）。

    返回字段：id, created_at, status, report_path, model, use_rag, use_web,
              finish_time, stock_codes, stock_names, mode, error_message

    Args:
        status:        按状态精确过滤（success / failed / running / waiting）
        model:         按模型模糊过滤（LIKE %model%）
        created_start: 创建时间起点（ISO 格式）
        created_end:   创建时间终点（ISO 格式）
        limit:         最大返回条数（默认 50，最大 500）

    Returns:
        dict: 包含 tasks 列表和 total 计数
    """
    try:
        from infra.storage.report_store import query_report_tasks
    except Exception as e:
        logger.error("导入 query_report_tasks 失败: %s", e)
        raise HTTPException(status_code=500, detail="query not available")
    rows = query_report_tasks(
        status_filter=status or None,
        model_filter=model or None,
        created_start=created_start or None,
        created_end=created_end or None,
        limit=limit,
    )
    return ok({"tasks": rows, "total": len(rows)})


@router.get("/report-tasks/{task_id}/download")
def reports_download_task(task_id: str) -> Response:
    """
    获取研报文件的直接下载链接（302 重定向到实际文件路径）。

    Args:
        task_id: 任务 ID

    Returns:
        Response: 文件内容（text/markdown），不存在时 404
    """
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    path = task.report_path
    if not path:
        raise HTTPException(status_code=404, detail="report file not found")
    p = Path(path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="report file missing on disk")
    try:
        content = p.read_text(encoding="utf-8")
    except Exception:
        content = str(task.report_markdown or "")
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={p.name}",
            "X-Report-Path": str(p),
        },
    )
