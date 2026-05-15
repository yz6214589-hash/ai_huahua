# 智能研报模块重构方案：改为 DeepAgent + Skills 模式

> **目标**：将 `api/reports.py` 的研报生成核心（`_generate_report_markdown`），从"直接调 DashScope LLM + 手拼 Prompt"改为"调用 DeepAgent Engine 驱动 Agent自主规划 + Skills 工具链"模式。
>
> **参考**：`/Users/apple/Desktop/ai_huahua/参考代码/CASE-智能研报生成/agent.py` + `/Users/apple/Desktop/ai_huahua/ai_quant/backend/llm/deepagent_engine.py` + 现有 Skills

---

## 一、现有架构 vs 目标架构

### 现有架构（要改的部分）

```
前端 POST /api/v1/reports/tasks
  └─ reports_create_task()
       └─ Worker._process_task()
            └─ _generate_report_markdown()       ← 替换目标
                 ├─ 读 MySQL (行情/财务/新闻)
                 ├─ 调 rag_query()              ← 复用
                 ├─ 拼 Prompt (system + user)
                 └─ _dashscope_generate()        ← 替换为 DeepAgent
```

### 目标架构（替换后）

```
前端 POST /api/v1/reports/tasks
  └─ reports_create_task()
       └─ Worker._process_task()
            └─ _generate_report_markdown()       ← 替换实现
                 └─ run_deepagent()             ← 新增
                      ├─ system_prompt（含五步法）
                      ├─ TOOLS=[
                      │    web_search        ← skills/web-search/scripts/search_market.py
                      │    query_pdf          ← skills/read-pdf/scripts/query_report.py
                      │    stock_price        ← skills/stock-price/scripts/get_kline.py
                      │    financial_analysis ← skills/financial-analysis/scripts/ratio_analysis.py
                      │    compare_period     ← skills/compare-reports/scripts/cross_period.py
                      │    compare_company   ← skills/compare-reports/scripts/cross_company.py
                      │    sentiment          ← skills/sentiment-analysis/
                      │   ]
                      └─ 返回 Markdown 研报文本
```

---

## 二、文件变更清单

| 操作 | 文件 | 改动说明 |
|------|------|---------|
| **修改** | `api/reports.py` | `_generate_report_markdown` 改为调用 `run_deepagent()` |
| **新增** | `llm/skills/report-agent/agent.py` | 研报专用 Agent（参考 CASE-智能研报生成/agent.py） |
| **新增** | `llm/skills/report-agent/scripts/run_report.py` | CLI 入口，被 DeepAgent 的 subprocess 调用 |
| **修改** | `llm/deepagent_engine.py` | 暴露 `run_report_agent(stock_codes, model)` 函数给 reports.py 调用 |
| **复用** | `infra/storage/report_store.py` | 任务管理不变 |
| **复用** | `infra/reports/rag.py` | RAG 检索不变（作为 query_pdf 底层） |
| **复用** | `llm/skills/write-report/` | 五步法 Prompt 模板复用 |
| **复用** | `llm/skills/web-search/` | 联网搜索工具 |
| **复用** | `llm/skills/stock-price/` | K线获取工具 |
| **复用** | `llm/skills/financial-analysis/` | 财务分析工具 |
| **复用** | `llm/skills/compare-reports/` | 跨期/跨公司对比工具 |
| **复用** | `llm/skills/sentiment-analysis/` | 舆情分析工具 |

---

## 三、核心实现细节

### 3.1 新增 `llm/skills/report-agent/agent.py`

```python
# 参考 CASE-智能研报生成/agent.py 的 create_charles_agent()
# 差异：
#   1. system_prompt 改为"针对单只股票生成研报"
#   2. tool 列表复用 llm/skills 下所有已实现的脚本工具
#   3. Backend 改为 LocalShellBackend，继承 /Users/apple/Desktop/ai_huahua/ai_quant 环境变量
#   4. 输出 JSON 协议: {"action":"final","text":"<markdown>"}

def create_report_agent(model=None, checkpointer=None):
    backend = LocalShellBackend(
        root_dir=str(Path(__file__).resolve().parent.parent.parent.parent),
        virtual_mode=True,
        inherit_env=True,
        timeout=300,
    )
    system_prompt = _build_report_prompt()  # 五步法 + 研报格式约束
    llm = ChatTongyi(model=model or os.getenv("CHARLES_MODEL","qwen-plus"))
    agent = create_deep_agent(
        model=llm,
        system_prompt=system_prompt,
        backend=backend,
        tools=REPORT_TOOLS,  # web_search, query_pdf, stock_price...
        checkpointer=checkpointer or InMemorySaver(),
    )
    return agent
```

### 3.2 `llm/deepagent_engine.py` 暴露接口

