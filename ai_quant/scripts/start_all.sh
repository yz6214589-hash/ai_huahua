#!/bin/bash

#==============================================================================
# AI Quant 一键启动脚本 (macOS)
# 
# 功能: 同时启动后端API，前端应用、AI对话机器人三个服务
# 
# 使用方法:
#   ./start_all.sh [选项]
# 
# 选项:
#   -d, --dev       开发模式 (默认)
#   -p, --prod      生产模式
#   -b, --background 后台运行
#   -h, --help      显示帮助信息
#   -s, --status    查看服务状态
#   -k, --kill      停止所有服务
#==============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="${PROJECT_ROOT}/backend"
FRONTEND_DIR="${PROJECT_ROOT}/web"
STREAMLIT_DIR="${PROJECT_ROOT}/streamlit_chat"

# 服务配置
PORT_BACKEND=8010
PORT_FRONTEND=5173
PORT_STREAMLIT=8501

URL_BACKEND="http://127.0.0.1:8010"
URL_FRONTEND="http://localhost:5173"
URL_STREAMLIT="http://localhost:8501"

# 全局变量
MODE="dev"
BACKGROUND=false
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/startup_$(date '+%Y%m%d_%H%M%S').log"

#==============================================================================
# 辅助函数
#==============================================================================

log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local color="$NC"
    
    case "$level" in
        "INFO")  color="$GREEN" ;;
        "WARN")  color="$YELLOW" ;;
        "ERROR") color="$RED" ;;
        "START") color="$BLUE" ;;
        "DONE")  color="$GREEN" ;;
        *)       color="$NC" ;;
    esac
    
    echo -e "${color}[${timestamp}] [${level}] ${message}${NC}" | tee -a "$LOG_FILE" 2>/dev/null || echo "[${timestamp}] [${level}] ${message}"
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

check_port() {
    local port="$1"
    lsof -i :"$port" >/dev/null 2>&1
}

get_pid_by_port() {
    local port="$1"
    # 过滤掉浏览器进程（Chrome、Trae等），只获取服务器进程（node、python等）
    lsof -ti :"$port" 2>/dev/null | grep -E "^[0-9]+$" | while read pid; do
        local cmd=$(ps -p "$pid" -o comm= 2>/dev/null)
        # 转换为小写以忽略大小写
        local cmd_lower=$(echo "$cmd" | tr '[:upper:]' '[:lower:]')
        # 匹配node服务器、Python进程（通过uvicorn启动）、streamlit等
        if [[ "$cmd_lower" =~ ^(node|python|uvicorn|streamlit)$ ]] || [[ "$cmd_lower" == *python* ]]; then
            echo "$pid"
            return 0
        fi
    done | head -1
}

kill_by_port() {
    local port="$1"
    local pid=$(get_pid_by_port "$port")
    if [ -n "$pid" ]; then
        kill "$pid" 2>/dev/null && return 0 || return 1
    fi
    return 0
}

get_python_version() {
    python3 --version 2>&1 | awk '{print $2}'
}

get_node_version() {
    node --version 2>&1 | sed 's/v//'
}

get_npm_version() {
    npm --version 2>&1
}

#==============================================================================
# 环境检查
#==============================================================================

check_dependencies() {
    log "INFO" "检查依赖环境..."
    
    local missing=""
    
    # 检查 Python
    if check_command python3; then
        local python_version=$(get_python_version)
        log "DONE" "Python 3 已安装 (版本: $python_version)"
    else
        missing="${missing} Python 3"
    fi
    
    # 检查 Node.js
    if check_command node; then
        local node_version=$(get_node_version)
        log "DONE" "Node.js 已安装 (版本: $node_version)"
    else
        missing="${missing} Node.js"
    fi
    
    # 检查 npm
    if check_command npm; then
        local npm_version=$(get_npm_version)
        log "DONE" "npm 已安装 (版本: $npm_version)"
    else
        missing="${missing} npm"
    fi
    
    # 检查 pip
    if check_command pip3; then
        log "DONE" "pip3 已安装"
    else
        missing="${missing} pip3"
    fi
    
    # 检查虚拟环境
    local venv_path="${PROJECT_ROOT}/venv"
    if [ -d "$venv_path" ]; then
        log "DONE" "Python 虚拟环境已创建"
    else
        log "WARN" "Python 虚拟环境未创建（将使用系统 Python）"
    fi
    
    # 报告缺失依赖
    if [ -n "$missing" ]; then
        log "ERROR" "缺少以下依赖:$missing"
        log "INFO" "请运行以下命令安装:"
        log "INFO" "  brew install python@3.11 node"
        return 1
    fi
    
    log "DONE" "环境检查完成"
    return 0
}

#==============================================================================
# 端口检查
#==============================================================================

