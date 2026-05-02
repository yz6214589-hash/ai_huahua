# Charles 智能研报（DeepAgents 多 Agent + RAG）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Charles（[charles](file:///Users/apple/Desktop/ai_huahua/charles)）中新增“智能研报”能力：前端创建研报任务、查看任务列表与研报内容；后端用 DeepAgents 多 Agent 工作流生成研报，并支持 RAG 检索与联网搜索；LLM 支持 qwen-max / deepseek 可选。

**Architecture:** 后端新增 `reports` 子模块：负责（1）研报任务存储与查询（MySQL）、（2）RAG 索引构建与检索（FAISS + DashScope Embedding）、（3）多 Agent（Planner/Research/Writer/Reviewer）编排生成研报并持久化。前端新增“智能研报”页面：股票多选 + 模型选择创建任务，展示可筛选的任务列表，支持查看（新标签页打开 HTML 研报）与删除。

**Tech Stack:** FastAPI（已有）+ MySQL（已有）+ DeepAgents（新增）+ LangChain Community（新增：FAISS / Embeddings）+ DashScope（已有 key：enable_search + embedding）+ DeepSeek（OpenAI compatible，新增 env）+ React/Vite（已有）

---

## 一、代码结构（落地文件清单）

### 后端（FastAPI）

**新增：**
- `api/charles_api/reports/__init__.py`
- `api/charles_api/reports/models.py`：研报任务 Pydantic 模型（API 入参/出参）
- `api/charles_api/reports/store.py`：研报任务 MySQL 读写
- `api/charles_api/reports/llm.py`：qwen-max / deepseek LLM 初始化（ChatTongyi / OpenAI compatible）
- `api/charles_api/reports/tools.py`：@tool 工具：`web_search`（qwen enable_search）、`rag_search`（FAISS）
- `api/charles_api/reports/agents.py`：多 Agent 工厂（Planner / Research / Writer / Reviewer）
- `api/charles_api/reports/generator.py`：任务执行器：读取任务 → 生成研报 → 更新任务状态
- `api/charles_api/reports/preprocess.py`：参考课程 `preprocess.py` 的 PDF → SQLite + FAISS 索引脚本（路径改为 `api/data/...`）

**修改：**
- `api/charles_api/config.py`：新增 DeepSeek 相关 env + 研报 data_dir 配置
- `api/charles_api/app.py`：新增建表、API 路由（创建/列表/查看/删除/研报 HTML 查看），并复用 BackgroundTasks 执行生成
- `api/requirements.txt`：补齐 DeepAgents / LangChain / FAISS / PyPDF2 等依赖

### 前端（React）

**新增：**
- `web/src/pages/Reports.tsx`：智能研报页面（创建任务 + 任务列表 + 筛选 + 查看/删除）

**修改：**
- `web/src/App.tsx`：新增路由 `/reports`
- `web/src/components/AppShell.tsx`：侧边栏新增入口“智能研报”，Topbar 标题映射
- `web/src/api/types.ts`：新增 ReportTask 相关类型

---

## 二、数据与接口设计

### 2.1 MySQL 表：`trade_report_task`

在 `api/charles_api/app.py:create_app()` 的启动阶段创建（参考已有 `_ensure_*_table` 风格）：