```python
# 新增函数，给 reports.py 调用
def run_report_agent(stock_codes: list[str], stock_names: list[str], model: str) -> str:
    """
    运行研报 Agent，返回 Markdown 研报文本。
    使用 thread_id = f"report_{stock_codes[0]}" 确保每次调用独立。
    """
    agent = create_report_agent(model=model)
    thread_id = f"report_{stock_codes[0]}"
    config = {"configurable": {"thread_id": thread_id}}
    user_prompt = f"请对以下股票进行深度研报分析：{stock_names[0]}({stock_codes[0]})"
    result = agent.invoke({"messages": [HumanMessage(content=user_prompt)]}, config)
    return _extract_final_text(result)
```

### 3.3 `api/reports.py` 改动

```python
# 替换 _generate_report_markdown() 内部逻辑
# 原来：拼 Prompt → 调 DashScope → 返回 Markdown
# 改为：调 run_report_agent(stock_codes, stock_names, model) → 返回 Markdown

def _generate_report_markdown(stock_codes, stock_names, use_rag, model):
    # 1. 简单前置检查（API Key 等）
    if not (os.getenv("DASHSCOPE_API_KEY") or "").strip():
        return _builtin_report_markdown(...)  # fallback

    # 2. 调用 DeepAgent（替代原来直接调 LLM）
    report_text = run_report_agent(
        stock_codes=stock_codes,
        stock_names=stock_names,
        model=model,
    )

    # 3. 若 Agent 未返回内容，fallback 到内置模板
    if not report_text or len(report_text) < 100:
        return _builtin_report_markdown(...)

    return report_text
```

### 3.4 工具映射（@tool → 脚本）

| @tool 函数 | 脚本路径 | 说明 |
|-----------|---------|------|
| `web_search` | `skills/web-search/scripts/search_market.py` | 联网搜索 |
| `query_pdf` | `skills/read-pdf/scripts/query_report.py` | RAG 检索 |
| `stock_price` | `skills/stock-price/scripts/get_kline.py` | 实时K线 |
| `financial_analysis` | `skills/financial-analysis/scripts/ratio_analysis.py` | 财务指标 |
| `compare_reports_period` | `skills/compare-reports/scripts/cross_period.py` | 跨期对比 |
| `compare_reports_company` | `skills/compare-reports/scripts/cross_company.py` | 跨公司对比 |
| `sentiment_scan` | `skills/sentiment-analysis/scripts/sentiment_scorer.py` | 舆情评分 |

---

## 四、执行计划

### 阶段一：搭建 Agent 框架（不改现有逻辑）

**Task 1**：创建 `llm/skills/report-agent/` 目录结构

```
llm/skills/report-agent/
├── agent.py          # Agent 定义（参考 CASE-智能研报生成）
├── scripts/
│   └── run_report.py # CLI 入口
└── SKILL.md         # 元数据
```

**Task 2**：实现 `agent.py` 中的工具注册

- 复用 `llm/skills/` 下已有脚本，用 `@tool` 装饰器包装
- 构造五步法 system_prompt

**Task 3**：验证 `agent.py` 独立可运行

```bash
cd llm/skills/report-agent
python agent.py --stock 600519.SH
# 期望：输出 Markdown 格式研报
```

### 阶段二：集成到 DeepAgent Engine

**Task 4**：在 `llm/deepagent_engine.py` 新增 `run_report_agent()`

- 接受 `stock_codes / stock_names / model` 参数
- 构造 user_prompt，调用 agent
- 提取 `{"action":"final","text":"..."}` 中的 text

**Task 5**：改造 `api/reports.py` 的 `_generate_report_markdown`

- 保留 MySQL 读行情逻辑（用于 fallback）
- 替换 LLM 调用为 `run_report_agent()`
- 保留异常处理（Agent 超时 → 内置模板 fallback）

### 阶段三：适配与回归测试

**Task 6**：确保现有 API 兼容

- `/api/v1/reports/tasks` 入参不变
- `/api/v1/reports/tasks/{id}/view` 返回格式兼容
- Worker 超时逻辑保持（300s）

**Task 7**：端到端测试

```bash
# 创建研报任务
curl -X POST http://localhost:8000/api/v1/reports/tasks \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen-plus","stock_codes":["000032.SZ"],"use_rag":true}'

# 等待后查看结果
curl http://localhost:8000/api/v1/reports/tasks
```

---

## 五、风险与备选

| 风险 | 应对 |
|------|------|
| Agent 调用超时（300s） | 保留 `_builtin_report_markdown()` 作为兜底 |
| 工具脚本未实现 | 先实现核心工具（web_search + query_pdf + stock_price），其他 fallback 到手动拼数据 |
| 模型幻觉严重 | system_prompt 约束"必须调用工具获取数据，不得捏造数字" |
| 流式输出不支持 | 先做非流式（DeepAgent 返回完整文本），后续再加 SSE |
