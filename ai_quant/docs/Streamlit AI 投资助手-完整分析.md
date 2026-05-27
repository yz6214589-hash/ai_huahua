# Streamlit "AI 投资助手" 完整分析

## 一、定位与架构

Streamlit "AI 投资助手" 是一个**独立的对话机器人前端界面**，与 React SPA 共享同一后端 FastAPI 服务，通过 HTTP/SSE 通信。它专注于提供纯对话式的 AI 交互体验。

```
用户浏览器 (Streamlit Web UI - 端口 8501)
        |
        | SSE (Server-Sent Events)
        v
+--------------------------------------------------+
|           后端 FastAPI (端口 8000)                  |
|                                                    |
|  POST /api/v1/agent/stream                        |
|  POST /api/v1/agent/run                           |
|  GET/POST/DELETE /api/v1/conversations/*          |
|                                                    |
|  +-----------+  +----------+  +-----------------+ |
|  |Router Agent|  |晨会工作流  |  | DeepAgent      | |
|  | (意图路由)  |  |(LangGraph)|  | (通用智能体)    | |
|  +-----------+  +----------+  +-----------------+ |
+--------------------------------------------------+
```

**与 React SPA 的关系**:

| 对比项 | Streamlit "AI 投资助手" | React SPA (Web 前端) |
|--------|----------------------|---------------------|
| **定位** | 纯对话机器人界面 | 完整的量化交易管理后台 |
| **交互** | 对话式（聊天界面） | 页面式（导航+表格+图表） |
| **调用的后端接口** | 仅 `agent` + `conversation` 路由 | 全部 26 个路由 |
| **是否可独立运行** | 是 (依赖后端) | 是 (依赖后端) |
| **启动端口** | 8501 | 5173 |
| **启动命令** | `streamlit run app.py --server.port 8501` | `npm run dev` |

两者**共享同一后端** FastAPI 服务，只是前端界面不同:
- **React SPA**: 用于日常量化管理（策略、回测、风控、数据采集）
- **Streamlit**: 用于快速 AI 对话交互（晨会、研报分析、问答）

---

## 二、文件结构

```
streamlit_chat/
+-- app.py                       # Streamlit 主入口 (~260行)
+-- requirements.txt             # streamlit==1.44.1, requests==2.32.3
+-- lib/
    +-- api_client.py            # 后端 API 客户端封装 (~90行)
    +-- theme.py                 # 自定义 CSS 主题 (~35行)
```

总共仅 **4 个文件**，代码量非常精简。

---

## 三、核心代码逐行分析

### 3.1 主入口 [app.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/streamlit_chat/app.py)

#### 3.1.1 页面配置与初始化

```python
# 设置页面标题、图标、宽屏布局
st.set_page_config(page_title="AI 投资助手", page_icon="A", layout="wide", initial_sidebar_state="collapsed")

# 应用自定义 CSS 主题
apply_theme()
```

**推荐问题** (4 个预设快捷入口):
```python
RECOMMENDED_QUESTIONS = [
    "请生成今日晨会简报",         # -> 路由到晨会工作流 (LangGraph)
    "帮我分析贵州茅台的投资价值",   # -> 路由到 DeepAgent (五步法分析)
    "最近有哪些热门板块？",         # -> 路由到 DeepAgent (联网搜索)
    "推荐几只低估值蓝筹股",         # -> 路由到 DeepAgent (策略推荐)
]
```

#### 3.1.2 状态管理

使用 Streamlit 的 `st.session_state` 管理三个状态变量:
```python
def _init_state() -> None:
    for k, v in {
        "conv_list": [],           # 历史对话列表（从后端获取）
        "current_conv_id": "",     # 当前对话 ID
        "chat_history": [],        # 当前对话的消息列表 [{role, content, metadata}]
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v
```