```sql
CREATE TABLE IF NOT EXISTS trade_report_task (
  task_id varchar(32) NOT NULL,
  model varchar(32) NOT NULL,
  stock_codes_json text NOT NULL,
  stock_names_json text,
  status varchar(16) NOT NULL,
  created_at datetime DEFAULT CURRENT_TIMESTAMP,
  started_at datetime DEFAULT NULL,
  finished_at datetime DEFAULT NULL,
  error_message text,
  report_markdown longtext,
  PRIMARY KEY (task_id),
  KEY idx_report_task_created (created_at),
  KEY idx_report_task_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

字段含义：
- `task_id`：uuid hex
- `model`：`qwen-max` 或 `deepseek`
- `stock_codes_json`：`["600519.SH","688981.SH"]`
- `stock_names_json`：`["贵州茅台","中芯国际"]`（便于列表直接展示）
- `status`：`waiting | running | success | failed`
- `report_markdown`：最终研报 Markdown

### 2.2 后端 API（新增）

- `POST /api/reports/tasks`
  - 入参：`{ model: "qwen-max"|"deepseek", stock_codes: string[] }`
  - 返回：`{ task: ReportTask }`
  - 行为：写入 DB（status=waiting），后台触发生成（BackgroundTasks）

- `GET /api/reports/tasks`
  - query：
    - `q`：股票代码/公司名模糊过滤（前端“股票公司”筛选）
    - `created_start` / `created_end`：创建时间范围（ISO date，如 `2026-05-01`）
    - `limit`：默认 100
  - 返回：`{ tasks: ReportTask[] }`

- `GET /api/reports/tasks/{task_id}`
  - 返回：`{ task: ReportTask }`

- `DELETE /api/reports/tasks/{task_id}`
  - 返回：`{ ok: true }`

- `GET /api/reports/tasks/{task_id}/view`
  - 返回：`text/html`（新标签页打开），把 `report_markdown` 渲染为 HTML（建议用 `markdown` 包）

### 2.3 前端交互（新增页面 `/reports`）

创建任务区：
- 股票下拉搜索（支持多选）
- 模型下拉：`qwen-max` / `deepseek`
- 按钮：创建研报任务

任务列表区：
- 列字段：
  - 股票代码/公司名称（多选时用 `，` 拼接）
  - 创建时间
  - 生成时间（`finished_at`）
  - 状态（等待/完成/失败/运行中）
  - 操作：查看（新标签页打开）、删除
- 筛选：
  - 创建时间范围（start/end）
  - 股票公司（输入框 + 可选从 `/api/stocks` 选择；最终传 `q=`）

---

## 三、RAG（索引构建与检索）

### 3.1 目录约定（按你的选择：`charles/api/data`）

- PDF 放置：`/Users/apple/Desktop/ai_huahua/charles/api/data/reports/`
- 解析缓存：`/Users/apple/Desktop/ai_huahua/charles/api/data/parsed/`
- 向量索引：`/Users/apple/Desktop/ai_huahua/charles/api/data/vector_store/`
- SQLite 元数据库：`/Users/apple/Desktop/ai_huahua/charles/api/data/documents.db`

### 3.2 索引脚本（`api/charles_api/reports/preprocess.py`）

按课程 `preprocess.py` 结构迁移，主要改动：
- `PROJECT_ROOT` → `Path(__file__).resolve().parents[1]`（指向 `api/`）
- `REPORTS_DIR / PARSED_DIR / VECTOR_STORE_DIR / DB_PATH` 改为 `api/data/...`
- embedding 仍使用 `DashScopeEmbeddings(model="text-embedding-v4")`

运行方式（后续执行阶段再落地命令，不在本计划里强制写 README）：
- `python -m charles_api.reports.preprocess --rebuild`

### 3.3 RAG 检索工具（`rag_search`）

使用 `langchain_community.vectorstores.FAISS.load_local()` 加载索引：
- 检索：`similarity_search(query, k=6, filter={"stock_code": "600519"} )`（多股票则分别检索或不加 filter）
- 返回内容包含页码溯源：`title / source / publish_date / page`

---

## 四、多 Agent（DeepAgents）研报生成

### 4.1 LLM 支持与联网搜索策略

- 主模型可选：
  - `qwen-max`：使用 `ChatTongyi(model="qwen-max")`
  - `deepseek`：使用 `OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)` 的 chat.completions（OpenAI compatible）
- 联网搜索 `web_search` 工具：统一走 DashScope `enable_search=True`（即便主模型选 deepseek，也可调用该工具实现联网搜索能力）
- RAG embedding：DashScope `text-embedding-v4`

所需环境变量（在 `.env` 中新增）：
- `DASHSCOPE_API_KEY`（已有但可能为空：联网搜索 + embedding 必需）
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com/v1`）
- `DEEPSEEK_MODEL`（默认 `deepseek-chat`）
- `CHARLES_REPORT_DATA_DIR`（默认 `api/data`）

### 4.2 多 Agent 角色拆分（每个角色都是一个 DeepAgent）

- PlannerAgent：拆任务与信息需求（输出结构化 JSON：需要哪些搜索 query / RAG query）
- ResearchAgent：根据 Planner 输出，调用 `web_search`、`rag_search` 汇总素材
- WriterAgent：把素材写成 Markdown 研报（按“五步法”框架输出）
- ReviewerAgent：检查风险提示、时间表述、引用来源（返回修订版或校验结果）

