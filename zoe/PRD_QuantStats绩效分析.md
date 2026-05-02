# QuantStats 绩效分析（Common / Plus）需求文档 & 交互流程

## 1. 背景与目标

Zoe 目前已具备回测能力（Backtrader）与 Web 控制台，但缺少“专业级绩效分析报告”能力。本需求新增“QuantStats 绩效分析”模块，支持两种模式：

- Common：参考 [1-QuantStats绩效分析.py](file:///Users/apple/Desktop/ai_huahua/week7/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260328/CASE-QuantStats%E7%BB%A9%E6%95%88%E5%88%86%E6%9E%90%E4%B8%8E%E6%8A%A5%E5%91%8A/1-QuantStats%E7%BB%A9%E6%95%88%E5%88%86%E6%9E%90.py) 的“回测净值/收益率 → QuantStats 指标 + 图表 + HTML 报告”链路
- Plus：参考 [4-实盘交易绩效分析Plus.py](file:///Users/apple/Desktop/ai_huahua/week7/%E8%AF%BE%E7%A8%8B%E4%BB%A3%E7%A0%81-20260328/CASE-QuantStats%E7%BB%A9%E6%95%88%E5%88%86%E6%9E%90%E4%B8%8E%E6%8A%A5%E5%91%8A/4-%E5%AE%9E%E7%9B%98%E4%BA%A4%E6%98%93%E7%BB%A9%E6%95%88%E5%88%86%E6%9E%90Plus.py) 的“实盘组合净值 + SVD 市场状态诊断 + 建议”增强报告

目标：

- 在 Zoe 控制台新增“绩效分析”入口
- 一键生成指标 + 图表 + 可分享的 HTML 报告（在浏览器新标签页打开）
- Common 与 Plus 两种模式前端交互清晰、参数明确

非目标（本期不做）：

- 账户资金管理、自动下单、交易执行
- 多账户/多用户权限体系
- 报告模板在线编辑器

## 2. 用户故事

### 2.1 Common（回测 / 自定义净值绩效报告）

作为量化研究员/交易员：

1. 我在 Zoe 的回测页已能跑出某个策略的回测结果
2. 我希望在“绩效分析”页选择同样的回测参数，直接生成 QuantStats 专业绩效报告
3. 我希望能在页面看到关键指标（总收益、年化、最大回撤、夏普等）并能打开完整 HTML 报告

作为研究员（自定义净值）：

1. 我已经有某策略/账户的净值序列（CSV）
2. 我希望上传净值 CSV 后，直接生成 QuantStats 报告（无需依赖 Zoe 回测）

### 2.2 Plus（实盘 CSV / 回测组合 + 市场状态诊断）

作为实盘交易员：

1. 我有券商导出的历史成交 CSV（可能需要多份合并）
2. 我希望 Zoe 能解析成交记录，基于数据库行情对持仓逐日估值，构建组合净值曲线
3. 我希望生成 QuantStats 报告，并额外看到：
   - 成本拆解（佣金/印花税/过户费等）
   - 个股盈亏拆解（哪只股票赚/亏）
   - SVD 滚动诊断：齐涨齐跌 / 板块分化 / 个股行情，并给出建议

作为组合回测用户：

1. 我希望对“多标的回测组合”（或多标的策略实例集合）做组合层面的绩效分析
2. 我希望看到组合的 QuantStats 指标与 SVD 市场状态诊断（基于组合内多个标的收益率矩阵）

## 3. 功能范围

### 3.1 Common 模式功能清单

- 输入（两种来源二选一）：
  - 回测参数：stock_code、start、end、strategy_id、params、initial_cash、commission
  - 自定义净值 CSV：上传文件（至少包含 date/nav 两列；nav 为净值，初始不要求为 1.0）
- 计算：
  - 从回测引擎获得“净值曲线（NAV）”或“日收益率序列（returns）”，或由净值 CSV 转换得到 returns
  - （可选）加载基准收益率（如沪深300）用于 Alpha/Beta/信息比率/跟踪误差
  - 使用 QuantStats 计算指标体系（30+ 指标）
  - 输出图表数据：累计收益、回撤水下图、月度热力图、滚动夏普（前端使用 ECharts 绘制）
- 输出：
  - 页面展示：关键指标卡片 + 图表缩略图
  - 一键打开 HTML 报告（可复制链接分享）

### 3.2 Plus 模式功能清单

- 输入（两种来源二选一）：
  - 实盘：上传券商成交 CSV（支持多文件）、初始资金 initial_cash、（可选）时间范围、SVD 参数（window/step）
  - 回测组合：选择多个标的/策略实例 + 组合权重（或等权），生成组合净值与收益率矩阵，并做 QuantStats + SVD
- 计算：
  - CSV 解析：清洗列名/空格、日期解析、交易方向识别、数值列转数值
  - 证券代码标准化：6/5 开头 → .SH；0/3 开头 → .SZ；其他暂不支持
  - 个股盈亏拆解：按标的聚合买入/卖出/成本/未平仓等
  - 成本拆解：佣金/印花税/过户费等汇总
  - 构建组合净值：按交易日迭代现金与持仓，按收盘价逐日估值
  - QuantStats 指标与图表数据输出（前端 ECharts 绘制）
  - SVD 市场状态诊断（至少 3 只有效股票、且数据长度满足 window+step）：
    - top1 因子方差占比 > 50%：齐涨齐跌
    - 35%~50%：板块分化
    - < 35%：个股行情
  - 输出建议（按参考脚本的文案规则）
- 输出：
  - 页面展示：关键指标 + 成本汇总 + 个股盈亏表 + SVD 状态卡片 + SVD 趋势图
  - 一键打开 HTML 报告

## 4. 页面与交互流程（Web 控制台）

### 4.1 入口与导航

- 顶部导航新增：绩效分析（/performance）
- 页面内提供模式切换：
  - Common（回测 / 净值 CSV）
  - Plus（实盘 CSV / 回测组合）

### 4.2 Common 交互流程

1. 用户进入 /performance，默认展示 Common 模式
2. 用户选择数据来源：
   - 回测
   - 净值 CSV
3. 若选择“回测”，用户填写回测参数：
   - 股票代码 stock_code（默认 600519.SH）
   - 日期 start/end（默认：近一年）
   - 策略 strategy_id（下拉，来自 /api/v1/strategies）
   - 参数 params（JSON 文本）
   - 初始资金 initial_cash
   - 手续费 commission
   - （可选）基准 benchmark_code（默认 000300.SH 或留空）
4. 若选择“净值 CSV”，用户上传 CSV 并填写：
   - （可选）基准 benchmark_code
5. 点击「生成报告」
6. 前端调用后端 API，展示：
   - 指标（表格/卡片）
   - 图表（ECharts 绘制）
   - 「打开 HTML 报告」按钮（新标签页打开）

异常提示（前端友好文案）：

- 回测依赖缺失（backtrader）
- 数据为空（no_data）
- 参数 JSON 解析失败
- 基准数据缺失（若基准是可选项，则提示“基准不可用，已跳过对比”）

### 4.3 Plus 交互流程

1. 用户切换到 Plus
2. 用户选择数据来源：
   - 实盘 CSV
   - 回测组合
3. 若选择“实盘 CSV”，上传 CSV（支持多文件），并填写：
   - 初始资金 initial_cash
   - SVD window/step（可选，默认 window=120，step=20）
4. 若选择“回测组合”，选择组合标的与权重（或等权）并填写 SVD 参数
5. 点击「生成报告」
6. 前端展示：
   - 指标（表格/卡片）
   - 成本汇总
   - 个股盈亏表（可排序）
   - SVD 状态卡片 + 建议 + 趋势图
   - 「打开 HTML 报告」

异常提示：

- CSV 无法识别/编码读取失败/必需列缺失
- 有效股票不足 3 只或交易日不足导致 SVD 跳过（页面明确标注“跳过原因”）

## 5. 后端 API（拟定）

说明：保持与现有 FastAPI 风格一致，返回 JSON；报告 HTML 通过静态路径或专用 endpoint 访问。

### 5.1 Common

- POST /api/v1/performance/quantstats/common
  - Request（两种之一）
    - JSON（回测）
      - stock_code: str
      - start: str (YYYY-MM-DD)
      - end: str (YYYY-MM-DD)
      - strategy_id: str
      - params: object
      - initial_cash: float
      - commission: float
      - benchmark_code: str | null
    - multipart/form-data（净值 CSV）
      - file: CSV（date/nav）
      - benchmark_code: str | null
  - Response
    - metrics: object
    - chart_series: object（ECharts 所需的数据序列）
    - report_url: str

### 5.2 Plus

- POST /api/v1/performance/quantstats/plus
  - Request（两种之一）
    - multipart/form-data（实盘 CSV）
      - files: CSV 文件列表
      - initial_cash: float
      - svd_window: int
      - svd_step: int
      - benchmark_code: str | null
    - JSON（回测组合）
      - items: array（{ stock_code, start, end, strategy_id, params, weight } 或 { instance_id, weight }）
      - initial_cash: float
      - commission: float
      - svd_window: int
      - svd_step: int
      - benchmark_code: str | null
  - Response
    - metrics: object
    - costs: object
    - per_stock: array
    - svd: object | null
    - chart_series: object
    - report_url: str

## 6. 数据与依赖

- 行情来源：沿用 Zoe 现有数据库读取逻辑（trade_stock_daily）
- 新依赖（后续开发阶段引入）：
  - quantstats
  - 不强制引入 matplotlib：页面图表默认用 ECharts 绘制

## 7. 验收标准（可验收项）

- 能在控制台看到“绩效分析”入口并正常打开页面
- Common 模式：
  - 用任意策略回测参数可生成指标并打开 HTML 报告
- Plus 模式：
  - 上传至少 1 份 CSV 可生成组合净值并生成报告
  - 当交易股票数 ≥ 3 且数据足够时，报告包含 SVD 状态与建议
- 报告与页面内容中文无乱码（UTF-8）