**对话加载** (从后端拉取完整历史):
```python
def _load_conversation(conv_id: str) -> None:
    conv = get_conversation(conv_id)  # GET /api/v1/conversations/{id}
    items = []
    for m in conv.get("messages", []) or []:
        role = m.get("role") or "user"
        content = m.get("content") or ""
        items.append({"role": role, "content": content, "metadata": m.get("metadata") or {}})
    st.session_state["current_conv_id"] = conv_id
    st.session_state["chat_history"] = items
```

#### 3.1.3 侧边栏 (对话管理)

```python
def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 对话管理")

        # 新建对话按钮
        if st.button("+ 新建对话", use_container_width=True, type="primary"):
            conv = create_conversation("新对话")  # POST /api/v1/conversations
            st.session_state["current_conv_id"] = conv["id"]
            st.session_state["chat_history"] = []
            st.rerun()

        st.divider()
        st.markdown("#### 历史对话")

        # 获取历史对话列表
        convs = list_conversations()  # GET /api/v1/conversations

        for conv in convs:
            cid = conv.get("id") or ""
            title = (conv.get("title") or "无标题").strip() or "无标题"
            is_active = st.session_state.get("current_conv_id") == cid

            cols = st.columns([4, 1])
            with cols[0]:
                # 切换对话按钮
                label = f"{title}" + ("（当前）" if is_active else "")
                if st.button(label[:28], key=f"conv_{cid}", use_container_width=True):
                    _load_conversation(cid)
                    st.rerun()
            with cols[1]:
                # 删除对话按钮
                if st.button("删除", key=f"del_{cid}", use_container_width=True):
                    delete_conversation(cid)  # DELETE /api/v1/conversations/{id}
                    if st.session_state.get("current_conv_id") == cid:
                        st.session_state["current_conv_id"] = ""
                        st.session_state["chat_history"] = []
                    st.rerun()
```

#### 3.1.4 欢迎页面

```python
RECOMMENDED_QUESTIONS = [
    "请生成今日晨会简报",
    "帮我分析贵州茅台的投资价值",
    "最近有哪些热门板块？",
    "推荐几只低估值蓝筹股",
]

def _render_welcome() -> None:
    with st.container():
        col_icon, col_text = st.columns([1, 8])
        with col_icon:
            st.markdown("### <span style='font-size:2.5rem'>hi~</span>", unsafe_allow_html=True)
        with col_text:
            st.markdown("#### 欢迎使用 AI 投资助手")
            st.markdown("请从左侧选择一个对话，或新建一个对话开始交流")
            st.markdown("---")
            st.markdown("**推荐问题：**")
            for q in RECOMMENDED_QUESTIONS:
                st.markdown(f"- {q}")
```

#### 3.1.5 核心对话处理 (`_handle_prompt`)

这是整个应用的核心函数，处理用户输入的完整流程:

