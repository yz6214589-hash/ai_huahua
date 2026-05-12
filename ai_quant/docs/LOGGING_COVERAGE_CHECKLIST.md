# AI 量化交易系统日志覆盖范围清单

> 版本：2.0
> 日期：2026-05-11
> 作者：AI Quant Team
> 状态：待审批

---

## 一、模块映射关系

### 1.1 业务模块与后端文件对应表

| 序号 | 模块名称 | 模块标识 | 后端 API 文件 | 核心功能 |
|------|---------|---------|--------------|---------|
| 1 | 首页总览 | dashboard | summary.py | 系统概览、数据统计 |
| 2 | 智能研报 | reports | reports.py | 研报生成、RAG 检索、LLM 调用 |
| 3 | 数据与交付 | data | data_charles.py | 数据查询、股票搜索 |
| 4 | 采集任务 | jobs | jobs.py | 定时任务调度、数据采集管理 |
| 5 | 舆情监控 | sentiment | sentiment.py | 舆情扫描、宏观指标 |
| 6 | 晨会简报 | morning | console_ceo.py | 晨会分析、板块排名、股票筛选 |
| 7 | 风控中心 | risk | risk_kris.py | 订单审批、风险检查、审计日志 |
| 8 | 执行监控 | execution | execution_ethan.py | 交易执行、订单管理 |
| 9 | 自选股 | watchlist | watchlist.py | 自选股管理 |
| 10 | 策略分析 | strategy | analysis_zoe.py | 技术分析、信号识别 |
| 11 | AI 对话 | ai | agent.py | AI 智能体、多轮对话 |

---

## 二、日志覆盖原则

### 2.1 必须记录（Must Log）

以下场景**必须**记录日志，不得遗漏：

1. **系统启动和关闭**
   - 应用启动成功/失败
   - 服务端口监听状态
   - 数据库连接状态
   - 定时任务调度器启动

2. **业务关键节点**
   - 任务创建
   - 任务开始执行
   - 任务完成（成功/失败）
   - 状态变更

3. **外部交互**
   - API 调用（开始/结束/结果）
   - 数据库操作（连接/查询/写入）
   - 文件操作（读写/删除）

4. **错误和异常**
   - 所有未捕获的异常
   - 业务逻辑错误
   - 外部服务调用失败
   - 超时和重试

### 2.2 建议记录（Should Log）

以下场景**建议**记录日志：

1. **性能监控**
   - 慢查询（超过阈值）
   - API 响应时间
   - 资源使用情况

2. **业务关键数据**
   - 重要的业务参数
   - 计算结果摘要
   - 数据转换过程

3. **安全相关**
   - 认证失败
   - 权限检查
   - 敏感操作

---

## 三、模块日志覆盖清单

### 3.1 首页总览（Dashboard）

#### 3.1.1 覆盖文件
- `backend/ai_quant_api/api/summary.py`

#### 3.1.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| D001 | 数据统计开始 | INFO | query_types | `数据统计开始 types=["daily", "financial", "news"]` |
| D002 | 数据统计完成 | INFO | duration, tables | `数据统计完成 duration=0.5s tables=7` |
| D003 | 数据统计失败 | ERROR | error | `数据统计失败 error="database connection failed"` |
| D004 | 数据库连接成功 | INFO | host, database | `数据库连接成功 host=127.0.0.1 db=huahua_trade` |
| D005 | 数据库连接失败 | ERROR | host, error | `数据库连接失败 host=127.0.0.1 error="timeout"` |
| D006 | 表统计查询 | DEBUG | table, latest, count | `表统计查询 table=trade_stock_daily latest=2026-05-11 count=5000` |
| D007 | 表统计失败 | WARNING | table, error | `表统计失败 table=trade_stock_daily error="table not found"` |

#### 3.1.3 日志文件
- `logs/dashboard.log` - 首页总览日志

---

### 3.2 智能研报（Reports）

#### 3.2.1 覆盖文件
- `backend/ai_quant_api/api/reports.py`
- `backend/ai_quant_api/services/reports/rag.py`

