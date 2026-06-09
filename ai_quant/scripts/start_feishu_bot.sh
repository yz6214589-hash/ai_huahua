#!/bin/bash
# 启动飞书 AI 投资助手机器人
# 使用 WebSocket 长连接模式，无需公网 IP
#
# 前置条件：在飞书开放平台手动配置
# ==============================================
# 1. 打开 https://open.feishu.cn/ ，登录后进入应用
# 2. 应用功能 -> 机器人 -> 启用机器人
# 3. 权限管理 -> 开通以下权限：
#    - im:message（获取与发送单聊、群组消息）
#    - im:message:send_as_bot（以应用身份发消息）
#    - im:message.group_at_msg:readonly（接收群聊 @机器人 消息）
#    - im:message.p2p_msg:readonly（接收私聊消息）
# 4. 事件订阅 -> 添加事件 im.message.receive_v1
# 5. 版本管理与发布 -> 创建版本并发布
# ==============================================
#
# 启动方式（二选一）：
#   前台运行: ./start_feishu_bot.sh
#   后台运行: nohup ./start_feishu_bot.sh > feishu_bot.log 2>&1 &

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="/Users/apple/Desktop/ai_huahua/ai_quant/venv"

source "${VENV_DIR}/bin/activate"

cd "${PROJECT_DIR}"

echo "正在启动飞书 AI 投资助手机器人..."
echo "启动时间: $(date '+%Y-%m-%d %H:%M:%S')"
python backend/feishu/bot.py
