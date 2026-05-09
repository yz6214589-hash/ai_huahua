#!/bin/bash
# ai_quant 一键启动脚本 (当前终端内运行，macOS / Linux)
# 用法: cd ai_quant && bash scripts/start_inline.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$ROOT_DIR/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "[错误] 虚拟环境不存在: $VENV_DIR"
    echo "请先运行: python3 -m venv venv"
    exit 1
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
NODE="$(command -v node)"
NPM="$(command -v npm)"

if [ -z "$NODE" ]; then
    echo "[错误] 未找到 Node.js"
    exit 1
fi

echo "============================================"
echo " AI Quant 量化系统启动"
echo "============================================"
echo "后端: http://localhost:8000"
echo "前端: http://localhost:5173"
echo "Streamlit: http://localhost:8501"
echo "============================================"

# 后端依赖
if ! $PYTHON -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "[提示] 正在安装后端依赖 ..."
    $PIP install -r "$ROOT_DIR/backend/requirements.txt" -q
fi

# 前端依赖
if [ ! -d "$ROOT_DIR/web/node_modules" ]; then
    echo "[提示] 正在安装前端依赖 ..."
    (cd "$ROOT_DIR/web" && $NPM install)
fi

# 启动后端
echo ""
echo "[后端] 启动中 ..."
$PYTHON backend/run_server.py &
BACKEND_PID=$!
echo "[后端] PID=$BACKEND_PID"

sleep 2

# 启动前端
echo ""
echo "[前端] 启动中 ..."
(cd "$ROOT_DIR/web" && $NPM run dev) &
FRONTEND_PID=$!
echo "[前端] PID=$FRONTEND_PID"

# 启动 Streamlit
STREAMLIT="$VENV_DIR/bin/streamlit"
if [ -f "$STREAMLIT" ]; then
    echo ""
    echo "[Streamlit] 启动中 ..."
    $STREAMLIT run streamlit_chat/app.py --server.port 8501 &
    STREAMLIT_PID=$!
    echo "[Streamlit] PID=$STREAMLIT_PID"
fi

echo ""
echo "============================================"
echo " 所有服务已启动!"
echo "============================================"
echo "后端: http://localhost:8000/docs"
echo "前端: http://localhost:5173"
echo "Streamlit: http://localhost:8501"
echo ""
echo "按 Ctrl+C 停止所有服务"
echo "============================================"

# 捕获 Ctrl+C
cleanup() {
    echo ""
    echo "[停止] 正在关闭服务 ..."
    kill $BACKEND_PID $FRONTEND_PID $STREAMLIT_PID 2>/dev/null
    echo "[完成] 所有服务已停止"
    exit 0
}
trap cleanup SIGINT SIGTERM

# 等待
wait
