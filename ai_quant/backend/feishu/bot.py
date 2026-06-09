"""
飞书 AI 投资助手机器人

通过飞书 WebSocket 长连接接收用户消息，
调用 DeepAgent 引擎处理，并将结果回复给用户。

启动方式: python backend/feishu/bot.py
（不要使用 python -m backend.feishu.bot，避免触发 backend/__init__.py 加载整个 FastAPI 应用）
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import ssl
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_SCRIPT_DIR)
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)

for _p in list(sys.path):
    if _p == _SCRIPT_DIR:
        sys.path.remove(_p)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

try:
    from dotenv import find_dotenv, load_dotenv

    load_dotenv(find_dotenv(usecwd=True), override=False)
except Exception:
    pass

FEISHU_APP_ID: str = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET: str = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BOT_LOG_LEVEL: str = os.getenv("FEISHU_BOT_LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, FEISHU_BOT_LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("feishu_bot")

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

import lark_oapi.ws.client as _ws_client

_original_ws_kwargs = _ws_client._ws_connect_kwargs


def _patched_ws_kwargs():
    kwargs = _original_ws_kwargs()
    kwargs["ssl"] = _SSL_CTX
    return kwargs


_ws_client._ws_connect_kwargs = _patched_ws_kwargs

from llm.deepagent_engine import run_deepagent, DeepAgentResult

FEISHU_MSG_MAX_LEN = 4000
# 飞书富文本 post 消息中 md 标签支持的最大字符数
FEISHU_POST_MD_MAX_LEN = 3800

# ===== 会话持久化 =====
_CONV_DB_DIR = Path(__file__).resolve().parent.parent.parent / ".data"
_CONV_DB_DIR.mkdir(parents=True, exist_ok=True)
_CONV_DB_PATH = _CONV_DB_DIR / "conversations.db"
_conv_db_lock = threading.Lock()


def _get_conv_db() -> sqlite3.Connection:
    """获取 conversations.db 连接"""
    import sqlite3 as _sqlite3
    conn = _sqlite3.connect(str(_CONV_DB_PATH), check_same_thread=False)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _init_conv_db():
    """初始化 conversations.db 表结构"""
    conn = _get_conv_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '新对话',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
        """)
        conn.commit()
    finally:
        conn.close()


_init_conv_db()


def _save_conversation_message(conv_id: str, role: str, content: str, title: str | None = None):
    """将一条消息持久化到 conversations.db。

    如果会话不存在则自动创建，同时更新会话标题和 updated_at。
    """
    import uuid
    from datetime import datetime

    now = datetime.now().isoformat()
    mid = uuid.uuid4().hex
    metadata = json.dumps({"source": "feishu"}, ensure_ascii=False)

    with _conv_db_lock:
        conn = _get_conv_db()
        try:
            # 检查会话是否存在
            cur = conn.cursor()
            cur.execute("SELECT id FROM conversations WHERE id = ?", (conv_id,))
            exists = cur.fetchone() is not None

            if not exists:
                # 创建新会话
                conv_title = title or "飞书对话"
                conn.execute(
                    "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (conv_id, conv_title, now, now),
                )
            else:
                # 更新会话标题和 updated_at
                if title:
                    conn.execute(
                        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                        (title, now, conv_id),
                    )
                else:
                    conn.execute(
                        "UPDATE conversations SET updated_at = ? WHERE id = ?",
                        (now, conv_id),
                    )

            # 插入消息
            conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, metadata, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (mid, conv_id, role, content, metadata, now),
            )
            conn.commit()
        except Exception as e:
            logger.warning("保存会话消息失败: %s", e)
        finally:
            conn.close()


def _clean_at_text(text: str) -> str:
    cleaned = re.sub(r"@_user_\d+\s*", "", text)
    return cleaned.strip()


