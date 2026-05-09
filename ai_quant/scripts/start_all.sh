#!/bin/bash
# ai_quant 一键启动脚本 (macOS / Linux)
# 用法: bash scripts/start_all.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/venv"

# 检查虚拟环境
if [ ! -d "$VENV_DIR" ]; then
    echo "[错误] 虚拟环境不存在: $VENV_DIR"
    echo "请先运行: python3 -m venv venv"
    exit 1
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
NODE="$(command -v node)"
NPM="$(command -v npm)"

# 检查 Node.js
if [ -z "$NODE" ]; then
    echo "[错误] 未找到 Node.js，请先安装"
    exit 1
fi

echo "============================================"
echo " AI Quant 量化系统启动脚本"
echo "============================================"
echo "后端端口: 8000"
echo "前端端口: 5173"
echo "Streamlit 端口: 8501"
echo "============================================"

# 后端依赖检查
echo "[1/3] 检查后端依赖 ..."
if ! $PYTHON -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "[提示] 正在安装后端依赖 ..."
    $PIP install -r "$ROOT_DIR/backend/requirements.txt" -q
fi

# 前端依赖检查
echo "[2/3] 检查前端依赖 ..."
if [ ! -d "$ROOT_DIR/web/node_modules" ]; then
    echo "[提示] 正在安装前端依赖 ..."
    (cd "$ROOT_DIR/web" && $NPM install)
fi

# 启动后端
echo "[3/3] 启动后端服务 ..."
echo "--------------------------------------------"
echo "后端地址: http://localhost:8000"
echo "Swagger 文档: http://localhost:8000/docs"
echo "--------------------------------------------"
osascript -e 'tell app "Terminal" to do script "cd '"$ROOT_DIR"' && '"$PYTHON"' backend/run_server.py"' 2>/dev/null || \
    xterm -e "cd '$ROOT_DIR' && $PYTHON backend/run_server.py" 2>/dev/null || \
    open -a Terminal && sleep 1 && \
    osascript -e "tell application \"Terminal\" to do script \"cd '$ROOT_DIR' && '$PYTHON' backend/run_server.py\""

# 等待后端启动
sleep 2

# 启动前端
echo ""
echo "--------------------------------------------"
echo "前端地址: http://localhost:5173"
echo "--------------------------------------------"
osascript -e 'tell app "Terminal" to do script "cd '"$ROOT_DIR/web"' && '"$NPM"' run dev"' 2>/dev/null || \
    xterm -e "cd '$ROOT_DIR/web' && $NPM run dev" 2>/dev/null || \
    open -a Terminal && sleep 1 && \
    osascript -e "tell application \"Terminal\" to do script \"cd '$ROOT_DIR/web' && $NPM run dev\""

# 启动 Streamlit（可选，跳过如果 streamlit 未安装）
echo ""
echo "--------------------------------------------"
echo "Streamlit 地址: http://localhost:8501"
echo "--------------------------------------------"
STREAMLIT="$VENV_DIR/bin/streamlit"
if [ -f "$STREAMLIT" ]; then
    osascript -e 'tell app "Terminal" to do script "cd '"$ROOT_DIR"' && '"$STREAMLIT"' run streamlit_chat/app.py --server.port 8501"' 2>/dev/null || \
        xterm -e "cd '$ROOT_DIR' && $STREAMLIT run streamlit_chat/app.py --server.port 8501" 2>/dev/null || \
        open -a Terminal && sleep 1 && \
        osascript -e "tell application \"Terminal\" to do script \"cd '$ROOT_DIR' && $STREAMLIT run streamlit_chat/app.py --server.port 8501\""
else
    echo "[提示] Streamlit 未安装，跳过。如需启用: $PIP install streamlit"
fi

echo ""
echo "============================================"
echo " 启动完成!"
echo " 后端: http://localhost:8000/docs"
echo " 前端: http://localhost:5173"
echo " Streamlit: http://localhost:8501"
echo "============================================"
echo ""
echo "按 Ctrl+C 可停止各服务"
