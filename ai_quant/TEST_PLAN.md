# AI Quant 量化交易系统测试计划

## 1. 测试概述

### 1.1 项目背景
AI Quant 量化交易系统是一个集成 AI 能力的量化投资平台，提供智能研报生成、舆情监控、交易执行、风控管理等核心功能。

### 1.2 测试目标
- 确保系统功能完整性
- 验证 API 接口正确性
- 保证前端页面可用性
- 验证端到端业务流程

## 2. 测试范围

### 2.1 后端单元测试

#### 2.1.1 API 冒烟测试 (`test_api_smoke.py`)
**测试内容：**
- 健康检查接口 `/api/health`
- 用户认证接口
- 基础数据查询接口

**测试文件：** `ai_quant/backend/tests/test_api_smoke.py`
**优先级：** 高

#### 2.1.2 日志服务测试 (`test_logging_service.py`)
**测试内容：**
- 日志记录功能
- 日志查询接口
- 日志格式化

**测试文件：** `ai_quant/backend/tests/test_logging_service.py`
**优先级：** 中

#### 2.1.3 研报 API 测试 (`test_reports_api.py`)
**测试内容：**
- 研报创建接口
- 研报查询接口
- 研报状态管理

**测试文件：** `ai_quant/backend/tests/test_reports_api.py`
**优先级：** 高

#### 2.1.4 RAG 功能测试 (`test_reports_rag.py`)
**测试内容：**
- RAG 向量化
- 相似度查询
- 上下文检索

**测试文件：** `ai_quant/backend/tests/test_reports_rag.py`
**优先级：** 中

#### 2.1.5 MySQL 配置测试 (`test_mysql_config.py`)
**测试内容：**
- 数据库连接
- 配置加载
- 连接池管理

**测试文件：** `ai_quant/backend/tests/test_mysql_config.py`
**优先级：** 高

#### 2.1.6 QMT 网关代理测试 (`test_qmt_gateway_proxy.py`)
**测试内容：**
- QMT 网关连接
- 交易指令转发
- 账户查询

**测试文件：** `ai_quant/backend/tests/test_qmt_gateway_proxy.py`
**优先级：** 中

#### 2.1.7 Ethan 集成测试 (`test_ethan_embedded.py`)
**测试内容：**
- Ethan 模块初始化
- 交易策略执行
- 结果回传

**测试文件：** `ai_quant/backend/tests/test_ethan_embedded.py`
**优先级：** 中

#### 2.1.8 Zoe 信号逻辑测试 (`test_zoe_signals_logic.py`)
**测试内容：**
- 技术指标计算
- 信号生成逻辑
- 信号过滤

**测试文件：** `ai_quant/backend/tests/test_zoe_signals_logic.py`
**优先级：** 中

#### 2.1.9 Morning Brief 嵌入式测试 (`test_morning_brief_embedded.py`)
**测试内容：**
-晨报生成流程
- 数据聚合
- 模板渲染

**测试文件：** `ai_quant/backend/tests/test_morning_brief_embedded.py`
**优先级：** 低

#### 2.1.10 Bug 修复回归测试 (`test_bugfix_regressions.py`)
**测试内容：**
- 已知 Bug 修复验证
- 回归测试

**测试文件：** `ai_quant/backend/tests/test_bugfix_regressions.py`
**优先级：** 高

### 2.2 前端 E2E 测试

#### 2.2.1 基础功能测试 (`basic.spec.ts`)
**测试内容：**
- 页面导航
- 用户登录
- 基础交互

**测试文件：** `ai_quant/web/e2e/basic.spec.ts`
**测试工具：** Playwright
**优先级：** 高

#### 2.2.2 完整系统测试 (`full_system_test.spec.ts`)
**测试内容：**
- 端到端业务流程
- 多页面协作
- 数据一致性

**测试文件：** `ai_quant/web/e2e/full_system_test.spec.ts`
**测试工具：** Playwright
**优先级：** 高