编排器（`generator.py`）流程：
1) `PlannerAgent.invoke()` 得到计划（JSON）
2) `ResearchAgent.invoke()`（可把 JSON 计划作为输入，引导工具调用）
3) `WriterAgent.invoke()` 得到 `report_markdown`
4) `ReviewerAgent.invoke()` 得到最终 `report_markdown`（或保持原样）
5) DB 更新 task：`status=success/failed`、`finished_at`、`report_markdown`

---

## 五、任务拆解（可执行清单）

### Task 1: 后端配置与依赖

**Files:**
- Modify: `api/charles_api/config.py`
- Modify: `api/requirements.txt`

- [ ] Step 1: 扩展 Settings（DeepSeek + report data dir）

```python
# api/charles_api/config.py
@dataclass(frozen=True)
class Settings:
    ...
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    report_data_dir: str
```

```python
def load_settings() -> Settings:
    ...
    return Settings(
        ...
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        report_data_dir=os.getenv("CHARLES_REPORT_DATA_DIR", os.path.join(os.getcwd(), "api", "data")),
    )
```

- [ ] Step 2: requirements 增加依赖（以最小闭环为目标）

```txt
# api/requirements.txt 增量追加（不要删除现有）
deepagents==0.0.0
langchain-community==0.3.0
langchain-core==0.3.0
langgraph==0.2.0
langchain-text-splitters==0.3.0
PyPDF2==3.0.1
faiss-cpu==1.8.0
markdown==3.7
```

> 版本号在执行阶段需要根据实际 pip 可用性做一次校准（以当前 pip 能装上为准）。

---

### Task 2: 研报任务模型与存储（MySQL）

**Files:**
- Create: `api/charles_api/reports/models.py`
- Create: `api/charles_api/reports/store.py`
- Modify: `api/charles_api/app.py`（建表 + CRUD API）

- [ ] Step 1: 新增 Pydantic 模型（后端内部）

```python
# api/charles_api/reports/models.py
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ReportModel(str, Enum):
    qwen_max = "qwen-max"
    deepseek = "deepseek"


class ReportTaskStatus(str, Enum):
    waiting = "waiting"
    running = "running"
    success = "success"
    failed = "failed"


class ReportTaskCreateRequest(BaseModel):
    model: ReportModel
    stock_codes: list[str] = Field(min_length=1)


class ReportTask(BaseModel):
    task_id: str
    model: ReportModel
    stock_codes: list[str]
    stock_names: list[str] = Field(default_factory=list)
    status: ReportTaskStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None
```

- [ ] Step 2: MySQL store 封装（不在 app.py 写长 SQL）

```python
# api/charles_api/reports/store.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..db import MySQLConfig, execute, query_dict
from .models import ReportModel, ReportTask, ReportTaskStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_task_id() -> str:
    return uuid4().hex


def create_task(
    conn,
    *,
    model: ReportModel,
    stock_codes: list[str],
    stock_names: list[str],
) -> ReportTask:
    task_id = new_task_id()
    execute(
        conn,
        """
        INSERT INTO trade_report_task
          (task_id, model, stock_codes_json, stock_names_json, status, created_at)
        VALUES
          (%s,%s,%s,%s,%s,NOW())
        """,
        (
            task_id,
            model.value,
            json.dumps(stock_codes, ensure_ascii=False),
            json.dumps(stock_names, ensure_ascii=False),
            ReportTaskStatus.waiting.value,
        ),
    )
    rows = query_dict(conn, "SELECT * FROM trade_report_task WHERE task_id=%s", (task_id,))
    r = (rows or [])[0]
    return ReportTask(
        task_id=str(r["task_id"]),
        model=ReportModel(str(r["model"])),
        stock_codes=json.loads(r["stock_codes_json"] or "[]"),
        stock_names=json.loads(r.get("stock_names_json") or "[]") if r.get("stock_names_json") else [],
        status=ReportTaskStatus(str(r["status"])),
        created_at=r["created_at"].isoformat() if r.get("created_at") else _now_iso(),
        started_at=r["started_at"].isoformat() if r.get("started_at") else None,
        finished_at=r["finished_at"].isoformat() if r.get("finished_at") else None,
        error_message=r.get("error_message"),
    )
```

> list/get/delete/update 在同一文件按相同风格补齐（执行阶段写全）。

- [ ] Step 3: app.py 中新增建表与接口

在 `create_app()` 的 `_ensure_*_table` 区域增加：

