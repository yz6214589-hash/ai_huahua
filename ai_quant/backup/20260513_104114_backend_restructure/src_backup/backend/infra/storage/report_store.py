"""
报告任务存储模块

本模块负责管理量化报告生成任务的全生命周期，包括:
- 任务创建、状态跟踪和更新
- 任务数据在本地文件系统中的持久化存储
- 可选的MySQL数据库备份存储
- 从现有的报告输出和日志文件中引导加载历史任务

支持功能:
- 并发安全的任务读写操作(使用线程锁)
- 自动从文件系统和日志中恢复任务状态
- 支持RAG增强的报告生成模式
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from threading import Lock
from typing import Any
from uuid import uuid4
import os
import json
from pathlib import Path
import re


@dataclass
class ReportTaskRecord:
    """
    报告任务记录数据类
    
    用于存储单个量化报告生成任务的完整信息，包括:
    - 任务标识和基本信息
    - 股票代码和名称
    - 任务执行状态
    - 时间戳信息
    - 报告内容和路径
    - 错误信息(如果任务失败)
    """
    task_id: str
    model: str
    stock_codes: list[str]
    stock_names: list[str]
    use_rag: bool
    status: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
    error_location: str | None = None
    report_path: str | None = None
    report_markdown: str | None = None


# 内存中的任务存储字典,key为task_id
_TASKS: dict[str, ReportTaskRecord] = {}
# 线程锁,保证并发访问_TASKS时的数据一致性
_LOCK = Lock()
# 标记是否已从磁盘加载过任务数据,避免重复加载
_LOADED = False
# 标记MySQL表是否已初始化,避免重复创建表
_MYSQL_READY = False


def _project_root() -> Path:
    """
    获取项目根目录路径
    
    通过当前文件路径向上查找4层目录得到项目根目录
    
    Returns:
        Path: 项目根目录的Path对象
    """
    return Path(__file__).resolve().parents[3]


def _store_dir() -> Path:
    """
    获取任务存储目录路径
    
    优先使用环境变量AI_QUANT_REPORT_TASK_STORE_DIR指定的目录,
    如果未设置则使用项目根目录下的.ai_quant/report_tasks目录
    
    Returns:
        Path: 任务存储目录路径
    """
    # 优先使用环境变量指定的目录
    env = str(os.getenv("AI_QUANT_REPORT_TASK_STORE_DIR", "") or "").strip()
    if env:
        return Path(env)
    # 默认使用项目根目录下的.ai_quant/report_tasks目录
    return _project_root() / ".ai_quant" / "report_tasks"


def _task_path(task_id: str) -> Path:
    """
    获取指定任务ID对应的JSON文件路径
    
    Args:
        task_id: 任务唯一标识符
        
    Returns:
        Path: 任务JSON文件的完整路径
    """
    return _store_dir() / f"{task_id}.json"


def _mysql_enabled() -> bool:
    """
    检查MySQL存储是否启用
    
    通过环境变量AI_QUANT_REPORT_MYSQL_ENABLED控制,
    默认启用(值为1或true时启用)
    
    Returns:
        bool: MySQL存储是否启用
    """
    raw = str(os.getenv("AI_QUANT_REPORT_MYSQL_ENABLED", "1") or "").strip()
    return raw not in ("0", "false", "False")


def _to_mysql_dt(v: str | None) -> str | None:
    """
    将ISO格式时间字符串转换为MySQL DATETIME格式
    
    将ISO格式(如2024-01-01T10:30:00)转换为MySQL DATETIME格式(如2024-01-01 10:30:00)
    
    Args:
        v: ISO格式的时间字符串或None
        
    Returns:
        MySQL DATETIME格式的字符串或None
    """
    s = str(v or "").strip()
    if not s:
        return None
    # 将ISO格式中的T替换为空格
    if "T" in s:
        s = s.replace("T", " ")
    # 只保留前19个字符(Y-m-d H:M:S格式)
    return s[:19]


def _ensure_mysql_table(conn) -> None:
    """
    确保MySQL中的任务表已创建
    
    如果表不存在则创建ai_quant_report_tasks表,
    该表用于备份和持久化任务记录
    
    Args:
        conn: MySQL数据库连接对象
    """
    global _MYSQL_READY
    # 已初始化则跳过
    if _MYSQL_READY:
        return
    from src.backend..infra.storage.database import execute

    # 创建任务表的SQL语句,包含所有必要字段和索引
    sql = """
    CREATE TABLE IF NOT EXISTS ai_quant_report_tasks (
      task_id VARCHAR(64) NOT NULL,
      model VARCHAR(32) NOT NULL,
      stock_codes TEXT NULL,
      stock_names TEXT NULL,
      use_rag TINYINT(1) NOT NULL DEFAULT 1,
      status VARCHAR(16) NOT NULL,
      created_at DATETIME NOT NULL,
      started_at DATETIME NULL,
      finished_at DATETIME NULL,
      error_message TEXT NULL,
      error_location VARCHAR(256) NULL,
      report_path VARCHAR(512) NULL,
      updated_at DATETIME NOT NULL,
      PRIMARY KEY (task_id),
      KEY idx_status (status),
      KEY idx_created_at (created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """
    execute(conn, sql)
    # 标记已初始化,避免重复创建
    _MYSQL_READY = True


def _mysql_upsert(rec: ReportTaskRecord) -> None:
    """
    将任务记录插入或更新到MySQL数据库
    
    使用INSERT...ON DUPLICATE KEY UPDATE实现upsert语义,
    如果任务ID已存在则更新,否则插入新记录
    
    Args:
        rec: 要插入或更新的任务记录
    """
    # MySQL未启用时直接返回
    if not _mysql_enabled():
        return
    try:
        from src.backend..infra.storage.database import connect, execute, load_mysql_config

        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return
    try:
        # 确保表存在
        _ensure_mysql_table(conn)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # 构建upsert SQL,使用占位符避免SQL注入
        sql = """
        INSERT INTO ai_quant_report_tasks
          (task_id, model, stock_codes, stock_names, use_rag, status, created_at, started_at, finished_at, error_message, error_location, report_path, updated_at)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
          model=VALUES(model),
          stock_codes=VALUES(stock_codes),
          stock_names=VALUES(stock_names),
          use_rag=VALUES(use_rag),
          status=VALUES(status),
          created_at=VALUES(created_at),
          started_at=VALUES(started_at),
          finished_at=VALUES(finished_at),
          error_message=VALUES(error_message),
          error_location=VALUES(error_location),
          report_path=VALUES(report_path),
          updated_at=VALUES(updated_at)
        """
        execute(
            conn,
            sql,
            (
                rec.task_id,
                rec.model or "",
                # 将列表序列化为JSON字符串存储
                json.dumps(rec.stock_codes or [], ensure_ascii=False),
                json.dumps(rec.stock_names or [], ensure_ascii=False),
                # 布尔值转换为0/1
                1 if rec.use_rag else 0,
                rec.status or "",
                _to_mysql_dt(rec.created_at) or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                _to_mysql_dt(rec.started_at),
                _to_mysql_dt(rec.finished_at),
                rec.error_message,
                rec.error_location,
                rec.report_path,
                now,
            ),
        )
    except Exception:
        return
    finally:
        # 确保连接关闭
        conn.close()


def _mysql_delete(task_id: str) -> None:
    """
    从MySQL数据库中删除指定任务记录
    
    Args:
        task_id: 要删除的任务ID
    """
    if not _mysql_enabled():
        return
    try:
        from src.backend..infra.storage.database import connect, execute, load_mysql_config

        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return
    try:
        _ensure_mysql_table(conn)
        # 使用参数化查询防止SQL注入
        execute(conn, "DELETE FROM ai_quant_report_tasks WHERE task_id=%s", (task_id,))
    except Exception:
        return
    finally:
        conn.close()


def _load_once() -> None:
    """
    从磁盘加载任务数据到内存(仅执行一次)
    
    执行一次性加载:
    1. 清空内存中的任务列表
    2. 从存储目录加载所有JSON任务文件
    3. 如果启用了引导模式,还会从报告输出和日志中补充加载历史任务
    """
    global _LOADED
    # 已加载则跳过,避免重复加载
    if _LOADED:
        return
    _TASKS.clear()
    root = _store_dir()
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)

    # 遍历存储目录下的所有JSON文件
    for p in root.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        tid = str(data.get("task_id") or "").strip()
        if not tid:
            continue
        # 从JSON数据构造ReportTaskRecord对象
        rec = ReportTaskRecord(
            task_id=tid,
            model=str(data.get("model") or ""),
            stock_codes=list(data.get("stock_codes") or []),
            stock_names=list(data.get("stock_names") or []),
            use_rag=bool(data.get("use_rag", True)),
            status=str(data.get("status") or "waiting"),
            created_at=str(data.get("created_at") or now_iso()),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            error_message=data.get("error_message"),
            error_location=data.get("error_location"),
            report_path=data.get("report_path"),
            report_markdown=data.get("report_markdown"),
        )
        _TASKS[tid] = rec

    # 检查是否启用引导模式(默认启用)
    try:
        bootstrap = str(os.getenv("AI_QUANT_REPORT_STORE_BOOTSTRAP", "1")).strip() not in ("0", "false", "False")
    except Exception:
        bootstrap = True
    # 从报告输出和日志中引导加载历史任务
    if bootstrap:
        _bootstrap_from_outputs_and_log()
    _LOADED = True


def _bootstrap_from_outputs_and_log() -> None:
    """
    从报告输出目录和日志文件引导加载历史任务
    
    扫描以下位置以发现历史任务:
    1. 项目根目录和上级目录下的.ai_quant/report_outputs目录中的Markdown报告
    2. .ai_quant/reports_worker.log日志文件中的任务执行记录
    
    从日志中解析任务失败记录并补充缺失的任务信息
    """
    primary_root = _project_root()
    candidate_roots = [primary_root]
    try:
        # 同时检查上级目录,以便发现更多历史任务
        parent = primary_root.parent
        if parent and parent not in candidate_roots:
            candidate_roots.append(parent)
    except Exception:
        pass

    def _iso_from_mtime(path: Path) -> str:
        """
        从文件修改时间生成ISO格式时间字符串
        
        Args:
            path: 文件路径
            
        Returns:
            ISO格式的时间字符串
        """
        try:
            ts = path.stat().st_mtime
            return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
        except Exception:
            return now_iso()

    # 遍历可能的项目根目录
    for project_root in candidate_roots:
        outputs_dir = project_root / ".ai_quant" / "report_outputs"
        log_file = project_root / ".ai_quant" / "reports_worker.log"

        # 处理报告输出目录中的Markdown文件
        if outputs_dir.exists():
            for md in outputs_dir.glob("*.md"):
                tid = md.stem.strip()
                if not tid:
                    continue
                try:
                    content = md.read_text(encoding="utf-8")
                except Exception:
                    content = ""
                created = _iso_from_mtime(md)
                # 如果任务已存在,尝试补充报告内容
                if tid in _TASKS:
                    rec = _TASKS[tid]
                    if rec.status == "success" and (rec.report_markdown is None or str(rec.report_markdown) == ""):
                        if content.strip():
                            # 成功状态但缺少报告内容,补充内容
                            rec.report_markdown = content
                            rec.started_at = rec.started_at or created
                            rec.finished_at = rec.finished_at or created
                            _persist(rec, mysql=False)
                        else:
                            # 报告文件为空,标记为失败
                            rec.status = "failed"
                            rec.error_message = rec.error_message or "report file empty"
                            _persist(rec, mysql=False)
                    continue

                # 创建新任务记录
                rec2 = ReportTaskRecord(
                    task_id=tid,
                    model="",
                    stock_codes=[],
                    stock_names=[],
                    use_rag=True,
                    status="success" if content.strip() else "failed",
                    created_at=created,
                    started_at=created,
                    finished_at=created,
                    error_message=None if content.strip() else "report file empty",
                    error_location=None,
                    report_path=str(md),
                    report_markdown=content if content.strip() else None,
                )
                _TASKS[tid] = rec2
                _persist(rec2, mysql=False)

        # 处理日志文件,解析任务执行记录
        if log_file.exists():
            try:
                lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                lines = []

            # 定义日志解析正则表达式
            # 匹配任务失败日志
            re_failed = re.compile(r"^\[(?P<ts>[0-9:\-\s]+)\].*?\[reports\]\s+task_failed\s+task_id=(?P<id>[0-9a-f]{16,64})\s+(?P<msg>.*)$")
            # 匹配任务开始执行日志
            re_enter = re.compile(r"^\[(?P<ts>[0-9:\-\s]+)\].*?\[reports\]\s+_generate_report_markdown enter\s+model=(?P<model>\S+)\s+stock_code=(?P<code>\S+)\s+stock_name=(?P<name>\S+)(?:\s+.*)?$")

            # 记录最近一次任务元数据,用于失败记录补充
            last_meta_by_task: dict[str, dict[str, str]] = {}
            for ln in lines:
                # 解析任务开始日志,记录元数据
                m2 = re_enter.search(ln)
                if m2:
                    meta = {"model": m2.group("model"), "code": m2.group("code"), "name": m2.group("name"), "ts": m2.group("ts").strip()}
                    last_meta_by_task["_last"] = meta
                    continue

                # 解析任务失败日志
                m = re_failed.search(ln)
                if not m:
                    continue
                tid = m.group("id")
                msg = (m.group("msg") or "").strip()
                ts = m.group("ts").strip()
                # 获取最近的任务元数据
                meta = last_meta_by_task.get("_last") or {}
                created = ts.replace(" ", "T") if len(ts) >= 10 else now_iso()
                
                # 如果任务已存在,更新其状态
                if tid in _TASKS:
                    rec = _TASKS[tid]
                    changed = False
                    # 补充缺失的模型信息
                    if (not rec.model) and str(meta.get("model") or "").strip():
                        rec.model = str(meta.get("model") or "")
                        changed = True
                    if (not rec.stock_codes) and str(meta.get("code") or "").strip():
                        rec.stock_codes = [str(meta.get("code") or "")]
                        changed = True
                    if (not rec.stock_names) and str(meta.get("name") or "").strip():
                        rec.stock_names = [str(meta.get("name") or "")]
                        changed = True
                    # 检查报告是否为空
                    if rec.status == "success" and (rec.report_markdown is None or str(rec.report_markdown) == ""):
                        rec.status = "failed"
                        rec.error_message = rec.error_message or "report empty"
                        changed = True
                    # 标记为失败状态
                    if rec.status != "failed":
                        rec.status = "failed"
                        changed = True
                    # 补充错误信息
                    if not rec.error_message:
                        rec.error_message = msg or "failed"
                        changed = True
                    # 保存更改
                    if changed:
                        rec.created_at = rec.created_at or created
                        rec.started_at = created
                        rec.finished_at = created
                        _persist(rec, mysql=False)
                    continue

                # 创建失败任务记录
                rec2 = ReportTaskRecord(
                    task_id=tid,
                    model=str(meta.get("model") or ""),
                    stock_codes=[str(meta.get("code") or "")] if str(meta.get("code") or "").strip() else [],
                    stock_names=[str(meta.get("name") or "")] if str(meta.get("name") or "").strip() else [],
                    use_rag=True,
                    status="failed",
                    created_at=created,
                    started_at=created,
                    finished_at=created,
                    error_message=msg or "failed",
                    error_location=None,
                    report_path=None,
                    report_markdown=None,
                )
                _TASKS[tid] = rec2
                _persist(rec2, mysql=False)


def _persist(rec: ReportTaskRecord, *, mysql: bool = True) -> None:
    """
    将任务记录持久化到磁盘(以及可选的MySQL)
    
    使用原子写入操作确保数据一致性:
    1. 先写入临时文件
    2. 然后原子替换目标文件
    
    Args:
        rec: 要持久化的任务记录
        mysql: 是否同时同步到MySQL数据库,默认True
    """
    root = _store_dir()
    root.mkdir(parents=True, exist_ok=True)
    p = _task_path(rec.task_id)
    # 先写入临时文件,避免写入过程中读取到不完整数据
    tmp = p.with_name(f".{p.name}.tmp")
    tmp.write_text(json.dumps(asdict(rec), ensure_ascii=False, default=str), encoding="utf-8")
    # 原子替换为目标文件
    tmp.replace(p)
    # 可选:同步到MySQL
    if mysql:
        _mysql_upsert(rec)


def now_iso() -> str:
    """
    获取当前时间的ISO格式字符串
    
    Returns:
        当前时间的ISO 8601格式字符串,精确到秒
    """
    return datetime.now().isoformat(timespec="seconds")


def create_task(model: str, stock_codes: list[str], stock_names: list[str], use_rag: bool = True) -> ReportTaskRecord:
    """
    创建新的报告生成任务
    
    Args:
        model: 使用的AI模型名称
        stock_codes: 股票代码列表
        stock_names: 股票名称列表
        use_rag: 是否使用RAG增强,默认True
        
    Returns:
        创建的任务记录对象
    """
    # 生成唯一任务ID
    task_id = uuid4().hex
    rec = ReportTaskRecord(
        task_id=task_id,
        model=model,
        stock_codes=list(stock_codes),
        stock_names=list(stock_names),
        use_rag=bool(use_rag),
        status="waiting",
        created_at=now_iso(),
    )
    # 使用锁保证并发安全
    with _LOCK:
        _load_once()
        _TASKS[task_id] = rec
        _persist(rec, mysql=True)
    return rec


def update_task(task_id: str, **patch: Any) -> ReportTaskRecord | None:
    """
    更新指定任务的字段
    
    Args:
        task_id: 要更新的任务ID
        **patch: 要更新的字段名和值的键值对
        
    Returns:
        更新后的任务记录,如果任务不存在则返回None
    """
    with _LOCK:
        _load_once()
        rec = _TASKS.get(task_id)
        if rec is None:
            return None
        # 只更新存在于dataclass中的字段
        for k, v in patch.items():
            if hasattr(rec, k):
                setattr(rec, k, v)
        _persist(rec, mysql=True)
        return rec


def get_task(task_id: str) -> ReportTaskRecord | None:
    """
    获取指定任务ID的任务记录
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务记录对象,如果不存在则返回None
    """
    with _LOCK:
        _load_once()
        return _TASKS.get(task_id)


def delete_task(task_id: str) -> bool:
    """
    删除指定任务
    
    同时删除内存中的记录、磁盘文件以及MySQL中的记录
    
    Args:
        task_id: 要删除的任务ID
        
    Returns:
        是否成功删除
    """
    with _LOCK:
        _load_once()
        ok = _TASKS.pop(task_id, None) is not None
        if ok:
            try:
                # 删除磁盘上的JSON文件
                _task_path(task_id).unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass
            # 删除MySQL中的记录
            _mysql_delete(task_id)
        return ok


def list_tasks() -> list[dict[str, Any]]:
    """
    列出所有任务记录
    
    按创建时间倒序排列(最新的在前)
    
    Returns:
        任务记录列表,每个记录为字典格式
    """
    with _LOCK:
        _load_once()
        items = list(_TASKS.values())
    # 按创建时间倒序排列
    items.sort(key=lambda x: x.created_at, reverse=True)
    return [asdict(x) for x in items]