```python
def _handle_prompt(prompt: str) -> None:
    # 1. 确保有当前对话
    conv_id = _ensure_conversation()

    # 2. 显示用户消息并持久化
    st.session_state["chat_history"].append({"role": "user", "content": prompt})
    add_message(conv_id, "user", prompt)  # POST /api/v1/conversations/{id}/messages
    with st.chat_message("user"):
        st.markdown(prompt)

    # 3. 初始化 SSE 流式接收
    status_box = st.empty()
    assistant_placeholder = None
    tool_calls = []
    full_text = ""
    report_html = ""

    # 4. SSE 流式接收后端响应
    for ev in stream_agent(prompt):  # POST /api/v1/agent/stream
        ev_type = ev.get("_event") or ""

        if ev_type == "route":
            # 显示路由信息 (如 "路由: graph:morning_brief")
            target = ev.get("route", {}).get("target", "")
            status_box.info(f"路由: {target}")

        elif ev_type == "status":
            # 显示处理状态 (如 "正在分析您的问题...")
            status_box.info(ev.get("message", ""))

        elif ev_type == "tools":
            # 显示可用工具数量
            tools = ev.get("tools") or []
            status_box.info(f"识别到 {len(tools)} 个工具")

        elif ev_type == "tool_end":
            # 工具调用完成 -> 记录到 tool_calls 列表
            tool_calls.append({
                "name": ev.get("tool", "unknown"),
                "status": "done",
                "detail": json.dumps(ev.get("result", {}), ensure_ascii=False, indent=2)[:2000],
            })
            status_box.success(f"工具 `{ev.get('tool')}` 完成")

        elif ev_type == "message":
            # AI 消息 -> 流式追加显示
            content = ev.get("message", {}).get("content", "")
            if content:
                full_text = (full_text + "\n\n" + content).strip()
                if assistant_placeholder is None:
                    with st.chat_message("assistant"):
                        assistant_placeholder = st.empty()
                assistant_placeholder.markdown(full_text)

        elif ev_type == "report":
            # 晨会简报 HTML
            report_html = (ev.get("report_html") or "").strip()

        elif ev_type == "done":
            # 处理完成
            pass

    # 5. 渲染工具调用详情
    _render_tool_calls(tool_calls)

    # 6. 保存回答到 chat_history 和后端
    st.session_state["chat_history"].append({
        "role": "assistant",
        "content": full_text,
        "tool_calls": tool_calls,
        "report_html": report_html,
    })
    add_message(conv_id, "assistant", full_text, {"tool_calls": tool_calls})

    # 7. 如果有晨会简报 HTML -> 渲染
    if report_html:
        st.divider()
        st.subheader("晨会简报")
        st.html(report_html[:8000])  # 限制 8000 字符

    # 8. 清空状态提示
    status_box.empty()
```

流程图示:

```
用户在输入框输入问题
    |
    |-- 1. _ensure_conversation() -> 获取/创建对话ID
    |
    |-- 2. 将用户消息写入 chat_history -> 渲染
    |
    |-- 3. add_message(conv_id, "user", prompt) -> 持久化到后端
    |
    |-- 4. stream_agent(prompt) -> SSE 流式调用后端
    |      |
    |      |-- event: route    -> 显示路由信息 (如 "路由: graph:morning_brief")
    |      |-- event: status   -> 显示处理状态 (如 "正在分析您的问题...")
    |      |-- event: tools    -> 显示可用工具数量
    |      |-- event: tool_end -> 记录工具调用结果
    |      |-- event: message  -> 流式追加 AI 回答文本
    |      |-- event: report   -> 接收晨会简报 HTML
    |      |-- event: done     -> 处理完成
    |
    |-- 5. 渲染工具调用详情 (_render_tool_calls -> st.expander)
    |
    |-- 6. 保存回答到 chat_history + 持久化到后端
    |
    |-- 7. 如果有 report_html -> 用 st.html() 渲染晨会简报 HTML
    |
    |-- 8. 清空 status_box
```

`_ensure_conversation()` 逻辑:
```python
def _ensure_conversation() -> str:
    cid = st.session_state.get("current_conv_id") or ""
    if cid:
        return cid      # 已有对话 -> 直接返回
    conv = create_conversation("新对话")  # 无对话 -> 创建新的
    st.session_state["current_conv_id"] = conv["id"]
    st.session_state["chat_history"] = []
    return conv["id"]
```

#### 3.1.6 工具调用详情渲染

```python
def _render_tool_calls(tool_calls: list[dict[str, Any]]) -> None:
    if not tool_calls:
        return
    with st.expander("工具调用详情"):
        for t in tool_calls:
            icon = {"done": "✅", "error": "❌", "running": "⏳"}.get(t.get("status") or "", "🔧")
            st.markdown(f"{icon} **{t.get('name', '?')}**：`{t.get('status', '')}`")
            detail = t.get("detail") or ""
            if detail:
                st.code(detail[:2000], language="json")
```

#### 3.1.7 主渲染逻辑