```python
def _ensure_report_task_table() -> None:
    conn = connect(mysql_cfg)
    try:
        execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS trade_report_task (
              task_id varchar(32) NOT NULL,
              model varchar(32) NOT NULL,
              stock_codes_json text NOT NULL,
              stock_names_json text,
              status varchar(16) NOT NULL,
              created_at datetime DEFAULT CURRENT_TIMESTAMP,
              started_at datetime DEFAULT NULL,
              finished_at datetime DEFAULT NULL,
              error_message text,
              report_markdown longtext,
              PRIMARY KEY (task_id),
              KEY idx_report_task_created (created_at),
              KEY idx_report_task_status (status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """,
        )
        conn.commit()
    finally:
        conn.close()
```

然后在路由区增加 CRUD（执行阶段补齐完整实现）：
- `POST /api/reports/tasks`
- `GET /api/reports/tasks`
- `GET /api/reports/tasks/{task_id}`
- `DELETE /api/reports/tasks/{task_id}`

---

### Task 3: RAG（preprocess + 检索工具）

**Files:**
- Create: `api/charles_api/reports/preprocess.py`
- Create: `api/charles_api/reports/tools.py`

- [ ] Step 1: 把课程 `preprocess.py` 迁移到 `api/charles_api/reports/preprocess.py`

迁移规则：
- 只改路径常量和 `PROJECT_ROOT`，保留原始处理逻辑
- `REPORTS_DIR/PARSED_DIR/VECTOR_STORE_DIR/DB_PATH` 统一落在 `api/data`

- [ ] Step 2: 实现 `rag_search` 工具（FAISS）

```python
# api/charles_api/reports/tools.py
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.tools import tool


@lru_cache(maxsize=2)
def _load_vectorstore(index_dir: str):
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY required for embeddings")
    embeddings = DashScopeEmbeddings(model="text-embedding-v4", dashscope_api_key=api_key)
    return FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)


@tool
def rag_search(query: str, stock_codes: str = "", k: int = 6) -> str:
    index_dir = os.getenv("CHARLES_RAG_INDEX_DIR") or os.path.join(os.getcwd(), "api", "data", "vector_store")
    vs = _load_vectorstore(index_dir)
    codes = [c.strip() for c in (stock_codes or "").split(",") if c.strip()]
    docs = []
    if codes:
        for c in codes:
            docs.extend(vs.similarity_search(query, k=max(1, int(k)), filter={"stock_code": c}))
    else:
        docs = vs.similarity_search(query, k=max(1, int(k)))
    out = []
    for d in docs[: max(1, int(k))]:
        m = d.metadata or {}
        out.append(
            {
                "stock_code": m.get("stock_code"),
                "stock_name": m.get("stock_name"),
                "title": m.get("title"),
                "source": m.get("source"),
                "publish_date": m.get("publish_date"),
                "page": m.get("page"),
                "text": d.page_content,
            }
        )
    import json

    return json.dumps({"query": query, "hits": out}, ensure_ascii=False, indent=2)
```

---

### Task 4: 联网搜索工具（web_search）

**Files:**
- Modify: `api/charles_api/reports/tools.py`

- [ ] Step 1: 增加 `web_search`（复用课程 `search_market.py` 逻辑）

```python
from openai import OpenAI

@tool
def web_search(query: str, type: str = "general") -> str:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY required for web_search")
    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    resp = client.chat.completions.create(
        model=os.getenv("QWEN_MODEL", "qwen-max"),
        messages=[
            {"role": "system", "content": "你是专业投研助手，请基于联网搜索结果回答，并标注来源与时间。"},
            {"role": "user", "content": f"[{type}] {query}"},
        ],
        extra_body={"enable_search": True},
    )
    return resp.choices[0].message.content or ""
```

---

### Task 5: 多 Agent（DeepAgents）实现与编排

**Files:**
- Create: `api/charles_api/reports/llm.py`
- Create: `api/charles_api/reports/agents.py`
- Create: `api/charles_api/reports/generator.py`
- Modify: `api/charles_api/app.py`（任务创建后触发生成）

- [ ] Step 1: LLM 工厂（qwen-max / deepseek）

```python
# api/charles_api/reports/llm.py
from __future__ import annotations

import os

from langchain_community.chat_models.tongyi import ChatTongyi
from openai import OpenAI

from .models import ReportModel


def build_llm(model: ReportModel):
    if model == ReportModel.qwen_max:
        return ChatTongyi(model="qwen-max")
    if model == ReportModel.deepseek:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY required")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        return OpenAI(api_key=api_key, base_url=base_url), model_name
    raise RuntimeError("unknown model")
```