def _format_to_markdown(text: str) -> str:
    """将 AI 返回的纯文本内容优化为飞书 Markdown 格式。

    飞书富文本 post 的 md 标签支持：
    - 标题（通过 # 语法）
    - 粗体 **text**、斜体 *text*
    - 有序/无序列表
    - 引用 > text
    - 分割线 ---
    - 代码块
    - 超链接 [text](url)
    """
    if not text:
        return ""

    lines = text.split("\n")
    result_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # 跳过空行，保留一个空行用于段落分隔
        if not stripped:
            if result_lines and result_lines[-1] != "":
                result_lines.append("")
            continue

        # 已经是 Markdown 标题格式，直接保留
        if stripped.startswith("#"):
            result_lines.append(stripped)
            continue

        # 已经是 Markdown 列表格式，直接保留
        if stripped.startswith("- ") or stripped.startswith("* "):
            result_lines.append(stripped)
            continue

        # 已经是有序列表格式
        if re.match(r"^\d+\.\s", stripped):
            result_lines.append(stripped)
            continue

        # 已经是引用格式
        if stripped.startswith("> "):
            result_lines.append(stripped)
            continue

        # 已经是代码块
        if stripped.startswith("```"):
            result_lines.append(stripped)
            continue

        # 已经是分割线
        if stripped in ("---", "***", "___"):
            result_lines.append("\n --- \n")
            continue

        # 检测中文数字标题模式，如 "一、公司概况"、"二、财务分析"
        m = re.match(r"^([一二三四五六七八九十]+)[、.](.+)$", stripped)
        if m:
            result_lines.append(f"### {m.group(1)}、{m.group(2).strip()}")
            continue

        # 检测数字编号标题模式，如 "1. 公司概况"、"2. 财务分析"（非列表项）
        m = re.match(r"^(\d+)[、.]\s*(.+)$", stripped)
        if m:
            num = int(m.group(1))
            content = m.group(2).strip()
            # 如果内容较短（<=20字），视为标题
            if len(content) <= 20:
                result_lines.append(f"### {num}. {content}")
            else:
                result_lines.append(stripped)
            continue

        # 检测括号编号标题，如 "（一）公司概况"、"(1) 公司概况"
        m = re.match(r"^[（(]\s*([一二三四五六七八九十\d]+)\s*[）)]\s*(.+)$", stripped)
        if m:
            result_lines.append(f"#### {m.group(1)}、{m.group(2).strip()}")
            continue

        # 检测 "【xxx】" 模式，视为小节标题
        m = re.match(r"^【(.+)】(.*)$", stripped)
        if m:
            title = m.group(1)
            extra = m.group(2).strip()
            if extra:
                result_lines.append(f"**{title}** {extra}")
            else:
                result_lines.append(f"**{title}**")
            continue

        # 检测 "核心结论："、"投资建议：" 等冒号结尾的短句，视为加粗标签
        m = re.match(r"^([\u4e00-\u9fa5]{2,8}[：:])\s*(.*)$", stripped)
        if m:
            label = m.group(1)
            content = m.group(2).strip()
            if content:
                result_lines.append(f"**{label}** {content}")
            else:
                result_lines.append(f"**{label}**")
            continue

        # 普通文本直接保留
        result_lines.append(stripped)

    # 清理连续空行（最多保留一个）
    cleaned: list[str] = []
    prev_empty = False
    for line in result_lines:
        if line == "":
            if not prev_empty:
                cleaned.append(line)
            prev_empty = True
        else:
            prev_empty = False
            cleaned.append(line)

    return "\n".join(cleaned)


def _extract_title(text: str) -> str:
    """从文本中提取标题，用于富文本消息的标题栏。"""
    # 优先匹配 Markdown 标题
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()[:50]
        if line.startswith("## "):
            return line[3:].strip()[:50]

    # 匹配中文数字标题
    m = re.search(r"([一二三四五六七八九十]+[、.].+)", text)
    if m:
        return m.group(1).strip()[:50]

    # 取第一行非空内容
    for line in text.split("\n"):
        line = line.strip()
        if line:
            return line[:50]

    return "AI投资助手"


def _split_markdown(md_text: str, max_len: int = FEISHU_POST_MD_MAX_LEN) -> list[str]:
    """将 Markdown 文本按段落分割，确保每段不超过飞书限制。"""
    if len(md_text) <= max_len:
        return [md_text]

    parts: list[str] = []
    remaining = md_text
    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break
        # 优先在空行处分割
        cut_pos = remaining.rfind("\n\n", 0, max_len)
        if cut_pos <= 0:
            # 其次在换行处分割
            cut_pos = remaining.rfind("\n", 0, max_len)
        if cut_pos <= 0:
            cut_pos = max_len
        parts.append(remaining[:cut_pos])
        remaining = remaining[cut_pos:].lstrip("\n")
    return parts


