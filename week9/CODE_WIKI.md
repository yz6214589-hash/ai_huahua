# Week9 Code Wiki

本文档覆盖 [week9](file:///Users/apple/Desktop/ai_huahua/week9) 下全部代码与示例工程，目标是帮助你快速理解：整体架构、模块职责、关键类/函数、依赖关系与运行方式。

## 1. 总览

week9 主要包含两大类内容：

1. **nanobot 框架与用例**（课程代码-20260411）
   - nanobot-main：通用多渠道 AI Agent 框架（Python），并提供可选的 Node/TS Bridge（如 WhatsApp）。
   - CASE-AI量化助手（nanobot）：基于 nanobot 的“投研/量化助手”案例工程（以 Skills 组织能力）。
   - CASE-XtQuant实盘交易：xtquant + miniQMT 实盘交易示例与封装。
   - CASE-nanobot使用、skill-nanobot：nanobot 的使用示例与技能模板示例。
2. **强化学习（RL）示例工程**（课程代码-20260415）
   - 股票交易环境 + DQN 择时 + 回测评估 + 拆单对比（TWAP vs RL）。
   - CartPole Q-learning 离散化示例。
   - 迷宫 Q-learning 矩阵迭代示例。

## 2. 目录结构

```
week9/
├─ 课程代码-20260411/
│  ├─ nanobot-main/                         # nanobot 框架（Python + 可选 Node bridge）
│  ├─ CASE-AI量化助手（nanobot）/           # 投研/量化 Agent 案例（Skills 驱动）
│  ├─ CASE-XtQuant实盘交易/                 # miniQMT/xtquant 实盘示例
│  ├─ CASE-nanobot使用/                     # nanobot 的使用范例（多子例子）
│  ├─ skill-nanobot/                        # “技能化”示例工程
│  └─ nanobot-main/bridge/                  # Node/TS bridge（可选）
└─ 课程代码-20260415/
   ├─ CASE-基于RL的交易策略/                # 股票交易环境 + DQN + 回测 + 拆单
   ├─ CASE-cartpole-qlearning/              # CartPole Q-learning 离散化
   └─ CASE-迷宫问题/                        # 迷宫 Q-learning
```

## 3. nanobot-main（框架）架构

### 3.1 框架定位

nanobot-main 是“多渠道消息接入 + Agent Loop + 工具/技能系统 + 多 Provider 适配”的轻量框架：

- **面向 CLI/SDK**：既可用命令行交互，也可在 Python 中以 SDK 方式调用。
- **面向扩展**：通过 Skills（SKILL.md）“教”Agent 如何用工具；通过 Tools 接入文件系统、Web、Shell、消息发送、子 Agent（spawn）、MCP 等能力。

### 3.2 关键模块与职责（按调用链）

**入口层**
- CLI 入口命令：`nanobot`（Typer App）在 [pyproject.toml](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/pyproject.toml#L84-L86) 声明，对应实现为 [commands.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/cli/commands.py)。
- Python 模块入口：`python -m nanobot` 在 [__main__.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/__main__.py)。
- 程序化接口（SDK 外观）：[Nanobot](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/nanobot.py#L23-L114)。

**核心运行层（Agent Loop）**
- 核心调度器：[AgentLoop](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/loop.py#L149-L478)
  - 初始化装配：ContextBuilder / SessionManager / ToolRegistry / AgentRunner / SubagentManager（见 [loop.py:L163-L253](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/loop.py#L163-L253)）
  - 默认工具注册：文件读写、list、exec、web_search/web_fetch、message、spawn、cron（见 [loop.py:L257-L280](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/loop.py#L257-L280)）
  - 主循环：从总线消费消息并派发任务（见 [loop.py:L392-L424](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/loop.py#L392-L424)）
  - 会话串行 + 跨会话并发：按 session_key 加锁（见 [loop.py:L424-L429](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/loop.py#L424-L429)）

**消息解耦层**
- 消息总线：Inbound/Outbound 两队列 [MessageBus](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/bus/queue.py#L8-L44)

**上下文构建层（Prompt / Memory / Skills）**
- 上下文构建：system prompt + 历史 + runtime metadata 合并 [ContextBuilder](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/context.py#L16-L169)
  - BOOTSTRAP 文件：AGENTS.md / SOUL.md / USER.md / TOOLS.md（workspace 内存在就会加载）
  - Memory：读取 `workspace/memory/MEMORY.md` 注入系统提示
  - Skills：生成 skills summary（用于渐进式加载）
- Skills 加载与可用性判断：读取 `skills/<name>/SKILL.md` [SkillsLoader](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/skills.py#L13-L141)

**工具系统（Tools）**
- 工具注册表：负责 tool schema、参数校验、执行与错误提示 [ToolRegistry](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/tools/registry.py#L8-L73)

**Provider 适配层（LLM）**
- Provider 构造（基于 config 自动选择 backend）：[_make_provider](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/nanobot.py#L116-L176)

### 3.3 核心执行流程（简化版）

1. Channel/CLI 将消息写入 MessageBus.inbound。
2. AgentLoop.run 消费 inbound，按 session_key 将消息派发到 `_dispatch`（会话串行 + 跨会话并发）。
3. `_process_message`（内部）调用 ContextBuilder 组装 system prompt + history + runtime context + 当前 user 消息。
4. AgentRunner 与 LLMProvider 调用模型得到 response（可能包含 tool calls）。
5. ToolRegistry 逐个执行 tool calls，将结果回灌到 messages，再次迭代直到 final response 或达到 max_iterations。
6. 将 final response 写回 MessageBus.outbound，由 Channel/CLI 展示或发送。

### 3.4 依赖与安装（nanobot-main）

- Python 版本要求：`>=3.11`（见 [pyproject.toml](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/pyproject.toml#L6)）
- 核心依赖（节选）：typer、pydantic、httpx、websockets、loguru、rich、mcp、openai、anthropic 等（见 [pyproject.toml:L20-L51](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/pyproject.toml#L20-L51)）
- 可选依赖（extras）：weixin / wecom / matrix / discord / api / dev（见 [pyproject.toml:L53-L82](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/pyproject.toml#L53-L82)）

### 3.5 运行方式（nanobot-main）

以 nanobot-main 自身 README 为准（见 [README.md](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/README.md)）。常见路径如下：

1. 在 `nanobot-main/` 内以可编辑方式安装

```bash
pip install -e .
```

2. 使用 CLI

```bash
nanobot --help
nanobot onboard
nanobot agent -m "Hello!"
nanobot gateway
nanobot serve
nanobot status
```

3. 以 SDK 方式调用（示意）

```python
from nanobot.nanobot import Nanobot

bot = Nanobot.from_config()
result = await bot.run("Summarize this repo")
print(result.content)
```

## 4. CASE-AI量化助手（nanobot）（案例工程）

### 4.1 定位与核心思路

该案例把“投研/量化能力”拆成多个 **Skill**（每个 Skill 一个目录，一份 SKILL.md + 若干 scripts），并配合 AGENTS.md 固化角色与方法论，实现一个可渐进式加载能力的投研 Agent（Charles）。

### 4.2 入口与运行

- 入口脚本：[agent.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/agent.py#L1-L165)
- 典型运行方式（脚本内已给出）：

```bash
python agent.py
python agent.py -m "帮我写一份中芯国际的研报"
```

### 4.3 关键实现点

- 框架引用方式：通过 `sys.path` 注入 `nanobot-main`，避免单独发布/安装（见 [agent.py:L35-L39](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/agent.py#L35-L39)）。
- 构建 Bot：`build_bot()` 读取本地 config.json，并把 `DASHSCOPE_API_KEY / TAVILY_API_KEY` 注入配置（见 [agent.py:L74-L106](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/agent.py#L74-L106)）。
- 时间上下文注入：`_inject_time_context()` 将当天日期写入 `memory/MEMORY.md`，用于控制研报时间表述（见 [agent.py:L56-L71](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/agent.py#L56-L71)）。
- Hook 展示工具调用：`CharlesHook.before_execute_tools` 打印 tool call（见 [agent.py:L47-L55](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/agent.py#L47-L55)）。

### 4.4 Skills（能力模块）一览（节选）

Skill 的共同结构为：`skills/<skill-name>/SKILL.md`（说明书）+ `scripts/*.py`（可执行脚本）。

- **read-pdf**：PDF 财报/公告解析 + FAISS RAG 问答（见 [read-pdf/SKILL.md](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/skills/read-pdf/SKILL.md)）
- **sentiment-analysis**：个股新闻舆情 + 宏观恐慌指数 + Polymarket 监控（见 [sentiment-analysis/SKILL.md](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/skills/sentiment-analysis/SKILL.md)）
- **strategy-backtest**：基于 miniQMT/xtquant 的策略回测（MACD/双均线）（见 [strategy-backtest/SKILL.md](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/skills/strategy-backtest/SKILL.md)）
- **write-report**：将分析流程产品化输出报告（目录：skills/write-report/）
- **financial-analysis**：财务比率分析、同业对比（目录：skills/financial-analysis/）
- **trade-order**：下单/查账户/交易封装脚本（目录：skills/trade-order/）
- **web-search**：对市场信息进行搜索与整合（目录：skills/web-search/）

### 4.5 常见依赖（以各脚本 import 为准）

该案例工程未集中声明 requirements，依赖分散在各 scripts 中；常见依赖包括但不限于：

- 数据抓取/行情：akshare
- 数据处理：pandas / numpy
- RAG：faiss、langchain 相关组件（见匹配文件列表：read-pdf/scripts/*.py）
- 交易与回测：xtquant（若使用 miniQMT 相关 skill）

## 5. CASE-XtQuant实盘交易（miniQMT）

### 5.1 定位

该目录提供一组“直接运行的演示脚本”，展示如何通过 `xtquant` 调用 miniQMT 完成：

- 查询账户、查询持仓
- 下单与撤单
- 回调事件处理
- 从策略信号生成订单

### 5.2 核心类：MiniQMTTrader

封装类位于 [4-miniqmt_trader.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-XtQuant%E5%AE%9E%E7%9B%98%E4%BA%A4%E6%98%93/4-miniqmt_trader.py#L87-L240)，关键点：

- `connect()/disconnect()`：连接 miniQMT 并 subscribe 账户
- `buy()/sell()`：自动区分沪深市价类型
- `cancel()/cancel_all()`：撤单能力
- `query_*()`：资产、持仓、委托、成交查询
- `_check_risk()`：内置简单风控（持仓只数上限、单笔金额上限）
- `_TraderCallback`：把回调事件写入 `_events`，并打印到控制台

### 5.3 运行方式

该目录脚本通常可直接运行（前提：已安装 xtquant，且 miniQMT 客户端已启动并登录）：

```bash
python 1-query_account.py
python 2-order_and_cancel.py
python 3-callback_demo.py
python 4-miniqmt_trader.py
python 5-signal_to_order.py
```

## 6. 强化学习（RL）相关工程

### 6.1 CASE-基于RL的交易策略

**定位**
- 自建股票交易环境（类似 Gym API）+ DQN 择时训练 + 回测评估 + 拆单环境（RL vs TWAP）。

**关键脚本**
- `1-搭建RL交易环境.py`：定义并演示交易环境（StockTradingEnv），被后续脚本动态导入使用（见 [2-DQN择时策略.py:L33-L38](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-%E5%9F%BA%E4%BA%8ERL%E7%9A%84%E4%BA%A4%E6%98%93%E7%AD%96%E7%95%A5/2-DQN%E6%8B%A9%E6%97%B6%E7%AD%96%E7%95%A5.py#L33-L38)）
- `2-DQN择时策略.py`：从零实现 DQN 组件（QNetwork / ReplayBuffer / DQNAgent）（见 [2-DQN择时策略.py:L45-L119](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-%E5%9F%BA%E4%BA%8ERL%E7%9A%84%E4%BA%A4%E6%98%93%E7%AD%96%E7%95%A5/2-DQN%E6%8B%A9%E6%97%B6%E7%AD%96%E7%95%A5.py#L45-L119)）
- `3-策略回测与评估.py`：回测与评估（读取训练好的模型/策略结果）
- `4-智能拆单环境.py`：拆单环境（强化学习做执行）
- `5-TWAP与RL拆单对比.py`：TWAP 与 RL 执行对比
- `data_loader.py`：数据加载（MySQL 等数据源）
- `db_config.py`：数据库连接与回测参数（通常通过 `.env` 配置）

**运行方式（常见顺序）**

```bash
python 1-搭建RL交易环境.py
python 2-DQN择时策略.py
python 3-策略回测与评估.py
python 4-智能拆单环境.py
python 5-TWAP与RL拆单对比.py
```

### 6.2 CASE-cartpole-qlearning

**定位**
- Gymnasium CartPole-v1：连续状态离散化（分箱）+ Q-learning 表格法 + 训练/录制。

**关键类/函数**
- Q 表与离散化：`Qlearning`（将 observation 映射为离散 state，并维护 Q table）见 [agent.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-cartpole-qlearning/agent.py#L9-L77)
- ε-greedy：`Agent.act()` 见 [agent.py:L79-L96](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-cartpole-qlearning/agent.py#L79-L96)
- 训练循环：`Trainer.train()` 见 [agent.py:L98-L160](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-cartpole-qlearning/agent.py#L98-L160)

**入口与运行**
- [cartpole.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-cartpole-qlearning/cartpole.py#L11-L67)

```bash
python cartpole.py --episode 100 --render --monitor
```

### 6.3 CASE-迷宫问题

**定位**
- 6 个节点的小型迷宫，使用奖励矩阵 R 与动作价值矩阵 Q，通过迭代更新学习最优策略。

**关键函数**
- `getMaxQ(state)`：取某一状态行的最大 Q 值
- `QLearning(state)`：按 Bellman 更新 `Q[state, action] = R + gamma * maxQ(next_state)`

文件： [maze.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-%E8%BF%B7%E5%AE%AB%E9%97%AE%E9%A2%98/maze.py#L1-L38)

运行：

```bash
python maze.py
```

## 7. 跨子项目依赖关系

### 7.1 依赖关系图（文字版）

```
CASE-AI量化助手（nanobot）
  └── 通过 sys.path 直接复用 nanobot-main（框架）
      ├── AgentLoop / ContextBuilder / ToolRegistry / Provider
      └── SkillsLoader（读取 CASE 工程自己的 skills/*/SKILL.md）

CASE-XtQuant实盘交易
  └── 依赖 xtquant + miniQMT 客户端（外部）

课程代码-20260415（RL）
  ├── CASE-基于RL的交易策略：numpy/torch/gym(类)/matplotlib + DB（外部 MySQL）
  ├── CASE-cartpole-qlearning：gymnasium（外部）
  └── CASE-迷宫问题：numpy
```

### 7.2 “框架 vs 案例”边界建议

- **nanobot-main**：尽量当作可复用框架阅读（关注 AgentLoop/ContextBuilder/Tools/Providers 的组合方式）。
- **CASE-AI量化助手**：关注“Skill 化组织方式 + agent.py 如何装配 config/hook/memory”，以及每个 skill 的 SKILL.md 如何约束执行流程。
- **CASE-XtQuant实盘交易**：关注交易封装类 MiniQMTTrader 的连接/回调/风控/下单 API 设计。
- **RL**：关注“环境 API → 算法实现 → 训练/评估/对比”的脚本化流水线。

## 8. 关键文件索引（按阅读优先级）

### 8.1 nanobot 框架核心

- [agent/loop.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/loop.py)
- [agent/context.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/context.py)
- [agent/skills.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/skills.py)
- [agent/tools/registry.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/agent/tools/registry.py)
- [cli/commands.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/cli/commands.py)
- [nanobot.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/nanobot-main/nanobot/nanobot.py)

### 8.2 投研/量化案例（Charles）

- [CASE-AI量化助手/agent.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/agent.py)
- [CASE-AI量化助手/AGENTS.md](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/AGENTS.md)
- [read-pdf/SKILL.md](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/skills/read-pdf/SKILL.md)
- [sentiment-analysis/SKILL.md](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-AI%E9%87%8F%E5%8C%96%E5%8A%A9%E6%89%8B%EF%BC%88nanobot%EF%BC%89/skills/sentiment-analysis/SKILL.md)

### 8.3 实盘交易

- [4-miniqmt_trader.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260411/CASE-XtQuant%E5%AE%9E%E7%9B%98%E4%BA%A4%E6%98%93/4-miniqmt_trader.py)

### 8.4 强化学习

- [2-DQN择时策略.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-%E5%9F%BA%E4%BA%8ERL%E7%9A%84%E4%BA%A4%E6%98%93%E7%AD%96%E7%95%A5/2-DQN%E6%8B%A9%E6%97%B6%E7%AD%96%E7%95%A5.py)
- [cartpole.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-cartpole-qlearning/cartpole.py)
- [maze.py](file:///Users/apple/Desktop/ai_huahua/week9/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260415/CASE-%E8%BF%B7%E5%AE%AB%E9%97%AE%E9%A2%98/maze.py)