- [ ] Step 2: Agent 工厂

```python
# api/charles_api/reports/agents.py
from __future__ import annotations

from datetime import datetime

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from langgraph.checkpoint.memory import InMemorySaver

from .models import ReportModel
from .tools import rag_search, web_search
from .llm import build_llm


def _backend(root_dir: str):
    return LocalShellBackend(root_dir=root_dir, virtual_mode=True, inherit_env=True, timeout=300)


def build_agents(root_dir: str, model: ReportModel):
    today = datetime.now().strftime("%Y-%m-%d")
    tools = [web_search, rag_search]
    checkpointer = InMemorySaver()

    llm = build_llm(model)

    planner = create_deep_agent(
        model=llm,
        system_prompt=f"今天是 {today}。你是投研规划助手。输出 JSON: {{web_queries:[], rag_queries:[], outline:''}}",
        backend=_backend(root_dir),
        tools=tools,
        checkpointer=checkpointer,
    )
    researcher = create_deep_agent(
        model=llm,
        system_prompt=f"今天是 {today}。你是投研研究员，优先调用 web_search 与 rag_search 汇总证据。",
        backend=_backend(root_dir),
        tools=tools,
        checkpointer=checkpointer,
    )
    writer = create_deep_agent(
        model=llm,
        system_prompt=f"今天是 {today}。你是研报写作助手，按五步法输出 Markdown，并包含风险提示。",
        backend=_backend(root_dir),
        tools=tools,
        checkpointer=checkpointer,
    )
    reviewer = create_deep_agent(
        model=llm,
        system_prompt=f"今天是 {today}。你是研报审校助手，检查时间表述与风险提示，输出最终 Markdown。",
        backend=_backend(root_dir),
        tools=tools,
        checkpointer=checkpointer,
    )
    return planner, researcher, writer, reviewer
```

> 说明：若 deepseek 的 OpenAI client 不满足 `create_deep_agent` 期望（LangChain chat model），执行阶段将把 deepseek 封装为 LangChain compatible chat model（通过 langchain-openai），并把依赖加到 requirements。

- [ ] Step 3: generator 执行器（后台任务）

```python
# api/charles_api/reports/generator.py
from __future__ import annotations

import json
from datetime import datetime

from ..db import MySQLConfig, connect
from .agents import build_agents
from .models import ReportTaskStatus
from .store import get_task, update_task_running, update_task_success, update_task_failed


def run_report_task(mysql_cfg: MySQLConfig, *, task_id: str, root_dir: str) -> None:
    conn = connect(mysql_cfg)
    try:
        task = get_task(conn, task_id=task_id)
        update_task_running(conn, task_id=task_id)
        conn.commit()
    finally:
        conn.close()

    try:
        planner, researcher, writer, reviewer = build_agents(root_dir, task.model)

        prompt = f"为以下股票生成一份综合研报：{','.join(task.stock_codes)}。请覆盖基本面、行业、估值、风险。"
        plan_res = planner.invoke({"messages": [{"role": "user", "content": prompt}]})
        plan_text = plan_res.get("messages", [])[-1].content

        research_res = researcher.invoke({"messages": [{"role": "user", "content": f\"计划如下：\\n{plan_text}\\n请开始研究并输出素材。\"}]})
        research_text = research_res.get("messages", [])[-1].content

        draft_res = writer.invoke({"messages": [{"role": "user", "content": f\"素材如下：\\n{research_text}\\n请输出研报 Markdown。\"}]})
        draft_md = draft_res.get("messages", [])[-1].content

        final_res = reviewer.invoke({"messages": [{"role": "user", "content": f\"请审校以下研报并输出最终 Markdown：\\n{draft_md}\"}]})
        final_md = final_res.get("messages", [])[-1].content

        conn2 = connect(mysql_cfg)
        try:
            update_task_success(conn2, task_id=task_id, report_markdown=final_md)
            conn2.commit()
        finally:
            conn2.close()
    except Exception as e:
        conn3 = connect(mysql_cfg)
        try:
            update_task_failed(conn3, task_id=task_id, error_message=f\"{type(e).__name__}: {e}\")
            conn3.commit()
        finally:
            conn3.close()
```