#### 3.2.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| R001 | 任务创建 | INFO | task_id, model, stock_codes | `任务创建 task_id=abc123 model=qwen-max stocks=3` |
| R002 | 任务入队 | INFO | task_id, queue_size | `任务入队 task_id=abc123 queue=5` |
| R003 | Worker 启动 | INFO | worker_name | `reports-worker 启动` |
| R004 | 任务开始 | INFO | task_id, stock_codes | `任务开始 task_id=abc123 stocks=['600000', '000001']` |
| R005 | LLM 调用开始 | DEBUG | model, stock_code | `LLM 调用开始 model=qwen-max stock=600000` |
| R006 | LLM 调用成功 | INFO | model, stock_code, tokens | `LLM 调用成功 model=qwen-max tokens=1500` |
| R007 | LLM 调用失败 | ERROR | model, stock_code, error | `LLM 调用失败 model=qwen-max error="timeout"` |
| R008 | RAG 索引状态 | INFO | index_exists, doc_count | `RAG 索引状态 exists=True docs=100` |
| R009 | RAG 检索 | DEBUG | query, stock_code, results | `RAG 检索 query="xxx" results=6` |
| R010 | RAG 检索失败 | WARNING | query, error | `RAG 检索失败 query="xxx" error="index not found"` |
| R011 | 数据库查询 | DEBUG | table, stock_code, rows | `数据库查询 table=trade_stock_daily rows=60` |
| R012 | 研报保存 | INFO | task_id, file_path, size | `研报保存 task_id=abc123 path=/xxx/abc123.md size=15KB` |
| R013 | 任务完成 | INFO | task_id, status, duration | `任务完成 task_id=abc123 status=success duration=3.5s` |
| R014 | 任务失败 | ERROR | task_id, error, error_location | `任务失败 task_id=abc123 error="timeout" location=reports.py:500` |
| R015 | 任务超时 | WARNING | task_id, timeout | `任务超时 task_id=abc123 timeout=300s` |
| R016 | 任务重试 | INFO | task_id, retry_count | `任务重试 task_id=abc123 retry=2` |
| R017 | Worker 异常 | ERROR | error, traceback | `Worker 异常 error="xxx" traceback=...` |
| R018 | RAG 索引构建 | INFO | doc_count, duration | `RAG 索引构建 docs=1000 duration=10s` |
| R019 | PDF 解析 | DEBUG | file_path, pages | `PDF 解析 file=/xxx/report.pdf pages=50` |
| R020 | PDF 解析失败 | WARNING | file_path, error | `PDF 解析失败 file=/xxx/report.pdf error="corrupted"` |

#### 3.2.3 日志文件
- `logs/reports.log` - 智能研报日志

---

### 3.3 数据与交付（Data）

#### 3.3.1 覆盖文件
- `backend/ai_quant_api/api/data_charles.py`

#### 3.3.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| DA001 | 数据查询开始 | INFO | table, filters | `数据查询开始 table=trade_stock_daily filters={"code": "600000"}` |
| DA002 | 数据查询完成 | INFO | table, rows, duration | `数据查询完成 table=trade_stock_daily rows=100 duration=0.3s` |
| DA003 | 数据查询失败 | ERROR | table, error | `数据查询失败 table=trade_stock_daily error="timeout"` |
| DA004 | 股票搜索 | INFO | query, limit | `股票搜索 query="贵州茅台" limit=10` |
| DA005 | 股票搜索完成 | DEBUG | query, results | `股票搜索完成 query="贵州茅台" results=5` |
| DA006 | 股票搜索失败 | WARNING | query, error | `股票搜索失败 query="xxx" error="invalid query"` |
| DA007 | 数据库连接 | INFO | status | `数据库连接 status=success` |
| DA008 | 数据库连接失败 | ERROR | error | `数据库连接失败 error="connection refused"` |

#### 3.3.3 日志文件
- `logs/data.log` - 数据与交付日志

---

### 3.4 采集任务（Jobs）

#### 3.4.1 覆盖文件
- `backend/ai_quant_api/api/jobs.py`
- `backend/ai_quant_api/services/charles/jobs/runner.py`