check_ports() {
    log "INFO" "检查端口占用情况..."
    
    local occupied=""
    local all_free=true
    
    # 检查后端端口
    if check_port "$PORT_BACKEND"; then
        local pid=$(get_pid_by_port "$PORT_BACKEND")
        occupied="${occupied} 后端:$PORT_BACKEND(PID:$pid)"
        log "WARN" "后端端口 $PORT_BACKEND 已被占用 (PID: $pid)"
        all_free=false
    else
        log "DONE" "后端端口 $PORT_BACKEND 可用"
    fi
    
    # 检查前端端口
    if check_port "$PORT_FRONTEND"; then
        local pid=$(get_pid_by_port "$PORT_FRONTEND")
        occupied="${occupied} 前端:$PORT_FRONTEND(PID:$pid)"
        log "WARN" "前端端口 $PORT_FRONTEND 已被占用 (PID: $pid)"
        all_free=false
    else
        log "DONE" "前端端口 $PORT_FRONTEND 可用"
    fi
    
    # 检查Streamlit端口
    if check_port "$PORT_STREAMLIT"; then
        local pid=$(get_pid_by_port "$PORT_STREAMLIT")
        occupied="${occupied} Streamlit:$PORT_STREAMLIT(PID:$pid)"
        log "WARN" "Streamlit端口 $PORT_STREAMLIT 已被占用 (PID: $pid)"
        all_free=false
    else
        log "DONE" "Streamlit端口 $PORT_STREAMLIT 可用"
    fi
    
    if [ "$all_free" = false ]; then
        return 1
    fi
    
    return 0
}

kill_services() {
    log "INFO" "停止已运行的服务..."
    
    for port in $PORT_BACKEND $PORT_FRONTEND $PORT_STREAMLIT; do
        if kill_by_port "$port"; then
            log "DONE" "已停止端口 $port"
        fi
    done
    
    sleep 1
}

#==============================================================================
# 服务启动函数
#==============================================================================

start_backend() {
    log "START" "启动后端API服务..."
    
    local cmd="cd '${BACKEND_DIR}' && PYTHONPATH=. python3 -m uvicorn app:app --host 127.0.0.1 --port ${PORT_BACKEND}"
    
    if [ "$MODE" = "dev" ]; then
        cmd="$cmd --reload"
    fi
    
    if [ "$BACKGROUND" = true ]; then
        eval "$cmd > '${LOG_DIR}/backend.log' 2>&1 &"
        sleep 2
    else
        eval "$cmd" &
    fi
    
    sleep 3
    
    if check_port "$PORT_BACKEND"; then
        local actual_pid=$(get_pid_by_port "$PORT_BACKEND")
        log "DONE" "后端API已启动 (PID: $actual_pid, URL: ${URL_BACKEND})"
        return 0
    else
        log "ERROR" "后端API启动失败"
        return 1
    fi
}

start_frontend() {
    log "START" "启动前端应用..."
    
    # 检查 node_modules
    if [ ! -d "${FRONTEND_DIR}/node_modules" ]; then
        log "INFO" "正在安装前端依赖..."
        cd "${FRONTEND_DIR}" && npm install
    fi
    
    local cmd="cd '${FRONTEND_DIR}' && npm run dev"
    
    if [ "$BACKGROUND" = true ]; then
        eval "$cmd > '${LOG_DIR}/frontend.log' 2>&1 &"
        sleep 5
    else
        eval "$cmd" &
    fi
    
    sleep 5
    
    if check_port "$PORT_FRONTEND"; then
        local actual_pid=$(get_pid_by_port "$PORT_FRONTEND")
        log "DONE" "前端已启动 (PID: $actual_pid, URL: ${URL_FRONTEND})"
        return 0
    else
        log "ERROR" "前端启动失败"
        return 1
    fi
}

start_streamlit() {
    log "START" "启动AI对话机器人..."
    
    local app_file="${STREAMLIT_DIR}/app.py"
    
    if [ ! -f "$app_file" ]; then
        log "ERROR" "Streamlit 应用文件不存在: $app_file"
        return 1
    fi
    
    local cmd="cd '${STREAMLIT_DIR}' && python3 -m streamlit run app.py --server.port ${PORT_STREAMLIT} --server.headless true"
    
    if [ "$BACKGROUND" = true ]; then
        eval "$cmd > '${LOG_DIR}/streamlit.log' 2>&1 &"
        sleep 5
    else
        eval "$cmd" &
    fi
    
    sleep 5
    
    if check_port "$PORT_STREAMLIT"; then
        local actual_pid=$(get_pid_by_port "$PORT_STREAMLIT")
        log "DONE" "AI对话机器人已启动 (PID: $actual_pid, URL: ${URL_STREAMLIT})"
        return 0
    else
        log "ERROR" "AI对话机器人启动失败"
        return 1
    fi
}

#==============================================================================
# 服务管理
#==============================================================================