---

### Task 6: 研报 HTML 查看（新标签页）

**Files:**
- Modify: `api/charles_api/app.py`

- [ ] Step 1: 增加 `/api/reports/tasks/{task_id}/view`

核心实现（示意）：

```python
from fastapi.responses import HTMLResponse
import markdown as _md

@app.get("/api/reports/tasks/{task_id}/view")
def report_view(task_id: str):
    conn = connect(mysql_cfg)
    try:
        rows = query_dict(conn, "SELECT report_markdown, status, error_message FROM trade_report_task WHERE task_id=%s", (task_id,))
        if not rows:
            raise HTTPException(status_code=404, detail="task not found")
        r = rows[0]
    finally:
        conn.close()

    md_text = str(r.get("report_markdown") or "")
    if not md_text:
        status = str(r.get("status") or "")
        err = str(r.get("error_message") or "")
        md_text = f"# 研报尚未生成\\n\\n状态：{status}\\n\\n{err}"

    body = _md.markdown(md_text, extensions=["tables", "fenced_code"])
    html = f\"\"\"<!doctype html>
<html><head><meta charset="utf-8" />
<title>Report {task_id}</title>
<style>
body{{font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial; padding:24px; max-width: 980px; margin:0 auto;}}
pre,code{{background:#f4f4f5;}}
pre{{padding:12px; overflow:auto;}}
table{{border-collapse:collapse; width:100%;}}
th,td{{border:1px solid #e4e4e7; padding:6px 8px;}}
</style></head><body>{body}</body></html>\"\"\"
    return HTMLResponse(content=html)
```

---

### Task 7: 前端页面（创建任务 + 列表 + 筛选 + 查看/删除）

**Files:**
- Create: `web/src/pages/Reports.tsx`
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/AppShell.tsx`
- Modify: `web/src/api/types.ts`

- [ ] Step 1: types.ts 增加类型

```ts
export type ReportModel = 'qwen-max' | 'deepseek'
export type ReportTaskStatus = 'waiting' | 'running' | 'success' | 'failed'

export interface ReportTask {
  task_id: string
  model: ReportModel
  stock_codes: string[]
  stock_names: string[]
  status: ReportTaskStatus
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
}
```

- [ ] Step 2: 新增页面 `Reports.tsx`（表格 + 过滤 + 新建）

页面要点（执行阶段写完整 TSX）：
- 复用 `/api/stocks?q=` 做股票搜索建议
- 维护 `selectedStocks: StockSearchItem[]`，渲染为可删除的 tag
- 创建任务：`POST /api/reports/tasks`
- 列表：`GET /api/reports/tasks?created_start=...&created_end=...&q=...`
- 查看：`window.open(/api/reports/tasks/${task_id}/view, '_blank')`
- 删除：`DELETE /api/reports/tasks/${task_id}`
- 定时刷新列表（例如 1500ms，与 Jobs 风格一致）

- [ ] Step 3: 路由与侧边栏

```tsx
// web/src/App.tsx
<Route path="/reports" element={<Reports />} />
```

```ts
// web/src/components/AppShell.tsx Sidebar items 增加
{ to: '/reports', label: '智能研报', icon: FileText }
```

并在 Topbar title 映射里增加 `/reports`。

---

## 六、验证方式（执行阶段做最小闭环验证）

- 后端：
  - `GET /api/health` 仍为 ok
  - `POST /api/reports/tasks` 创建任务后，`GET /api/reports/tasks` 能看到 status 从 waiting → running → success/failed
  - `GET /api/reports/tasks/{id}/view` 可打开 HTML
- 前端：
  - `/reports` 页面可创建任务、列表刷新、筛选、查看新标签页、删除

---

## 七、规格自检（覆盖需求）

- 多 agent：Planner/Research/Writer/Reviewer 四个 DeepAgents
- 模型选择：前端下拉 `qwen-max/deepseek`，后端按 task.model 选择
- deepseek 联网搜索：通过工具 `web_search` 使用 qwen enable_search 提供联网能力（deepseek 作为主写作模型）
- RAG：FAISS 索引 + `rag_search` 工具；索引脚本从课程 preprocess 迁移
- 前端交互：股票多选创建任务；任务列表含字段与筛选；查看新标签页；删除

---

Plan complete and saved to `docs/superpowers/plans/2026-05-02-charles-smart-report.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