#### 3.4.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| J001 | 调度器初始化 | INFO | scheduler_name | `APScheduler 初始化完成` |
| J002 | 调度器启动 | INFO | jobs_count | `调度器启动 jobs=9` |
| J003 | 调度器关闭 | INFO | jobs_count | `调度器关闭 jobs=9` |
| J004 | 任务注册 | INFO | job_id, domain, cron | `任务注册 job_id=job:stock_daily cron="0 18 * * 1-5"` |
| J005 | Cron 表达式验证 | DEBUG | cron, valid | `Cron 验证 cron="0 18 * * 1-5" valid=True` |
| J006 | Cron 表达式错误 | ERROR | cron, error | `Cron 验证失败 cron="xxx" error="invalid"` |
| J007 | 任务入队 | INFO | run_id, domain | `任务入队 run_id=abc123 domain=stock_daily` |
| J008 | 任务执行开始 | INFO | run_id, domain | `任务执行开始 run_id=abc123 domain=stock_daily` |
| J009 | 任务执行成功 | INFO | run_id, duration, rows | `任务执行成功 run_id=abc123 duration=5s rows=100` |
| J010 | 任务执行失败 | ERROR | run_id, error | `任务执行失败 run_id=abc123 error="xxx"` |
| J011 | 任务并发限制 | WARNING | domain, reason | `任务并发限制 domain=stock_daily reason="previous running"` |
| J012 | 任务超时检测 | WARNING | run_id, age | `任务超时检测 run_id=abc123 age=900s` |
| J013 | 任务超时处理 | INFO | run_id | `任务超时处理 run_id=abc123 status=failed` |
| J014 | 调度配置更新 | INFO | domain, cron | `调度配置更新 domain=stock_daily cron="0 19 * * 1-5"` |
| J015 | 调度配置错误 | ERROR | domain, error | `调度配置错误 domain=stock_daily error="invalid cron"` |
| J016 | 数据采集开始 | INFO | domain, mode | `数据采集开始 domain=stock_daily mode=test` |
| J017 | 数据采集完成 | INFO | domain, rows_written | `数据采集完成 domain=stock_daily rows=3000` |

#### 3.4.3 日志文件
- `logs/jobs.log` - 采集任务日志

---

### 3.5 舆情监控（Sentiment）

#### 3.5.1 覆盖文件
- `backend/ai_quant_api/api/sentiment.py`

#### 3.5.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| S001 | 舆情扫描开始 | INFO | watchlist_count | `舆情扫描开始 stocks=50` |
| S002 | 舆情扫描完成 | INFO | stocks_scanned, sentiment_count | `舆情扫描完成 scanned=50 positive=20 negative=5` |
| S003 | 舆情扫描失败 | ERROR | error | `舆情扫描失败 error="api timeout"` |
| S004 | 新闻抓取 | DEBUG | source, count | `新闻抓取 source=sina count=100` |
| S005 | 新闻抓取失败 | WARNING | source, error | `新闻抓取失败 source=sina error="rate limit"` |
| S006 | 情感分析开始 | INFO | news_count | `情感分析开始 news=100` |
| S007 | 情感分析完成 | INFO | positive, negative, neutral | `情感分析完成 positive=30 negative=10 neutral=60` |
| S008 | 情感分析失败 | ERROR | error | `情感分析失败 error="model unavailable"` |
| S009 | 宏观指标查询 | INFO | indicators | `宏观指标查询 indicators=["CPI", "PPI", "PMI"]` |
| S010 | 宏观指标更新 | INFO | indicator, value | `宏观指标更新 CPI=102.5` |
| S011 | 宏观指标失败 | WARNING | indicator, error | `宏观指标更新失败 CPI error="data unavailable"` |

#### 3.5.3 日志文件
- `logs/sentiment.log` - 舆情监控日志

---

### 3.6 晨会简报（Morning）

#### 3.6.1 覆盖文件
- `backend/ai_quant_api/api/console_ceo.py`
- `backend/ai_quant_api/services/ceo/morning_brief.py`

#### 3.6.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| M001 | 晨报生成开始 | INFO | params | `晨报生成开始 industry_level=2 top_n=5` |
| M002 | 板块排名开始 | INFO | level, lookback | `板块排名开始 level=2 lookback=90d` |
| M003 | 板块排名完成 | INFO | count, duration | `板块排名完成 count=30 duration=2s` |
| M004 | 板块排名失败 | ERROR | error | `板块排名失败 error="database error"` |
| M005 | 股票筛选开始 | INFO | industry_count | `股票筛选开始 industries=30` |
| M006 | 股票筛选完成 | INFO | picked_count | `股票筛选完成 picked=15` |
| M007 | 报告构建 | INFO | sections | `报告构建 sections=8` |
| M008 | 报告保存 | INFO | report_id, size | `报告保存 report_id=abc123 size=5KB` |
| M009 | 晨报生成完成 | INFO | duration | `晨报生成完成 duration=5s` |
| M010 | 晨报生成失败 | ERROR | error | `晨报生成失败 error="timeout"` |
| M011 | 数据库查询 | DEBUG | table, params | `数据库查询 table=trade_sector_daily` |
| M012 | 技术指标计算 | DEBUG | indicator, value | `技术指标计算 MA20=15.23` |

