# AI Quant 一键启动脚本

## 简介

`start_all.sh` 是一个用于 macOS 系统的启动脚本，可以一键启动 AI Quant 智能量化投资系统的所有服务。

## 功能特性

- ✅ **环境检查**: 自动检测 Python、Node.js、npm、pip 等依赖
- ✅ **端口检测**: 检查端口占用情况，避免冲突
- ✅ **顺序启动**: 按正确顺序启动服务（后端 → 前端/AI对话）
- ✅ **状态显示**: 实时显示每个服务的启动状态和访问链接
- ✅ **错误处理**: 服务启动失败时记录日志并优雅终止
- ✅ **多模式支持**: 支持开发模式和生产模式
- ✅ **后台运行**: 支持后台运行模式

## 服务说明

| 服务 | 端口 | 技术栈 | 访问地址 |
|------|------|--------|----------|
| 后端 API | 8010 | FastAPI + LangGraph | http://127.0.0.1:8010 |
| 前端应用 | 5173 | React + Vite | http://localhost:5173 |
| AI 对话机器人 | 8501 | Streamlit | http://localhost:8501 |

## 快速开始

### 1. 首次使用

```bash
cd /Users/apple/Desktop/ai_huahua/ai_quant/scripts
chmod +x start_all.sh
./start_all.sh
```

### 2. 启动所有服务

```bash
# 开发模式启动（默认，包含热重载）
./start_all.sh

# 开发模式启动（显式指定）
./start_all.sh -d

# 生产模式启动
./start_all.sh -p

# 后台运行
./start_all.sh -b
```

### 3. 管理服务

```bash
# 查看服务状态
./start_all.sh -s

# 停止所有服务
./start_all.sh -k

# 查看帮助
./start_all.sh -h
```

## 命令行选项

| 选项 | 说明 |
|------|------|
| `-d, --dev` | 开发模式（默认），包含热重载功能 |
| `-p, --prod` | 生产模式，禁用热重载 |
| `-b, --background` | 后台运行模式 |
| `-s, --status` | 查看服务状态 |
| `-k, --kill` | 停止所有服务 |
| `-h, --help` | 显示帮助信息 |

## 使用示例

### 启动并保持前台运行

```bash
./start_all.sh
# 输出：
# ╔══════════════════════════════════════════════════════════════╗
# ║              AI Quant 智能量化投资系统                    ║
# ╚══════════════════════════════════════════════════════════════╝
#
# [INFO] 检查依赖环境...
# [DONE] Python 3 已安装 (版本: 3.11)
# [DONE] Node.js 已安装 (版本: 20.0)
# ...
# [DONE] 所有服务启动成功!
#
# 访问链接:
#   后端API:    http://127.0.0.1:8010
#   前端应用:   http://localhost:5173
#   AI对话机器人: http://localhost:8501
```

### 后台运行

```bash
./start_all.sh -b
# 服务将在后台运行，可以通过以下命令查看状态
./start_all.sh -s
```

### 停止所有服务

```bash
./start_all.sh -k
```

## 日志文件

日志文件保存在 `${PROJECT_ROOT}/logs/` 目录下：

```
logs/
├── startup_20260101_120000.log    # 启动日志
├── backend.log                     # 后端日志
├── frontend.log                    # 前端日志
└── streamlit.log                  # AI对话日志
```

## 故障排除

### 端口被占用

如果提示端口被占用，可以选择停止现有服务或手动释放端口：

```bash
# 查看端口占用
lsof -i :8010
lsof -i :5173
lsof -i :8501

# 停止占用端口的进程
kill -9 <PID>
```

### 依赖缺失

如果提示依赖缺失，请安装：

```bash
# 使用 Homebrew 安装依赖
brew install python@3.11 node

# 安装 Python 依赖
cd /Users/apple/Desktop/ai_huahua/ai_quant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 安装前端依赖
cd web
npm install
```

### 虚拟环境

脚本会自动检测项目根目录下的 `venv` 目录。如果使用其他虚拟环境，请确保激活后再运行脚本。

## 高级用法

### 自定义端口

编辑 `start_all.sh` 文件中的 `PORTS` 数组：

```bash
declare -A PORTS=(
    ["backend"]=9000      # 自定义后端端口
    ["frontend"]=3000     # 自定义前端端口
    ["streamlit"]=8502     # 自定义Streamlit端口
)
```

### 添加新服务

在 `start_all.sh` 中添加新的服务配置：

```bash
# 在 SERVICES、PORTS、URLS 数组中添加新服务
declare -A SERVICES=(
    ["backend"]="FastAPI 后端服务:8010"
    ["frontend"]="React 前端服务:5173"
    ["streamlit"]="Streamlit AI对话:8501"
    ["new_service"]="新服务:9000"  # 添加新服务
)
```

## 技术细节

### 启动顺序

1. **后端 API** (优先级最高)
   - 提供 REST API 接口
   - 其他服务依赖其 API

2. **前端应用** 和 **AI 对话机器人** (并行启动)
   - 依赖后端 API
   - 可以独立访问

### 健康检查

脚本使用 HTTP 请求检查服务是否启动成功：

```bash
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8010"
```

### 信号处理

脚本捕获以下信号以优雅关闭服务：

- `SIGINT` (Ctrl+C)
- `SIGTERM` (终止信号)

## 许可证

本项目仅供学习参考使用。

## 联系方式

如有问题，请提交 Issue 或联系开发团队。