```python
_init_state()    # 初始化 session_state
_render_sidebar()  # 渲染侧边栏

has_conv = bool(st.session_state.get("current_conv_id"))
history = st.session_state.get("chat_history", [])

if not has_conv:
    _render_welcome()  # 无对话 -> 显示欢迎页面
else:
    _render_history()  # 有对话 -> 渲染聊天历史

st.divider()
prompt = st.chat_input("输入您的问题")
if prompt:
    _handle_prompt(prompt)  # 处理用户输入
```

---

### 3.2 API 客户端 [lib/api_client.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/streamlit_chat/lib/api_client.py)

封装了与后端 FastAPI 的所有 HTTP 通信:

**基础配置**:
```python
def _base() -> str:
    return os.getenv("AI_QUANT_API_BASE", "http://localhost:8000").rstrip("/")
```

**接口清单**:

| 函数 | HTTP 方法 | 后端路径 | 用途 | 超时 |
|------|-----------|---------|------|------|
| `get_status()` | GET | `/api/v1/agent/status` | 检查 Agent 状态 | 10s |
| `get_tools()` | GET | `/api/v1/agent/tools` | 获取可用工具列表 | 10s |
| `get_agent_runs(limit=20)` | GET | `/api/v1/agent/runs` | 获取运行历史 | 10s |
| `stream_agent(user_input)` | POST | `/api/v1/agent/stream` | **SSE 流式调用 (核心)** | 120s |
| `list_conversations()` | GET | `/api/v1/conversations` | 获取对话列表 | 10s |
| `create_conversation(title)` | POST | `/api/v1/conversations` | 创建新对话 | 20s |
| `get_conversation(conv_id)` | GET | `/api/v1/conversations/{id}` | 获取对话详情 | 20s |
| `delete_conversation(conv_id)` | DELETE | `/api/v1/conversations/{id}` | 删除对话 | 20s |
| `add_message(conv_id, role, content, metadata)` | POST | `/api/v1/conversations/{id}/messages` | 添加消息 | 20s |

**SSE 流式解析** (核心):
```python
def stream_agent(user_input: str) -> Iterator[dict[str, Any]]:
    with requests.post(
        f"{_base()}/api/v1/agent/stream",
        json={"input": user_input},
        stream=True,           # 启用流式响应
        timeout=120,           # 长超时 (120秒)
        headers={"Accept": "text/event-stream"},
    ) as resp:
        resp.raise_for_status()
        ev_type = ""
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue       # 跳过空行 (SSE 分隔符)
            line = line.strip()
            if line.startswith("event:"):
                ev_type = line[6:].strip()   # 解析事件类型
                continue
            if line.startswith("data:"):
                try:
                    payload = json.loads(line[5:].strip())  # 解析 JSON 负载
                except Exception:
                    continue
                yield {**payload, "_event": ev_type}  # 合并事件类型
```

---

### 3.3 主题样式 [lib/theme.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/streamlit_chat/lib/theme.py)

通过 `st.markdown(..., unsafe_allow_html=True)` 注入自定义 CSS:

```css
/* 页面背景 */
.stApp { background-color: #f8fafc; }

/* 消息气泡容器: 白底、圆角、阴影边框 */
[data-testid="stChatMessageContainer"] {
    background-color: #ffffff;
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 8px;
    border: 1px solid #e2e8f0;
}

/* 输入框: 固定底部、白底、上边框 */
[data-testid="stChatInputContainer"] {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 12px 24px;
    border-top: 1px solid #e2e8f0;
    z-index: 100;
}

/* 按钮样式 */
.stButton > button {
    border-radius: 8px;
    font-weight: 500;
}
```

---

## 四、SSE 事件协议详解

Streamlit 前端与后端通过 Server-Sent Events (SSE) 通信。后端 [agent.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/api/agent.py) 的 `run_agent_stream()` 函数定义的事件协议:

| 事件类型 | 触发时机 | data 内容 | Streamlit 处理 |
|---------|---------|-----------|---------------|
| `route` | 路由决策后 | `{"route": {"target": "...", "reason": "..."}}` | 显示路由信息 |
| `status` | 处理过程中 | `{"status": "...", "message": "..."}` | 显示状态提示 |
| `tools` | DeepAgent 启动时 | `{"tools": [...]}` | 显示工具数量 |
| `tool_end` | 每个工具执行完 | `{"tool": "...", "result": {...}}` | 记录到 tool_calls 列表 |
| `message` | AI 生成回复 | `{"message": {"role": "assistant", "content": "..."}}` | 流式追加显示 |
| `report` | 晨会简报生成 | `{"report_html": "<html>..."}` | 保留等待后续渲染 |
| `done` | 全部完成 | `{"result": {...}}` | 标记完成 |
| `error` | 发生错误 | `{"error": "..."}` | 显示错误信息 |

**事件流示例** (用户输入 "请生成今日晨会简报"):

```
event: route
data: {"route":{"target":"graph:morning_brief","reason":"matched_keyword"},"run_id":"abc123"}

event: status
data: {"status":"thinking","message":"正在分析您的问题...","run_id":"abc123"}

event: status
data: {"status":"routing","message":"路由到: 晨会工作流","run_id":"abc123"}

event: status
data: {"status":"generating","message":"正在生成晨会简报...","run_id":"abc123"}

event: message
data: {"message":{"role":"assistant","content":"晨会简报已生成"},"run_id":"abc123"}

event: report
data: {"report_html":"<html>晨会简报全文...</html>","run_id":"abc123"}

event: status
data: {"status":"done","message":"处理完成","run_id":"abc123"}

event: done
data: {"result":{"text":"处理完成"},"run_id":"abc123"}
```

---

## 五、与后端 DeepAgent 引擎的交互

### 5.1 调用链路

```
Streamlit 前端
    |
    | POST /api/v1/agent/stream  (SSE)
    v
agent.py -> route_intent()
    |
    +-- "graph:morning_brief" -> LangGraph 晨会工作流
    |       |
    |       +-- collect 节点: 初始化参数
    |       +-- run 节点: 行业评分 -> 生成 Markdown/HTML 报告
    |
    +-- "tool:quant_assistant" -> 量化助手 (关键词匹配)
    |
    +-- 默认 -> DeepAgent 引擎
            |
            +-- 构建 System Prompt (当前时间 + 工具列表 + 五步法)
            +-- LLM 多轮思考循环 (最多6步)
            |   +-- 输出 JSON {"action":"tool","tool_name":"...","args":{...}}
            |   +-- 执行工具 -> 返回结果
            |   +-- 循环直到 action="final"
            +-- 输出最终回答
```

### 5.2 路由决策 (Router Agent)

[router_agent.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/agents/router_agent.py):

```python
def route_intent(user_input: str) -> dict:
    text = user_input.strip()
    if not text:
        return {"target": "none", "reason": "empty_input"}
    if "晨会" in text:
        return {"target": "graph:morning_brief", "reason": "matched_keyword"}
    return {"target": "tool:quant_assistant", "reason": "default_route"}
```

### 5.3 DeepAgent 引擎核心逻辑