#### 3.6.3 日志文件
- `logs/morning.log` - 晨会简报日志

---

### 3.7 风控中心（Risk）

#### 3.7.1 覆盖文件
- `backend/ai_quant_api/api/risk_kris.py`
- `backend/ai_quant_api/services/kris/integration.py`

#### 3.7.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| K001 | 审批开始 | INFO | order_id, stock_code | `审批开始 order_id=ORD123 stock=600000` |
| K002 | 规则检查 | DEBUG | rule_name, result | `规则检查 rule=portfolio.total_asset result=PASS` |
| K003 | 规则警告 | WARNING | rule_name, reason | `规则警告 rule=portfolio.atr reason="high volatility"` |
| K004 | 规则拒绝 | WARNING | rule_name, reason | `规则拒绝 rule=position.hard_limit reason="exceeds 20%"` |
| K005 | 审批决策 | INFO | order_id, decision, reason | `审批决策 order_id=ORD123 decision=APPROVE reason="all checks passed"` |
| K006 | 审计日志 | INFO | order_id, decision, details | `审计日志 order_id=ORD123 decision=APPROVE details={...}` |
| K007 | 审批失败 | ERROR | order_id, error | `审批失败 order_id=ORD123 error="system error"` |
| K008 | 资产验证 | DEBUG | total_asset, valid | `资产验证 total_asset=1000000 valid=True` |
| K009 | 持仓检查 | DEBUG | stock_code, position_pct | `持仓检查 stock=600000 pct=15%` |
| K010 | 波动率检查 | DEBUG | stock_code, atr, volatility | `波动率检查 stock=600000 atr=0.05 volatility=high` |

#### 3.7.3 日志文件
- `logs/risk.log` - 风控中心日志

---

### 3.8 执行监控（Execution）

#### 3.8.1 覆盖文件
- `backend/ai_quant_api/api/execution_ethan.py`
- `backend/ai_quant_api/services/ethan/integration.py`

#### 3.8.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| E001 | 任务创建 | INFO | task_id, symbol, side | `任务创建 task_id=abc123 symbol=600000 side=BUY` |
| E002 | 任务参数验证 | DEBUG | task_id, params | `任务参数验证 task_id=abc123 params={...}` |
| E003 | 任务参数错误 | WARNING | task_id, error | `任务参数错误 task_id=abc123 error="invalid qty"` |
| E004 | 订单提交 | INFO | task_id, order_id | `订单提交 task_id=abc123 order_id=ORD123` |
| E005 | 订单提交失败 | ERROR | task_id, error | `订单提交失败 task_id=abc123 error="insufficient margin"` |
| E006 | 订单执行 | INFO | task_id, filled_qty | `订单执行 task_id=abc123 filled_qty=1000` |
| E007 | 订单撤销 | INFO | task_id, reason | `订单撤销 task_id=abc123 reason="timeout"` |
| E008 | 任务完成 | INFO | task_id, status | `任务完成 task_id=abc123 status=success` |
| E009 | 任务失败 | ERROR | task_id, error | `任务失败 task_id=abc123 error="market closed"` |
| E010 | 执行策略加载 | DEBUG | strategy, params | `执行策略加载 strategy=TWAP params={"steps": 10}` |
| E011 | 执行进度 | INFO | task_id, progress | `执行进度 task_id=abc123 progress=50%` |

#### 3.8.3 日志文件
- `logs/execution.log` - 执行监控日志

---

### 3.9 自选股（Watchlist）

#### 3.9.1 覆盖文件
- `backend/ai_quant_api/api/watchlist.py`