def _split_long_text(text: str, max_len: int = FEISHU_MSG_MAX_LEN) -> list[str]:
    if len(text) <= max_len:
        return [text]
    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_len:
            parts.append(remaining)
            break
        cut_pos = remaining.rfind("\n", 0, max_len)
        if cut_pos <= 0:
            cut_pos = max_len
        parts.append(remaining[:cut_pos])
        remaining = remaining[cut_pos:].lstrip("\n")
    return parts


class FeishuBot:
    def __init__(self) -> None:
        if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
            raise RuntimeError(
                "缺少飞书凭证，请设置环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET"
            )

        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET

        self.api_client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .log_level(lark.LogLevel.DEBUG)
            .build()
        )

        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._on_message_receive)
            .build()
        )

        self.ws_client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.DEBUG,
        )

        logger.info("飞书机器人初始化完成 app_id=%s", self.app_id[:8] + "***")

    def _on_message_receive(self, data: lark.im.v1.P2ImMessageReceiveV1) -> None:
        try:
            event = data.event
            if not event:
                return

            message = event.message
            if not message:
                return

            msg_type = str(message.message_type or "")
            chat_id = str(message.chat_id or "")
            message_id = str(message.message_id or "")
            chat_type = str(message.chat_type or "")

            if chat_type == "p2p" and msg_type != "text":
                self._send_text(chat_id, "目前仅支持文字消息，请直接输入文字提问。")
                return

            if msg_type != "text":
                return

            content_str = str(message.content or "{}")
            try:
                content_obj = json.loads(content_str)
            except json.JSONDecodeError:
                logger.warning("消息内容解析失败: %s", content_str[:200])
                return

            user_text = str(content_obj.get("text", "")).strip()
            if not user_text:
                return

            user_text = _clean_at_text(user_text)
            if not user_text:
                return

            sender = event.sender
            sender_id = ""
            if sender and sender.sender_id:
                sender_id = str(sender.sender_id.open_id or "")

            logger.info(
                "收到消息 chat_id=%s sender=%s chat_type=%s text=%s",
                chat_id,
                sender_id,
                chat_type,
                user_text[:100],
            )

            thread_id = f"feishu_{chat_id}"

            threading.Thread(
                target=self._process_and_reply,
                args=(chat_id, message_id, user_text, thread_id),
                daemon=True,
            ).start()

        except Exception as exc:
            logger.exception("处理消息事件异常: %s", exc)

    def _process_and_reply(
        self,
        chat_id: str,
        message_id: str,
        user_text: str,
        thread_id: str,
    ) -> None:
        try:
            self._reply_text(message_id, "正在分析中，请稍候...")

            # 持久化用户消息（用用户消息前50字符作为会话标题）
            _save_conversation_message(thread_id, "user", user_text, title=user_text[:50])

            result: DeepAgentResult = run_deepagent(user_text, thread_id=thread_id, max_steps=20)

            reply_text = result.text or "抱歉，未能生成有效的分析结果。"

            # 持久化AI回复
            _save_conversation_message(thread_id, "assistant", reply_text)

            # 将纯文本转换为飞书 Markdown 格式
            md_text = _format_to_markdown(reply_text)
            title = _extract_title(reply_text)

            # 使用富文本 post 格式发送（支持 Markdown 渲染）
            md_parts = _split_markdown(md_text)
            for i, part in enumerate(md_parts):
                if i == 0:
                    # 第一条消息使用 reply（回复用户消息）
                    self._reply_post(message_id, part, title=title)
                else:
                    # 后续消息使用 send（普通发送）
                    self._send_post(chat_id, part)

            logger.info(
                "回复完成 chat_id=%s text_len=%d parts=%d",
                chat_id,
                len(reply_text),
                len(md_parts),
            )

        except Exception as exc:
            logger.exception("处理请求异常: %s", exc)
            error_msg = f"处理请求时出现错误: {type(exc).__name__}"
            try:
                self._send_text(chat_id, error_msg)
            except Exception:
                pass

    def _send_text(self, chat_id: str, text: str) -> None:
        content = json.dumps({"text": text}, ensure_ascii=False)
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(content)
                .build()
            )
            .build()
        )
        response = self.api_client.im.v1.message.create(request)
        if not response.success():
            logger.error(
                "发送消息失败 chat_id=%s code=%s msg=%s",
                chat_id,
                response.code,
                response.msg,
            )

    def _send_post(self, chat_id: str, md_text: str, title: str = "") -> None:
        """使用富文本 post 格式发送消息（支持 Markdown 渲染）。"""
        post_content = {
            "zh_cn": {
                "title": title or "AI投资助手",
                "content": [[{"tag": "md", "text": md_text}]],
            }
        }
        content = json.dumps(post_content, ensure_ascii=False)
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("post")
                .content(content)
                .build()
            )
            .build()
        )
        response = self.api_client.im.v1.message.create(request)
        if not response.success():
            logger.warning(
                "富文本发送失败，降级为纯文本 chat_id=%s code=%s msg=%s",
                chat_id,
                response.code,
                response.msg,
            )
            # 降级为纯文本发送
            self._send_text(chat_id, md_text)

    def _reply_text(self, message_id: str, text: str) -> None:
        content = json.dumps({"text": text}, ensure_ascii=False)
        request = (
            ReplyMessageRequest.builder()
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("text")
                .build()
            )
            .message_id(message_id)
            .build()
        )
        response = self.api_client.im.v1.message.reply(request)
        if not response.success():
            logger.error(
                "回复消息失败 message_id=%s code=%s msg=%s",
                message_id,
                response.code,
                response.msg,
            )

    def _reply_post(self, message_id: str, md_text: str, title: str = "") -> None:
        """使用富文本 post 格式回复消息（支持 Markdown 渲染）。"""
        post_content = {
            "zh_cn": {
                "title": title or "AI投资助手",
                "content": [[{"tag": "md", "text": md_text}]],
            }
        }
        content = json.dumps(post_content, ensure_ascii=False)
        request = (
            ReplyMessageRequest.builder()
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("post")
                .build()
            )
            .message_id(message_id)
            .build()
        )
        response = self.api_client.im.v1.message.reply(request)
        if not response.success():
            logger.warning(
                "富文本回复失败，降级为纯文本 message_id=%s code=%s msg=%s",
                message_id,
                response.code,
                response.msg,
            )
            # 降级为纯文本回复
            self._reply_text(message_id, md_text)

    def start(self) -> None:
        logger.info("飞书机器人正在启动 WebSocket 长连接...")
        self.ws_client.start()


