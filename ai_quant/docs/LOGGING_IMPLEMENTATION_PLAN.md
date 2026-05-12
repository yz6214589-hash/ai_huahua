# AI 量化交易系统日志系统开发计划

> 版本：1.0
> 日期：2026-05-11
> 作者：AI Quant Team
> 状态：待审批

---

## 一、项目概述

### 1.1 项目目标

为 ai_quant 系统设计并实现一个统一、集中、规范的日志系统，覆盖 11 个核心业务模块，共 139 个日志点。

### 1.2 项目范围

- **前端**：无（前端主要负责展示）
- **后端**：FastAPI 应用，11 个业务模块
- **日志系统**：统一日志服务、日志查询 API、日志文件管理
- **测试**：单元测试、集成测试、性能测试

### 1.3 项目周期

预计总工时：**5-7 个工作日**

---

## 二、技术方案

### 2.1 技术栈

- **Python 标准库**：`logging` 模块
- **文件轮转**：`logging.handlers.RotatingFileHandler`
- **异步优化**：`queue.Queue` + 独立线程
- **配置管理**：环境变量 + `dataclass`
- **API 框架**：FastAPI

### 2.2 核心组件

1. **日志服务**（`runtime/logging_service.py`）
   - `LoggerManager`：日志管理器（单例模式）
   - `get_logger()`：统一日志获取接口
   - `LoggingConfig`：日志配置数据类

2. **日志格式化器**（`runtime/logging_service.py`）
   - `UnifiedFormatter`：统一日志格式
   - 支持结构化日志输出

3. **敏感信息脱敏器**（`runtime/logging_service.py`）
   - `sanitize()`：脱敏函数
   - 支持 API Key、密码、手机号、身份证等

4. **日志轮转管理器**
   - 使用 `RotatingFileHandler`
   - 按大小轮转（10MB）
   - 保留 5 个备份

5. **HTTP 日志中间件**（`app.py`）
   - 记录所有 HTTP 请求
   - 包含请求参数、响应状态、执行时间

6. **日志查询 API**（`api/logs.py`）
   - `GET /api/logs`：日志查询
   - `GET /api/logs/stats`：日志统计

---

## 三、任务分解

### 阶段一：核心日志服务（第 1-2 天）

#### 任务 1.1：创建日志服务模块

**文件**：
- 创建：`backend/ai_quant_api/runtime/logging_service.py`

**步骤**：
1. 创建 `LoggingConfig` 数据类
2. 实现 `LoggerManager` 单例类
3. 实现 `get_logger()` 函数
4. 实现 `UnifiedFormatter` 格式化器
5. 实现 `sanitize()` 脱敏函数
6. 添加日志轮转配置

**验收标准**：
- `get_logger('reports')` 返回配置好的 logger
- 日志格式为：`[时间戳] [模块] [级别] 消息`
- 敏感信息自动脱敏

**测试用例**：
```python
def test_get_logger():
    logger = get_logger('reports')
    assert logger.name == 'reports'

def test_log_format():
    logger = get_logger('test')
    logger.info("测试消息", extra={"key": "value"})
    # 检查日志格式

def test_sanitize():
    assert sanitize("sk-abcdef1234567890") == "sk-ab...7890"
    assert sanitize("13812345678") == "138****5678"
```

---

#### 任务 1.2：集成日志服务到应用

**文件**：
- 修改：`backend/ai_quant_api/app.py`
- 修改：`backend/ai_quant_api/config.py`

**步骤**：
1. 在 `config.py` 中添加 `LoggingConfig` 配置
2. 在 `app.py` 中初始化日志系统
3. 在应用启动时打印启动日志
4. 在应用关闭时打印关闭日志

**验收标准**：
- 应用启动时输出启动日志
- 所有模块可以使用 `get_logger()` 获取日志实例

**测试用例**：
```python
def test_app_startup_logging():
    # 启动应用，检查启动日志
    pass

def test_logger_initialization():
    # 检查所有模块的 logger 都可以正常获取
    for module in MODULES:
        logger = get_logger(module)
        assert logger is not None
```

---

#### 任务 1.3：改造 reports 模块（智能研报）

**文件**：
- 修改：`backend/ai_quant_api/api/reports.py`
- 修改：`backend/ai_quant_api/services/reports/rag.py`

**覆盖点**：
- R001-R020（共 20 个日志点）

**步骤**：
1. 导入 `get_logger()`
2. 替换所有 `_report_log()` 为 `logger.info/error/warning/debug()`
3. 添加缺失的日志点
4. 确保结构化日志格式正确

**验收标准**：
- 所有 20 个日志点都已实现
- 日志格式统一
- 敏感信息已脱敏