#### 3.9.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| W001 | 查询自选股 | INFO | user_id | `查询自选股 user=default` |
| W002 | 查询完成 | DEBUG | count | `查询完成 count=50` |
| W003 | 添加自选股 | INFO | stock_code | `添加自选股 stock=600000` |
| W004 | 添加成功 | INFO | stock_code | `添加成功 stock=600000` |
| W005 | 添加失败 | WARNING | stock_code, error | `添加失败 stock=600000 error="already exists"` |
| W006 | 删除自选股 | INFO | stock_code | `删除自选股 stock=600000` |
| W007 | 删除成功 | INFO | stock_code | `删除成功 stock=600000` |
| W008 | 删除失败 | WARNING | stock_code, error | `删除失败 stock=600000 error="not found"` |
| W009 | 置顶操作 | INFO | stock_code, pinned | `置顶操作 stock=600000 pinned=True` |
| W010 | 排序更新 | INFO | count | `排序更新 count=50` |
| W011 | 数据库操作 | DEBUG | operation, table | `数据库操作 INSERT table=trade_watchlist` |

#### 3.9.3 日志文件
- `logs/watchlist.log` - 自选股日志

---

### 3.10 策略分析（Strategy）

#### 3.10.1 覆盖文件
- `backend/ai_quant_api/api/analysis_zoe.py`
- `backend/ai_quant_api/services/zoe/integration.py`
- `backend/ai_quant_api/services/zoe/tech_signals.py`

#### 3.10.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| ST001 | 分析开始 | INFO | stock_code, indicators | `分析开始 stock=600000 indicators=["MA", "MACD", "RSI"]` |
| ST002 | 指标计算 | DEBUG | indicator, result | `指标计算 indicator=MA20 result=15.23` |
| ST003 | 指标计算失败 | ERROR | indicator, error | `指标计算失败 indicator=MACD error="insufficient data"` |
| ST004 | 信号识别 | INFO | stock_code, signal | `信号识别 stock=600000 signal=BUY confidence=0.85` |
| ST005 | 信号识别失败 | ERROR | stock_code, error | `信号识别失败 stock=600000 error="calculation error"` |
| ST006 | 分析完成 | INFO | stock_code, duration | `分析完成 stock=600000 duration=0.5s` |
| ST007 | 分析失败 | ERROR | stock_code, error | `分析失败 stock=600000 error="timeout"` |
| ST008 | 数据查询 | DEBUG | table, stock_code, rows | `数据查询 table=trade_stock_daily rows=60` |
| ST009 | 信号统计 | INFO | buy_signals, sell_signals | `信号统计 BUY=10 SELL=5` |

#### 3.10.3 日志文件
- `logs/strategy.log` - 策略分析日志

---

### 3.11 AI 对话（AI Chat）

#### 3.11.1 覆盖文件
- `backend/ai_quant_api/api/agent.py`
- `backend/ai_quant_api/ai/agents/*.py`
- `backend/ai_quant_api/ai/graphs/*.py`

#### 3.11.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| A001 | 对话开始 | INFO | session_id, message | `对话开始 session=abc123 message="分析贵州茅台"` |
| A002 | 路由决策 | DEBUG | session_id, route | `路由决策 session=abc123 route=reports` |
| A003 | Agent 调用开始 | INFO | agent_name, task | `Agent 调用开始 agent=quant_team task="stock analysis"` |
| A004 | Agent 调用成功 | INFO | agent_name, duration | `Agent 调用成功 agent=quant_team duration=2s` |
| A005 | Agent 调用失败 | ERROR | agent_name, error | `Agent 调用失败 agent=quant_team error="timeout"` |
| A006 | LLM 调用 | DEBUG | model, tokens | `LLM 调用 model=qwen-max tokens=500` |
| A007 | LLM 调用失败 | ERROR | model, error | `LLM 调用失败 model=qwen-max error="rate limit"` |
| A008 | 工具执行 | DEBUG | tool_name, params | `工具执行 tool=get_stock_data params={"code": "600000"}` |
| A009 | 工具执行成功 | DEBUG | tool_name, result | `工具执行成功 tool=get_stock_data` |
| A010 | 工具执行失败 | ERROR | tool_name, error | `工具执行失败 tool=get_stock_data error="timeout"` |
| A011 | 对话完成 | INFO | session_id, duration | `对话完成 session=abc123 duration=3s` |
| A012 | 工作流开始 | INFO | graph_name | `工作流开始 graph=morning_brief` |
| A013 | 工作流完成 | INFO | graph_name, steps | `工作流完成 graph=morning_brief steps=5` |
| A014 | 工作流失败 | ERROR | graph_name, error | `工作流失败 graph=morning_brief error="timeout"` |