[deepagent_engine.py](file:///Users/apple/Desktop/ai_huahua/ai_quant/backend/llm/deepagent_engine.py):

```python
def run_deepagent(user_input, thread_id="default", max_steps=6):
    catalog = _tool_catalog()       # 获取 17 个工具定义
    sys_prompt = _system_prompt(catalog)  # 构建系统提示词

    llm = ChatTongyi(model="qwen-plus")  # 通义千问模型

    thread = _get_thread(thread_id)  # 获取会话线程
    thread.append({"role": "user", "content": user_input})

    for _ in range(max_steps):       # 最多 6 步思考
        raw = llm.invoke([system, *working])  # 调用 LLM
        obj = json.loads(raw)

        if obj["action"] == "final":  # 最终回答
            return obj["text"]

        if obj["action"] == "tool":   # 调用工具
            tool_name = obj["tool_name"]
            args = obj["args"]
            result = run_tool(tool_name, args)  # 执行工具
            working.append({"role": "user", "content": f"工具结果: {result}"})
            # 继续循环...

    return "已达到最大执行步数"
```

**系统提示词**包含:
- 当前日期时间 (确保时间表述准确)
- 可用 17 个工具列表
- 常用股票代码 (中芯国际、贵州茅台等)
- **国泰君安"五步法"** 方法论:
  1. 信息差 -- 市场还不知道/忽视了什么？
  2. 逻辑差 -- 市场的推理错在哪里？
  3. 预期差 -- 一致预期 vs 实际偏离多大？
  4. 催化剂 -- 什么事件会引爆重估？
  5. 结论+风险闭环 -- 最终判断 + 哪里可能出错？
- 五种研报场景 (个股深度/季报速评/行业比较/事件驱动/财务异常)
- JSON 输出协议约束

---

## 六、对话流程时序图

### 6.1 用户输入分析请求

```
用户: "帮我分析贵州茅台的投资价值"
    |
+--------+         +-----------+         +-------------+
|Streamlit|         |agent.py   |         |  DeepAgent   |
+--------+         +-----------+         +-------------+
    |                    |                      |
    | POST /agent/stream |                      |
    |------------------->|                      |
    |                    |                      |
    | event: route       |  route_intent()      |
    |<-------------------|                      |
    |                    |                      |
    | event: status      |                      |
    |<-------------------|                      |
    |                    |  run_deepagent()      |
    |                    |--------------------->|
    |                    |                      |
    |                    |  多轮工具调用循环      |
    |                    |  web_search           |
    |                    |  financial_analysis   |
    |                    |  stock_price          |
    |                    |  ...                  |
    |                    |                      |
    | event: tool_end    |                      |
    |<-------------------|                      |
    | event: tool_end    |                      |
    |<-------------------|                      |
    |                    |                      |
    | event: message     |  final 回答           |
    |<-------------------|                      |
    | event: done        |                      |
    |<-------------------|                      |
    |                    |                      |
```

### 6.2 用户输入晨会请求

```
用户: "请生成今日晨会简报"
    |
+--------+         +-----------+         +-----------------+
|Streamlit|         |agent.py   |         | morning_brief   |
+--------+         +-----------+         +-----------------+
    |                    |                      |
    | POST /agent/stream |                      |
    |------------------->|                      |
    |                    |                      |
    | event: route       |                      |
    |<-------------------|                      |
    |                    |                      |
    | event: status      |                      |
    |<-------------------|                      |
    |                    |                      |
    |                    | build_morning_graph() |
    |                    |--------------------->|
    |                    |                      |
    |                    | collect 节点: 初始化   |
    |                    | run 节点: 行业评分     |
    |                    |                      |
    |                    |<---------------------|
    |                    |                      |
    | event: message     |                      |
    |<-------------------|                      |
    |                    |                      |
    | event: report      | (晨会简报 HTML)      |
    |<-------------------|                      |
    |                    |                      |
    | event: done        |                      |
    |<-------------------|                      |
    |                    |                      |
```

---

## 七、用户交互界面图

```
+---------------------------------------------------+
|  侧边栏                    |  对话主区域             |
|  +-----------------------+  |                       |
|  | 对话管理               |  |  hi~                  |
|  |  +------------------+ |  |                       |
|  |  | + 新建对话       | |  |  欢迎使用 AI 投资助手  |
|  |  +------------------+ |  |                       |
|  |-----------------------|  |  请从左侧选择一个对话  |
|  | 历史对话               |  |  或新建一个对话开始    |
|  |  [对话1] (当前)  删除 |  |                       |
|  |  [对话2]        删除 |  |  ---                   |
|  |  [对话3]        删除 |  |                       |
|  |  ...                  |  |  推荐问题:              |
|  |                       |  |  - 请生成今日晨会简报  |
|  |                       |  |  - 帮我分析贵州茅台     |
|  |                       |  |  - 最近有哪些热门板块?  |
|  |                       |  |  - 推荐几只低估值蓝筹  |
|  |                       |  |                       |
|  |                       |  |  [输入您的问题...]      |
|  |  2026-05-26           |  |                       |
|  +-----------------------+  |                       |
+---------------------------------------------------+

                        |
                        v (用户选择对话或直接提问)
                        |

+---------------------------------------------------+
|  对话界面                                           |
|  +---------------------------------------------+  |
|  |  用户: 帮我分析贵州茅台的投资价值               |  |
|  +---------------------------------------------+  |
|  +---------------------------------------------+  |
|  |  AI 助理: [流式输出分析报告...]               |  |
|  |                                            |  |
|  |  贵州茅台投资价值分析报告                     |  |
|  |                                            |  |
|  |  ## 基本信息                               |  |
|  |  - 股票代码: 600519.SH                     |  |
|  |  - 所属行业: 食品饮料                       |  |
|  |  - 最新收盘价: XXX元                       |  |
|  |                                            |  |
|  |  ## 财务分析                               |  |
|  |  - ROE: XX%                               |  |
|  |  - 营收增长率: XX%                         |  |
|  |  - ...                                     |  |
|  |                                            |  |
|  |  ## 投资观点                               |  |
|  |  ...                                       |  |
|  +---------------------------------------------+  |
|                                                    |
|  v 工具调用详情 (可展开)                              |
|  +---------------------------------------------+  |
|  |  ✅ web_search: done                          |  |
|  |  ✅ stock_price: done                         |  |
|  |  ✅ financial_analysis: done                  |  |
|  +---------------------------------------------+  |
|                                                    |
|  +---------------------------------------------+  |
|  |  [输入您的问题...]                             |  |
|  +---------------------------------------------+  |
+---------------------------------------------------+

                        |
                        v (如果生成了晨会简报)
                        |

+---------------------------------------------------+
|  晨会简报区域 (分隔线下方)                          |
|                                                    |
|  ---                                               |
|  晨会简报                                           |
|  +---------------------------------------------+  |
|  |  <html>晨会简报全文...</html> (st.html 渲染)   |  |
|  +---------------------------------------------+  |
+---------------------------------------------------+
```

---

## 八、技术要点总结

| 方面 | 说明 |
|------|------|
| **框架** | Streamlit 1.44.1 |
| **HTTP 客户端** | requests 2.32.3 |
| **通信方式** | SSE (Server-Sent Events) 流式 |
| **超时配置** | SSE 请求 120 秒，普通请求 10-20 秒 |
| **状态管理** | `st.session_state` (内存级) |
| **后端地址** | 环境变量 `AI_QUANT_API_BASE`，默认 `http://localhost:8000` |
| **对话管理** | 通过后端 `conversation_api` 持久化 |
| **总代码量** | 约 390 行 (4个文件) |
| **依赖数** | 仅 2 个 (streamlit, requests) |
| **样式方案** | 自定义 CSS (通过 `st.markdown` 注入) |
| **渲染方式** | `st.chat_message()` + `st.chat_input()` + `st.html()` |
| **流式更新** | `st.empty()` 占位符 + `.markdown()` 增量更新 |

**核心设计特点**:
1. **纯前端无状态** -- 所有对话数据通过后端持久化，Streamlit 只负责展示
2. **SSE 流式交互** -- 长连接接收后端实时响应，用户体验流畅
3. **工具调用可视化** -- 通过展开器展示 AI 的工具调用过程，提升透明度
4. **晨会简报 HTML 渲染** -- 直接渲染完整 HTML 报告，无需额外处理
5. **极简依赖** -- 仅依赖 streamlit 和 requests 两个包，维护成本低