#### 2.2.3 交易 API 测试 (`trading_api.spec.ts`)
**测试内容：**
- 交易接口集成
- 订单管理
- 持仓查询

**测试文件：** `ai_quant/web/e2e/trading_api.spec.ts`
**测试工具：** Playwright
**优先级：** 中

#### 2.2.4 研报 E2E 测试 (`report_e2e_tests.spec.ts`)
**测试内容：**
- 研报创建流程
- 研报查看流程
- RAG 功能

**测试文件：** `ai_quant/web/e2e/report_e2e_tests.spec.ts`
**测试工具：** Playwright
**优先级：** 高

## 3. 测试执行计划

### 3.1 每日构建测试
- **执行时间：** 每日凌晨 2:00
- **执行内容：** 所有单元测试
- **失败处理：** 发送告警通知

### 3.2 发布前测试
- **执行时间：** 每次发布前
- **执行内容：** 完整测试套件
- **通过标准：** 100% 通过率

### 3.3 手动测试场景
| 序号 | 测试场景 | 优先级 | 负责人员 |
|------|---------|--------|---------|
| 1 | 用户登录流程 | 高 | QA |
| 2 | 研报创建与查看 | 高 | QA |
| 3 | 交易下单流程 | 高 | QA |
| 4 | 风控规则配置 | 中 | QA |
| 5 | 晨报生成 | 中 | QA |

## 4. 测试环境要求

### 4.1 开发环境
- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Redis 6.0+

### 4.2 测试数据库
- 独立测试数据库实例
- 每日数据重置
- 隔离测试数据

### 4.3 外部依赖
- QMT 交易网关（测试环境）
- DeepSeek API（测试密钥）
- 行情数据服务（测试通道）

## 5. 测试数据管理

### 5.1 测试数据准备
- 使用 Faker 生成测试数据
- 保持测试数据独立性
- 定期更新测试数据集

### 5.2 敏感数据处理
- 测试数据脱敏
- API 密钥使用测试环境配置
- 数据库连接信息加密存储

## 6. 缺陷管理

### 6.1 缺陷严重等级
- **P0：** 系统崩溃、数据丢失
- **P1：** 核心功能不可用
- **P2：** 功能缺陷、性能问题
- **P3：** UI 问题、体验优化

### 6.2 缺陷修复周期
- P0: 2 小时内
- P1: 24 小时内
- P2: 1 周内
- P3: 2 周内

## 7. 测试报告

### 7.1 报告生成
- **自动化报告：** 每次构建后生成
- **周报：** 每周一汇总
- **月度报告：** 每月最后一天

### 7.2 报告内容
- 测试执行统计
- 缺陷分布分析
- 性能趋势
- 风险评估

## 8. 测试工具清单

| 工具名称 | 用途 | 版本要求 |
|---------|------|---------|
| pytest | Python 单元测试 | 7.0+ |
| Playwright | E2E 测试 | 1.40+ |
| pytest-cov | 测试覆盖率 | 4.0+ |
| allure | 测试报告 | 2.0+ |

## 9. 联系人和职责

| 角色 | 职责 | 联系方式 |
|------|------|---------|
| 测试负责人 | 测试计划制定、测试执行监督 | 待定 |
| 后端测试工程师 | 后端单元测试、E2E 测试 | 待定 |
| 前端测试工程师 | 前端 E2E 测试 | 待定 |
| DevOps | 测试环境维护、CI/CD | 待定 |

## 10. 附录

### A. 测试用例示例
详细测试用例请参考各测试文件内的 docstring。

### B. 常见问题
Q: 测试环境如何搭建？
A: 参考项目根目录的 `docker-compose.yml` 和部署文档。

Q: 如何运行单个测试？
A: `pytest tests/test_api_smoke.py -v`

Q: 如何查看测试覆盖率？
A: `pytest --cov=ai_quant_api tests/`

---

**文档版本：** 1.0  
**创建日期：** 2026-05-10  
**最后更新：** 2026-05-15  
**维护人：** AI Quant Team