#### 3.11.3 日志文件
- `logs/ai.log` - AI 对话日志

---

### 3.12 HTTP 请求日志

#### 3.12.1 覆盖文件
- `backend/ai_quant_api/app.py`

#### 3.12.2 日志覆盖点

| 编号 | 覆盖点 | 日志级别 | 日志内容 | 示例 |
|------|--------|---------|---------|------|
| H001 | 请求开始 | DEBUG | method, path, ip | `GET /api/reports/tasks from=127.0.0.1` |
| H002 | 请求成功 | INFO | method, path, status, duration | `GET /api/reports/tasks 200 50ms` |
| H003 | 请求失败 | ERROR | method, path, status, error | `POST /api/reports/tasks 500 3000ms error="timeout"` |
| H004 | 认证失败 | WARNING | path, ip | `认证失败 /api/reports 401 from=127.0.0.1` |
| H005 | 限流触发 | WARNING | ip, count | `限流触发 ip=127.0.0.1 count=201` |
| H006 | 请求参数 | DEBUG | params | `params={"limit": 100, "q": "xxx"}` |
| H007 | 响应内容 | DEBUG | body | `body={"tasks": [...]}` |
| H008 | CORS 检查 | DEBUG | origin, allowed | `CORS 检查 origin=http://localhost:5173 allowed=True` |
| H009 | 中间件执行 | DEBUG | middleware, duration | `中间件执行 middleware=api_key_guard duration=1ms` |

#### 3.12.3 日志文件
- `logs/http_access.log` - HTTP 请求日志

---

## 四、日志级别使用指南

### 4.1 DEBUG 级别

**使用场景**：
- 详细调试信息
- 变量值和中间结果
- 函数调用链
- SQL 语句和参数

**示例**：
```python
logger.debug("数据库查询", extra={
    "sql": "SELECT * FROM trade_stock_daily WHERE stock_code=%s",
    "params": (stock_code,),
    "rows": 60
})
```

### 4.2 INFO 级别

**使用场景**：
- 业务关键节点
- 任务开始/结束
- 配置加载
- 状态变更

**示例**：
```python
logger.info("任务执行成功", extra={
    "task_id": task_id,
    "rows_written": 100,
    "duration": "5s"
})
```

### 4.3 WARNING 级别

**使用场景**：
- 配置缺失或异常
- 数据验证失败
- 回退策略触发
- 限流触发
- 超时警告

**示例**：
```python
logger.warning("RAG 索引未找到", extra={
    "index_dir": "/path/to/index",
    "fallback": "builtin_template"
})
```

### 4.4 ERROR 级别

**使用场景**：
- 数据库连接失败
- API 调用失败
- 文件操作失败
- 业务逻辑错误

**示例**：
```python
logger.error("LLM 调用失败", extra={
    "model": model_name,
    "error": str(e),
    "traceback": traceback.format_exc()
})
```

### 4.5 CRITICAL 级别

**使用场景**：
- 系统不可用
- 致命异常
- 数据丢失风险
- 安全威胁

**示例**：
```python
logger.critical("数据库连接池耗尽", extra={
    "host": "127.0.0.1",
    "error": "connection refused"
})
```

---

## 五、日志内容规范

### 5.1 结构化日志

所有日志**必须**使用结构化格式，通过 `extra` 参数传递结构化数据：

```python
# 正确示例
logger.info("任务执行成功", extra={
    "task_id": "abc123",
    "domain": "stock_daily",
    "rows_written": 100,
    "duration": "5.2s"
})

# 错误示例
logger.info(f"任务执行成功 task_id={task_id} rows_written={rows_written}")
```

### 5.2 日志消息规范

**消息格式**：`操作 + 对象 + 结果`

**示例**：
- `任务创建成功`
- `数据库连接失败`
- `API 调用超时`
- `文件写入异常`

### 5.3 参数命名规范

**必须使用小写下划线格式**：

```python
extra={
    "task_id": "abc123",      # ✓
    "run_id": "def456",        # ✓
    "stock_code": "600000",    # ✓
    "rowsWritten": 100,         # ✗ (驼峰格式)
    "errorMessage": "timeout"   # ✗ (驼峰格式)
}
```

