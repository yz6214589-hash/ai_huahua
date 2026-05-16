# AI Quant 智能量化投资系统 - 部署前置准备指南

## 目录

1. [系统环境要求](#1-系统环境要求)
2. [Python 环境准备](#2-python-环境准备)
3. [依赖安装](#3-依赖安装)
4. [数据库配置](#4-数据库配置)
5. [环境变量配置](#5-环境变量配置)
6. [项目结构说明](#6-项目结构说明)
7. [启动服务](#7-启动服务)
8. [可选技能工具包安装](#8-可选技能工具包安装)
9. [常见部署问题排查](#9-常见部署问题排查)

---

## 1. 系统环境要求

### 操作系统

| 系统 | 支持情况 | 说明 |
|------|---------|------|
| macOS 12+ | 完全支持 | 本项目的开发和运行环境 |
| Linux (Ubuntu 20.04+/CentOS 7+) | 完全支持 | 生产环境推荐 |
| Windows 10/11 | 部分支持 | QMT 交易功能仅限 Windows |

### 基础软件

| 软件 | 最低版本 | 推荐版本 | 用途 |
|-----|---------|---------|------|
| Python | 3.10 | 3.10.7 | 后端运行环境 |
| Node.js | 18.x | 20.x | 前端构建运行 |
| npm | 8.x | 10.x | 前端包管理 |
| MySQL | 8.0 | 8.0+ | 业务数据存储（可选） |

### 硬件建议

| 部署规模 | CPU | 内存 | 磁盘 |
|---------|-----|------|------|
| 开发环境 | 4 核 | 8 GB | 20 GB |
| 生产环境 | 8 核 | 16 GB | 50 GB |

---

## 2. Python 环境准备

### 2.1 安装 Python 3.10

**macOS：**

```bash
# 使用 Homebrew 安装
brew install python@3.10

# 验证安装
python3.10 --version
```

**Ubuntu/Debian：**

```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-dev
```

**Windows：**

下载 Python 3.10 安装包：[https://www.python.org/downloads/](https://www.python.org/downloads/)

### 2.2 创建虚拟环境

在项目根目录下创建并激活 Python 虚拟环境：

```bash
# 进入项目目录
cd /path/to/ai_quant

# 创建虚拟环境（使用 Python 3.10）
python3.10 -m venv venv

# 激活虚拟环境
# macOS / Linux:
source venv/bin/activate

# Windows:
# .\venv\Scripts\activate
```

激活后，终端提示符前会出现 `(venv)` 标识。

---

## 3. 依赖安装

### 3.1 Python 依赖

确保虚拟环境已激活，然后执行：

```bash
# 升级 pip
pip install --upgrade pip

# 安装项目依赖（自动从 requirements.txt 读取）
pip install -r requirements.txt
```

如果安装速度慢，可使用国内镜像源：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3.2 Playwright 浏览器驱动（可选）

如需运行 UI 自动化测试，需额外安装 Playwright 浏览器：

```bash
# 安装 Chromium 浏览器驱动
playwright install chromium

# 或指定路径安装
python -m playwright install chromium
```

### 3.3 Node.js 前端依赖

```bash
cd web
npm install
```

---

## 4. 数据库配置

### 4.1 MySQL 数据库（核心业务数据）

本项目使用 MySQL 存储股票行情、财务数据、交易信号等核心业务数据。

**创建数据库：**

```sql
CREATE DATABASE IF NOT EXISTS huahua_trade
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
```

**执行数据库迁移：**

```bash
# 确保 MySQL 服务已启动，且环境变量已配置
cd backend
python migrations_sqlite.py
```

MySQL 连接参数通过以下环境变量配置（详见第 5 节）：

| 变量名 | 说明 | 默认值 |
|-------|------|-------|
| `WUCAI_SQL_HOST` | 数据库主机地址 | `127.0.0.1` |
| `WUCAI_SQL_PORT` | 数据库端口 | `3306` |
| `WUCAI_SQL_USERNAME` | 数据库用户名 | `root` |
| `WUCAI_SQL_PASSWORD` | 数据库密码 | 空 |
| `WUCAI_SQL_DB` | 数据库名称 | `huahua_trade` |

### 4.2 SQLite（无数据库模式）

如果不想使用 MySQL，系统会自动降级为 SQLite 本地存储，所有数据保存在 `.ai_quant/` 目录下。此模式适合开发测试，不建议生产环境使用。

---

## 5. 环境变量配置

### 5.1 核心配置

在项目根目录创建 `.env` 文件（可直接复制 `.env.example`）：

```bash
cp .env.example .env
```

### 5.2 完整环境变量清单

#### 应用配置

| 变量名 | 说明 | 默认值 | 必填 |
|-------|------|-------|------|
| `AI_QUANT_API_BASE` | API 基础地址 | `http://localhost:8000` | 否 |
| `AI_QUANT_CORS_ORIGINS` | 允许的 CORS 来源（逗号分隔） | `http://localhost:5173` | 否 |
| `AI_QUANT_API_KEY` | API 访问密钥（留空不启用认证） | 空 | 否 |
| `AI_QUANT_RATE_LIMIT_WINDOW_SECONDS` | 速率限制时间窗口（秒） | `10` | 否 |
| `AI_QUANT_RATE_LIMIT_MAX` | 速率限制最大请求数 | `200` | 否 |

#### 数据库配置

| 变量名 | 说明 | 默认值 | 必填 |
|-------|------|-------|------|
| `WUCAI_SQL_HOST` | MySQL 主机地址 | `127.0.0.1` | 否 |
| `WUCAI_SQL_PORT` | MySQL 端口 | `3306` | 否 |
| `WUCAI_SQL_USERNAME` | MySQL 用户名 | `root` | 否 |
| `WUCAI_SQL_PASSWORD` | MySQL 密码 | 空 | 否 |
| `WUCAI_SQL_DB` | MySQL 数据库名 | `huahua_trade` | 否 |

支持兼容别名：`DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME`、`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB`

#### AI/LLM 配置

| 变量名 | 说明 | 默认值 | 必填 |
|-------|------|-------|:----:|
| `DASHSCOPE_API_KEY` | 阿里云百炼 DashScope API 密钥 | 空 | **是** |
| `OPENAI_API_KEY` | OpenAI API 密钥 | 空 | 否 |
| `TAVILY_API_KEY` | Tavily 网络搜索 API 密钥 | 空 | 否 |
| `QWEN_MODEL` | 通义千问模型名称 | `qwen-max` | 否 |
| `CHARLES_MODEL` | 数据采集 Agent 模型 | `qwen-plus` | 否 |
| `TUSHARE_TOKEN` | Tushare 金融数据 Token | 空 | 否 |

#### 日志配置

| 变量名 | 说明 | 默认值 |
|-------|------|-------|
| `AI_QUANT_LOG_DIR` | 日志文件存储目录 | `.ai_quant/logs` |
| `AI_QUANT_LOG_LEVEL` | 日志级别 | `INFO` |
| `AI_QUANT_LOG_MAX_BYTES` | 单个日志文件最大字节数 | `10485760`（10MB） |
| `AI_QUANT_LOG_BACKUP_COUNT` | 保留的备份日志文件数 | `5` |
| `AI_QUANT_LOG_CONSOLE` | 是否输出到控制台 | `true` |
| `AI_QUANT_LOG_FILE` | 是否输出到文件 | `true` |

#### 报告/研报配置

| 变量名 | 说明 | 默认值 |
|-------|------|-------|
| `AI_QUANT_REPORT_OUTPUT_DIR` | 研报输出目录 | `.ai_quant/report_outputs` |
| `AI_QUANT_REPORT_USE_LLM` | 是否使用 LLM 生成研报 | `false` |
| `AI_QUANT_REPORT_LLM_TIMEOUT_SECONDS` | LLM 调用超时（秒） | `90` |
| `AI_QUANT_REPORT_TIMEOUT_SECONDS` | 报告生成超时（秒） | `300` |
| `AI_QUANT_REPORT_MYSQL_ENABLED` | 是否开启 MySQL 存储报告 | `1` |
| `AI_QUANT_REPORT_RAG_PDF_DIR` | RAG PDF 文件目录 | `.ai_quant/report_pdfs` |
| `AI_QUANT_REPORT_RAG_DB_PATH` | RAG 数据库路径 | `.ai_quant/documents.db` |
| `AI_QUANT_REPORT_INDEX_DIR` | RAG 向量索引目录 | `.ai_quant/vector_store` |

#### QMT 交易网关配置

| 变量名 | 说明 | 默认值 |
|-------|------|-------|
| `AI_QUANT_QMT_GATEWAY_BASE` | QMT 网关基础地址 | `http://127.0.0.1:58080` |
| `AI_QUANT_QMT_GATEWAY_TOKEN` | QMT 网关访问令牌 | 空 |
| `QMT_PATH` | QMT 客户端安装路径 | 空 |
| `ACCOUNT_ID` | QMT 交易账号 | 空 |

### 5.3 `.env` 文件示例

```bash
# ============================================
# AI Quant 系统环境配置
# ============================================

# API 配置
AI_QUANT_API_BASE=http://localhost:8000
AI_QUANT_CORS_ORIGINS=http://localhost:5173

# 数据库配置（MySQL）
WUCAI_SQL_HOST=127.0.0.1
WUCAI_SQL_PORT=3306
WUCAI_SQL_USERNAME=root
WUCAI_SQL_PASSWORD=your_password
WUCAI_SQL_DB=huahua_trade

# AI/LLM 配置
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 日志配置
AI_QUANT_LOG_LEVEL=INFO
AI_QUANT_LOG_CONSOLE=true
```

---

## 6. 项目结构说明

```
ai_quant/
├── backend/               # Python 后端（FastAPI）
│   ├── app.py            # FastAPI 应用入口
│   ├── config.py         # 配置管理
│   ├── api/              # API 路由层
│   ├── core/             # 核心业务逻辑
│   │   ├── analysis/     # 技术分析
│   │   ├── console/      # CEO 控制台 / 晨会简报
│   │   ├── execution/    # 执行引擎
│   │   ├── jobs/         # 定时任务（数据采集）
│   │   └── risk/         # 风控中心
│   ├── infra/            # 基础设施
│   │   ├── storage/      # 数据持久化
│   │   └── reports/      # RAG 检索增强生成
│   ├── agents/           # AI 智能体
│   ├── workflow/         # LangGraph 工作流
│   └── llm/              # LLM 集成（技能工具包）
├── web/                   # 前端（React + Vite）
├── streamlit_chat/        # AI 对话机器人（Streamlit）
├── scripts/               # 部署脚本
│   └── start_all.sh      # 一键启动脚本（macOS）
├── docs/                  # 文档
├── requirements.txt       # Python 依赖清单
└── .env                   # 环境变量配置
```

---

## 7. 启动服务

### 7.1 一键启动（macOS）

```bash
# 赋予执行权限
chmod +x scripts/start_all.sh

# 开发模式启动
./scripts/start_all.sh

# 查看服务状态
./scripts/start_all.sh -s

# 停止所有服务
./scripts/start_all.sh -k
```

### 7.2 手动启动

#### 后端 API 服务（FastAPI）

```bash
# 激活虚拟环境
source venv/bin/activate

# 从项目根目录启动（必须，因代码使用相对导入）
cd /path/to/ai_quant
PYTHONPATH=backend uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

#### 前端应用（React + Vite）

```bash
cd web
npm run dev
```

#### AI 对话机器人（Streamlit）

```bash
source venv/bin/activate
cd streamlit_chat
streamlit run app.py --server.port 8501
```

### 7.3 验证服务

| 服务 | 地址 | 验证方式 |
|-----|------|---------|
| 后端 API | `http://127.0.0.1:8000` | `curl http://127.0.0.1:8000/health` |
| API 文档 | `http://127.0.0.1:8000/docs` | 浏览器打开 |
| 前端应用 | `http://localhost:5173` | 浏览器打开 |
| AI 对话 | `http://localhost:8501` | 浏览器打开 |

---

## 8. 可选技能工具包安装

以下包仅在调用特定 AI 技能时需要，不是核心服务运行的必需依赖：

### 技能包一览

| 包名 | 技能用途 | 安装命令 |
|-----|---------|---------|
| jieba | 研报 PDF 检索（中文分词） | `pip install jieba` |
| rank-bm25 | 研报 PDF 检索（文本排序） | `pip install rank-bm25` |
| TA-Lib | 技术分析指标计算 | `pip install TA-Lib` |
| backtrader | 策略回测框架 | `pip install backtrader` |
| xtquant | QMT 量化交易终端 SDK | `pip install xtquant`（仅 Windows） |

> **注意**：TA-Lib 在 macOS 上需先通过 Homebrew 安装底层库：
> ```bash
> brew install ta-lib
> pip install TA-Lib
> ```

> **注意**：xtquant 是迅投 QMT 终端的 Python SDK，仅支持 Windows 环境。

---

## 9. 常见部署问题排查

### 9.1 Python 版本不匹配

**问题**：`ImportError: attempted relative import with no known parent package`

**原因**：从 `backend/` 目录直接运行 `uvicorn app:app` 导致相对导入失败。

**解决**：必须从项目根目录启动，并指定 `PYTHONPATH`：
```bash
cd /path/to/ai_quant
PYTHONPATH=backend uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

### 9.2 MySQL 连接失败

**问题**：`pymysql.err.OperationalError: Can't connect to MySQL server`

**原因**：MySQL 服务未启动或连接参数配置错误。

**解决步骤**：

1. 检查 MySQL 是否运行：
   ```bash
   # macOS
   brew services list | grep mysql
   
   # Linux
   systemctl status mysql
   ```

2. 确认环境变量配置正确（见第 5.2 节数据库配置）。

3. 如果不需要 MySQL，可设置环境变量让系统使用 SQLite 降级运行。

### 9.3 DashScope API 密钥缺失

**问题**：`RuntimeError: missing env: DASHSCOPE_API_KEY`

**原因**：未配置阿里云百炼 API 密钥。

**解决**：在 `.env` 文件中设置：
```bash
DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 9.4 端口冲突

**问题**：`Address already in use` 或端口被占用。

**解决**：

```bash
# 查看端口占用
lsof -i :8000

# 停止占用进程
kill -9 <PID>

# 或使用一键脚本停止所有服务
./scripts/start_all.sh -k
```

### 9.5 Streamlit 运行警告

**问题**：Streamlit 提示 `For better performance, install the Watchdog module`

**解决**：
```bash
pip install watchdog
```

### 9.6 Playwright 浏览器驱动缺失

**问题**：`playwright._impl._errors.Error: Executable doesn't exist`

**解决**：
```bash
playwright install chromium
# 或指定 playwright-core 路径
python -m playwright install chromium
```

### 9.7 依赖安装冲突

**问题**：`pip install` 时出现版本冲突。

**解决步骤**：

1. 使用虚拟环境隔离依赖：
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. 先升级 pip：
   ```bash
   pip install --upgrade pip
   ```

3. 使用镜像源安装：
   ```bash
   pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

4. 如仍有冲突，尝试逐个安装核心包：
   ```bash
   pip install fastapi uvicorn[standard] pydantic
   pip install numpy pandas
   pip install akshare
   # 按依赖分类逐一安装
   ```

### 9.8 macOS 特定问题

**问题**：`ValueError: unknown locale: UTF-8`

**解决**：在 `~/.zshrc` 中添加：
```bash
export LC_ALL=en_US.UTF-8
export LANG=en_US.UTF-8
```

**问题**：`pip install` 编译失败（如 TA-Lib、cffi 等含 C 扩展的包）

**解决**：先安装 Xcode Command Line Tools：
```bash
xcode-select --install
brew install pkg-config
```

---

## 附录：环境验证检查清单

部署完成后，请逐项确认：

- [ ] Python 3.10+ 已安装
- [ ] 虚拟环境已创建并激活
- [ ] `pip install -r requirements.txt` 执行成功
- [ ] `web/node_modules` 已创建（`npm install` 成功）
- [ ] `.env` 配置文件已创建（从 `.env.example` 复制）
- [ ] `DASHSCOPE_API_KEY` 已配置
- [ ] MySQL 服务运行中（或者接受 SQLite 降级模式）
- [ ] 后端服务可正常启动（`uvicorn backend.app:app`）
- [ ] 前端服务可正常启动（`npm run dev`）
- [ ] 各服务间通信正常（前端能通过代理访问后端）