show_status() {
    echo ""
    echo "=============================================="
    echo "       AI Quant 服务状态"
    echo "=============================================="
    echo ""
    
    # 后端
    printf "%-20s " "FastAPI 后端服务:8010"
    if check_port "$PORT_BACKEND"; then
        local pid=$(get_pid_by_port "$PORT_BACKEND")
        printf "${GREEN}● 运行中${NC} (PID: %s)\n" "$pid"
        printf "  ${CYAN}%s${NC}\n" "$URL_BACKEND"
    else
        printf "${RED}○ 已停止${NC}\n"
    fi
    echo ""
    
    # 前端
    printf "%-20s " "React 前端服务:5173"
    if check_port "$PORT_FRONTEND"; then
        local pid=$(get_pid_by_port "$PORT_FRONTEND")
        printf "${GREEN}● 运行中${NC} (PID: %s)\n" "$pid"
        printf "  ${CYAN}%s${NC}\n" "$URL_FRONTEND"
    else
        printf "${RED}○ 已停止${NC}\n"
    fi
    echo ""
    
    # Streamlit
    printf "%-20s " "Streamlit AI对话:8501"
    if check_port "$PORT_STREAMLIT"; then
        local pid=$(get_pid_by_port "$PORT_STREAMLIT")
        printf "${GREEN}● 运行中${NC} (PID: %s)\n" "$pid"
        printf "  ${CYAN}%s${NC}\n" "$URL_STREAMLIT"
    else
        printf "${RED}○ 已停止${NC}\n"
    fi
    echo ""
    
    echo "=============================================="
}

cleanup() {
    log "INFO" "正在清理..."
    
    for port in $PORT_BACKEND $PORT_FRONTEND $PORT_STREAMLIT; do
        kill_by_port "$port" 2>/dev/null || true
    done
    
    log "DONE" "清理完成"
}

#==============================================================================
# 主函数
#==============================================================================

show_banner() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}║              ${GREEN}AI Quant 智能量化投资系统${CYAN}                    ║${NC}"
    echo -e "${CYAN}║                                                              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_help() {
    cat << EOF
${CYAN}AI Quant 一键启动脚本${NC}

${YELLOW}用法:${NC}
    $0 [选项]

${YELLOW}选项:${NC}
    -d, --dev       开发模式 (默认，包含热重载)
    -p, --prod      生产模式
    -b, --background 后台运行模式
    -s, --status    查看服务状态
    -k, --kill      停止所有服务
    -h, --help      显示此帮助信息

${YELLOW}示例:${NC}
    $0              # 开发模式启动
    $0 -d           # 开发模式启动 (同默认)
    $0 -p -b        # 生产模式后台运行
    $0 -s           # 查看服务状态
    $0 -k           # 停止所有服务

${YELLOW}服务说明:${NC}
    后端API:     ${URL_BACKEND}  (FastAPI)
    前端应用:    ${URL_FRONTEND}   (React + Vite)
    AI对话机器人: ${URL_STREAMLIT}  (Streamlit)

${YELLOW}日志位置:${NC}
    ${LOG_DIR}/

EOF
}

main() {
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -d|--dev)
                MODE="dev"
                shift
                ;;
            -p|--prod)
                MODE="prod"
                shift
                ;;
            -b|--background)
                BACKGROUND=true
                shift
                ;;
            -s|--status)
                show_status
                exit 0
                ;;
            -k|--kill)
                show_banner
                cleanup
                exit 0
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "未知选项: $1"
                echo "使用 -h 查看帮助"
                exit 1
                ;;
        esac
    done
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 显示横幅
    show_banner
    
    # 环境检查
    if ! check_dependencies; then
        log "ERROR" "环境检查失败，无法启动服务"
        exit 1
    fi
    
    echo ""
    
    # 端口检查
    if ! check_ports; then
        echo ""
        read -p "是否停止现有服务并继续? (y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            kill_services
        else
            log "INFO" "用户取消启动"
            exit 0
        fi
    fi
    
    echo ""
    log "INFO" "模式: ${MODE}, 后台运行: ${BACKGROUND}"
    log "INFO" "开始启动服务..."
    echo ""
    
    # 按顺序启动服务
    local failed=""
    
    if ! start_backend; then
        failed="${failed} backend"
    fi
    
    if ! start_frontend; then
        failed="${failed} frontend"
    fi
    
    if ! start_streamlit; then
        failed="${failed} streamlit"
    fi
    
    # 结果报告
    echo ""
    echo "=============================================="
    echo "       启动结果"
    echo "=============================================="
    echo ""
    
    if [ -z "$failed" ]; then
        log "DONE" "所有服务启动成功!"
        echo ""
        echo -e "${GREEN}访问链接:${NC}"
        echo -e "  ${CYAN}后端API:    ${URL_BACKEND}${NC}"
        echo -e "  ${CYAN}前端应用:   ${URL_FRONTEND}${NC}"
        echo -e "  ${CYAN}AI对话机器人: ${URL_STREAMLIT}${NC}"
        echo ""
        echo -e "${YELLOW}按 Ctrl+C 停止所有服务${NC}"
        echo "=============================================="
        
        # 等待用户中断
        if [ "$BACKGROUND" = false ]; then
            wait
        fi
    else
        log "ERROR" "以下服务启动失败:$failed"
        log "INFO" "请查看日志: $LOG_FILE"
        echo ""
        read -p "是否停止已启动的服务? (y/N): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            cleanup
        fi
        exit 1
    fi
}

# 陷阱处理 (Ctrl+C)
trap 'cleanup; exit 0' INT TERM

# 运行主函数
main "$@"