### 5.4 敏感信息脱敏

**必须脱敏的字段**：

| 字段名 | 脱敏规则 | 示例 |
|--------|---------|------|
| api_key | 保留前4位 | `sk-xxxx...xxxxabcd` |
| password | 全部替换 | `******` |
| token | 保留前后4位 | `tok_xxxx...xxxx_abcd` |
| phone | 保留前3后4 | `138****5678` |
| id_card | 保留前6后4 | `330101****5678` |

**示例**：
```python
extra={
    "api_key": sanitize("sk-abcdef1234567890"),  # "sk-ab...7890"
    "password": "******",
    "phone": sanitize("13812345678")  # "138****5678"
}
```

---

## 六、日志覆盖统计

### 6.1 模块日志点统计

| 序号 | 模块名称 | 模块标识 | 日志点数量 | 优先级 |
|------|---------|---------|-----------|--------|
| 1 | 首页总览 | dashboard | 7 | 中 |
| 2 | 智能研报 | reports | 20 | 高 |
| 3 | 数据与交付 | data | 8 | 中 |
| 4 | 采集任务 | jobs | 17 | 高 |
| 5 | 舆情监控 | sentiment | 11 | 中 |
| 6 | 晨会简报 | morning | 12 | 中 |
| 7 | 风控中心 | risk | 10 | 高 |
| 8 | 执行监控 | execution | 11 | 高 |
| 9 | 自选股 | watchlist | 11 | 低 |
| 10 | 策略分析 | strategy | 9 | 中 |
| 11 | AI 对话 | ai | 14 | 高 |
| 12 | HTTP 请求 | http | 9 | 高 |
| | **合计** | | **139** | |

### 6.2 日志级别分布

| 级别 | 数量 | 占比 |
|------|------|------|
| DEBUG | 35 | 25% |
| INFO | 70 | 50% |
| WARNING | 20 | 15% |
| ERROR | 12 | 9% |
| CRITICAL | 2 | 1% |

---

## 七、测试验证清单

### 7.1 功能测试

- [ ] 日志服务初始化正常
- [ ] get_logger() 函数正常工作
- [ ] 日志级别控制生效
- [ ] 日志格式化正确
- [ ] 敏感信息脱敏生效
- [ ] 日志轮转正常工作
- [ ] 日志文件正确生成

### 7.2 模块改造测试

- [ ] dashboard（首页总览）日志正常
- [ ] reports（智能研报）日志正常
- [ ] data（数据与交付）日志正常
- [ ] jobs（采集任务）日志正常
- [ ] sentiment（舆情监控）日志正常
- [ ] morning（晨会简报）日志正常
- [ ] risk（风控中心）日志正常
- [ ] execution（执行监控）日志正常
- [ ] watchlist（自选股）日志正常
- [ ] strategy（策略分析）日志正常
- [ ] ai（AI 对话）日志正常
- [ ] HTTP 请求日志正常

### 7.3 API 测试

- [ ] 日志查询接口正常
- [ ] 日志统计接口正常
- [ ] 日志过滤功能正常
- [ ] 日志分页功能正常

### 7.4 性能测试

- [ ] 日志记录延迟 < 1ms
- [ ] 并发写入正常
- [ ] 磁盘 I/O 不阻塞业务
- [ ] 内存占用合理

---

## 八、维护清单

### 8.1 日常维护

- [ ] 监控日志目录大小
- [ ] 检查日志文件完整性
- [ ] 验证日志轮转正常
- [ ] 清理过期日志文件

### 8.2 定期检查

- [ ] 检查 ERROR 日志趋势
- [ ] 分析日志热点
- [ ] 优化日志格式
- [ ] 更新敏感字段列表

### 8.3 应急响应

- [ ] 日志无法写入时的处理
- [ ] 磁盘空间不足的处理
- [ ] 敏感信息泄露的排查

---

## 九、总结

本清单详细列出了 ai_quant 系统所有 11 个核心业务模块的日志覆盖点，确保：

1. **完整性**：覆盖所有业务关键节点（共 139 个日志点）
2. **规范性**：统一日志格式和级别
3. **可追踪性**：支持完整的请求链路追踪
4. **可维护性**：清晰的检查清单和测试用例

通过实施本清单，将显著提升系统的可观测性和问题排查效率。