**测试用例**：
```python
def test_reports_logging():
    logger = get_logger('reports')
    logger.info("任务创建", extra={"task_id": "test123"})
    # 检查日志文件

def test_llm_call_logging():
    # 模拟 LLM 调用，检查日志
    pass
```

---

### 阶段二：HTTP 日志中间件（第 0.5 天）

#### 任务 2.1：实现 HTTP 请求日志中间件

**文件**：
- 修改：`backend/ai_quant_api/app.py`

**覆盖点**：
- H001-H009（共 9 个日志点）

**步骤**：
1. 创建 HTTP 中间件函数
2. 记录请求开始、响应、错误
3. 记录请求参数和响应
4. 配置 `logs/http_access.log`

**验收标准**：
- 所有 HTTP 请求都记录到日志
- 日志包含请求方法、路径、状态码、耗时
- 错误请求记录完整的错误信息

**测试用例**：
```python
def test_http_logging():
    response = client.get("/api/reports/tasks")
    # 检查 http_access.log 文件
    pass
```

---

### 阶段三：其他模块改造（第 2-3 天）

#### 任务 3.1：改造 dashboard 和 data 模块

**文件**：
- 修改：`backend/ai_quant_api/api/summary.py`
- 修改：`backend/ai_quant_api/api/data_charles.py`

**覆盖点**：
- dashboard：D001-D007（7 个日志点）
- data：DA001-DA008（8 个日志点）

**验收标准**：
- dashboard 模块日志完整
- data 模块日志完整

---

#### 任务 3.2：改造 jobs 和 sentiment 模块

**文件**：
- 修改：`backend/ai_quant_api/api/jobs.py`
- 修改：`backend/ai_quant_api/api/sentiment.py`

**覆盖点**：
- jobs：J001-J017（17 个日志点）
- sentiment：S001-S011（11 个日志点）

**验收标准**：
- jobs 模块日志完整
- sentiment 模块日志完整

---

#### 任务 3.3：改造 morning 和 risk 模块

**文件**：
- 修改：`backend/ai_quant_api/api/console_ceo.py`
- 修改：`backend/ai_quant_api/api/risk_kris.py`

**覆盖点**：
- morning：M001-M012（12 个日志点）
- risk：K001-K010（10 个日志点）

**验收标准**：
- morning 模块日志完整
- risk 模块日志完整

---

#### 任务 3.4：改造 execution 和 watchlist 模块

**文件**：
- 修改：`backend/ai_quant_api/api/execution_ethan.py`
- 修改：`backend/ai_quant_api/api/watchlist.py`

**覆盖点**：
- execution：E001-E011（11 个日志点）
- watchlist：W001-W011（11 个日志点）

**验收标准**：
- execution 模块日志完整
- watchlist 模块日志完整

---

#### 任务 3.5：改造 strategy 和 ai 模块

**文件**：
- 修改：`backend/ai_quant_api/api/analysis_zoe.py`
- 修改：`backend/ai_quant_api/api/agent.py`

**覆盖点**：
- strategy：ST001-ST009（9 个日志点）
- ai：A001-A014（14 个日志点）

**验收标准**：
- strategy 模块日志完整
- ai 模块日志完整

---

### 阶段四：日志查询 API（第 1 天）

#### 任务 4.1：实现日志查询接口

**文件**：
- 创建：`backend/ai_quant_api/api/logs.py`

**步骤**：
1. 实现 `GET /api/logs` 接口
2. 支持按模块、级别、时间范围过滤
3. 支持关键词搜索
4. 支持分页

**验收标准**：
- 日志查询接口返回正确结果
- 过滤和分页功能正常

**测试用例**：
```python
def test_log_query():
    response = client.get("/api/logs?module=reports&level=ERROR")
    assert response.status_code == 200
    data = response.json()
    assert "logs" in data

def test_log_query_pagination():
    response = client.get("/api/logs?limit=10&offset=0")
    assert response.status_code == 200
```

---

#### 任务 4.2：实现日志统计接口

**文件**：
- 创建：`backend/ai_quant_api/api/logs.py`

**步骤**：
1. 实现 `GET /api/logs/stats` 接口
2. 统计各模块日志数量
3. 统计各级别日志数量
4. 统计磁盘使用情况

**验收标准**：
- 统计接口返回正确结果
- 数据准确

**测试用例**：
```python
def test_log_stats():
    response = client.get("/api/logs/stats")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "by_level" in data["summary"]
    assert "by_module" in data["summary"]
```

---

### 阶段五：优化和文档（第 0.5 天）

#### 任务 5.1：性能优化

**步骤**：
1. 添加异步日志写入队列
2. 批量写入优化
3. 内存缓冲优化

**验收标准**：
- 日志记录延迟 < 1ms
- 不影响业务处理性能

---

#### 任务 5.2：安全加固