_feishu_bot_process: subprocess.Popen | None = None
_feishu_bot_start_time: float = 0


def get_bot_status() -> dict:
    """获取飞书机器人运行状态"""
    global _feishu_bot_process, _feishu_bot_start_time
    if _feishu_bot_process is None:
        return {"running": False, "pid": None, "start_time": None, "uptime_seconds": None}
    poll = _feishu_bot_process.poll()
    running = poll is None
    uptime = None
    if _feishu_bot_start_time > 0:
        uptime = int(time.time() - _feishu_bot_start_time)
    return {
        "running": running,
        "pid": _feishu_bot_process.pid,
        "start_time": _feishu_bot_start_time,
        "uptime_seconds": uptime,
        "return_code": poll,
    }


def restart_bot() -> dict:
    """重启飞书机器人（终止当前进程并启动新进程）"""
    global _feishu_bot_process, _feishu_bot_start_time
    try:
        if _feishu_bot_process is not None:
            _feishu_bot_process.terminate()
            try:
                _feishu_bot_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                _feishu_bot_process.kill()
                _feishu_bot_process.wait(timeout=5)
            _feishu_bot_process = None

        bot_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.py")
        _feishu_bot_process = subprocess.Popen(
            [sys.executable, bot_script],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        _feishu_bot_start_time = time.time()
        return {"ok": True, "pid": _feishu_bot_process.pid}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main() -> None:
    bot = FeishuBot()
    bot.start()


if __name__ == "__main__":
    main()