**步骤**：
1. 添加日志访问认证
2. 验证敏感信息脱敏
3. 检查日志文件权限

**验收标准**：
- 日志查询需要认证
- 敏感信息完全脱敏

---

#### 任务 5.3：文档编写

**步骤**：
1. 编写使用文档
2. 编写运维手册
3. 更新代码注释

**验收标准**：
- 文档完整
- 代码注释清晰

---

## 四、时间安排

### 4.1 甘特图

| 阶段 | 任务 | 预计时间 | 累计时间 |
|------|------|---------|---------|
| 阶段一 | 核心日志服务 | 2 天 | 第 1-2 天 |
| 阶段二 | HTTP 日志中间件 | 0.5 天 | 第 2.5 天 |
| 阶段三 | 其他模块改造 | 2.5 天 | 第 5 天 |
| 阶段四 | 日志查询 API | 1 天 | 第 6 天 |
| 阶段五 | 优化和文档 | 0.5 天 | 第 6.5 天 |
| **总计** | | **6.5 天** | |

### 4.2 详细日程

#### 第 1 天
- [ ] 上午：创建日志服务模块（任务 1.1）
- [ ] 下午：集成日志服务到应用（任务 1.2）
- [ ] 晚上：改造 reports 模块（任务 1.3）

#### 第 2 天
- [ ] 上午：完成 reports 模块改造
- [ ] 下午：实现 HTTP 日志中间件（任务 2.1）
- [ ] 晚上：测试和修复

#### 第 3 天
- [ ] 上午：改造 dashboard 和 data 模块（任务 3.1）
- [ ] 下午：改造 jobs 和 sentiment 模块（任务 3.2）
- [ ] 晚上：测试和修复

#### 第 4 天
- [ ] 上午：改造 morning 和 risk 模块（任务 3.3）
- [ ] 下午：改造 execution 和 watchlist 模块（任务 3.4）
- [ ] 晚上：测试和修复

#### 第 5 天
- [ ] 上午：改造 strategy 和 ai 模块（任务 3.5）
- [ ] 下午：实现日志查询 API（任务 4.1）
- [ ] 晚上：测试和修复

#### 第 6 天
- [ ] 上午：实现日志统计 API（任务 4.2）
- [ ] 下午：性能优化和安全加固（任务 5.1、5.2）
- [ ] 晚上：编写文档（任务 5.3）

#### 第 7 天（备用）
- [ ] 整体测试
- [ ] Bug 修复
- [ ] 部署上线

---

## 五、资源需求

### 5.1 人力资源

- **开发人员**：1 人
- **测试人员**：1 人（可兼职）

### 5.2 环境需求

- **开发环境**：本地开发环境
- **测试环境**：测试服务器
- **生产环境**：生产服务器

### 5.3 工具需求

- **版本控制**：Git
- **代码审查**：Pull Request
- **CI/CD**：GitHub Actions（可选）

---

## 六、风险评估

### 6.1 技术风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 日志影响性能 | 高 | 中 | 使用异步写入、批量处理 |
| 日志格式不统一 | 中 | 中 | 统一规范、代码审查 |
| 轮转策略失效 | 中 | 低 | 监控检查、手动触发 |

### 6.2 进度风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 任务延期 | 中 | 中 | 预留缓冲时间 |
| Bug 修复 | 中 | 中 | 预留第 7 天 |

### 6.3 资源风险

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| 环境问题 | 低 | 低 | 提前准备环境 |

---

## 七、验收标准

### 7.1 功能验收

- [ ] 所有 139 个日志点都已实现
- [ ] 日志格式统一规范
- [ ] 敏感信息已脱敏
- [ ] 日志轮转正常工作
- [ ] 日志查询 API 正常
- [ ] 日志统计 API 正常

### 7.2 性能验收

- [ ] 日志记录延迟 < 1ms
- [ ] 不影响业务处理性能
- [ ] 并发写入正常

### 7.3 安全验收

- [ ] 日志访问需要认证
- [ ] 敏感信息完全脱敏
- [ ] 日志文件权限正确

### 7.4 文档验收

- [ ] 使用文档完整
- [ ] 运维手册完整
- [ ] 代码注释清晰

---

## 八、后续维护

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

本开发计划详细描述了日志系统的实施步骤，包括：

1. **阶段划分**：5 个阶段，共 6.5 个工作日
2. **任务分解**：13 个主要任务
3. **时间安排**：详细的甘特图和日程
4. **资源需求**：明确的人力和环境需求
5. **风险评估**：识别潜在风险和应对措施
6. **验收标准**：明确的功能、性能、安全和文档标准

通过执行本计划，将为 ai_quant 系统构建一个统一、规范、可观测的日志系统，为后续的运维和问题排查提供有力支持。
