"""
飞书集成API路由模块

提供飞书配置的查询和更新、机器人状态监控、连接测试和重连功能。
配置数据存储在 admin_feishu_config 表中，app_secret 加密存储。
响应格式统一为 {"ok": true, "data": ...} 或 {"ok": false, "error": "..."}
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime

import requests
from fastapi import APIRouter
from pydantic import BaseModel

from ..admin_db import get_admin_db
from ...infra.crypto import encrypt_value, decrypt_value

router = APIRouter(prefix="/api/v1/admin/feishu", tags=["admin-feishu"])


class UpdateFeishuConfigRequest(BaseModel):
    app_id: str
    app_secret: str
    ws_url: str | None = None


def _get_config() -> dict | None:
    """获取飞书配置记录（只有一条）"""
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, app_id, app_secret_cipher, ws_url, status, created_at, updated_at "
                "FROM admin_feishu_config LIMIT 1"
            )
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)
        finally:
            conn.close()


def _mask_secret(secret: str) -> str:
    """掩码处理密钥，只保留前4位和后4位"""
    if not secret:
        return ""
    if len(secret) <= 8:
        return secret[:2] + "***" + secret[-2:]
    return secret[:4] + "****" + secret[-4:]


def _is_bot_running() -> bool:
    """检查飞书机器人进程是否在运行"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "feishu/bot.py"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _get_bot_pids() -> list[str]:
    """获取飞书机器人进程ID列表"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "feishu/bot.py"],
            capture_output=True,
            timeout=5,
        )
        if result.returncode == 0:
            return [pid.strip() for pid in result.stdout.decode().strip().split("\n") if pid.strip()]
        return []
    except Exception:
        return []


def _test_connection(app_id: str, app_secret: str) -> tuple[bool, str]:
    """测试飞书连接，通过获取 tenant_access_token 验证凭证有效性"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    try:
        resp = requests.post(
            url,
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
        data = resp.json()
        if data.get("code") == 0:
            return True, "连接成功"
        return False, f"认证失败: {data.get('msg', '未知错误')}"
    except requests.exceptions.Timeout:
        return False, "连接超时"
    except requests.exceptions.ConnectionError:
        return False, "网络连接失败"
    except Exception as e:
        return False, str(e)


@router.get("/config")
def get_feishu_config():
    config = _get_config()
    if not config:
        return {"ok": False, "error": "飞书配置不存在"}
    try:
        decrypted = decrypt_value(config["app_secret_cipher"])
        masked_secret = _mask_secret(decrypted)
    except Exception:
        masked_secret = ""
    return {
        "ok": True,
        "data": {
            "app_id": config["app_id"],
            "app_secret": masked_secret,
            "ws_url": config["ws_url"],
            "status": config["status"],
        },
    }


@router.put("/config")
def update_feishu_config(req: UpdateFeishuConfigRequest):
    config = _get_config()
    if not config:
        config_id = uuid.uuid4().hex
        now = datetime.now().isoformat()
        cipher = encrypt_value(req.app_secret)
        ws_url = req.ws_url or "wss://open.feishu.cn/event"
        conn, lock = get_admin_db()
        with lock:
            try:
                conn.execute(
                    "INSERT INTO admin_feishu_config (id, app_id, app_secret_cipher, ws_url, status, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'enabled', ?, ?)",
                    (config_id, req.app_id, cipher, ws_url, now, now),
                )
                conn.commit()
            finally:
                conn.close()
        return {
            "ok": True,
            "data": {
                "app_id": req.app_id,
                "app_secret": _mask_secret(req.app_secret),
                "ws_url": ws_url,
                "status": "enabled",
            },
        }
    config_id = config["id"]
    now = datetime.now().isoformat()
    cipher = encrypt_value(req.app_secret)
    ws_url = req.ws_url or config["ws_url"]
    conn, lock = get_admin_db()
    with lock:
        try:
            conn.execute(
                "UPDATE admin_feishu_config SET app_id = ?, app_secret_cipher = ?, ws_url = ?, status = 'enabled', updated_at = ? WHERE id = ?",
                (req.app_id, cipher, ws_url, now, config_id),
            )
            conn.commit()
        finally:
            conn.close()
    return {
        "ok": True,
        "data": {
            "app_id": req.app_id,
            "app_secret": _mask_secret(req.app_secret),
            "ws_url": ws_url,
            "status": "enabled",
        },
    }


@router.get("/status")
def get_feishu_status():
    config = _get_config()
    if not config:
        return {"ok": False, "error": "飞书配置不存在"}
    running = _is_bot_running()
    pids = _get_bot_pids()
    return {
        "ok": True,
        "data": {
            "online": running,
            "today_message_count": 0,
            "active_sessions": 0,
            "connection_duration": "",
            "last_connect_time": "",
            "pids": pids,
            "config_status": config["status"],
        },
    }


@router.post("/test")
def test_feishu_connection():
    config = _get_config()
    if not config:
        return {"ok": False, "error": "飞书配置不存在"}
    if not config["app_id"] or not config["app_secret_cipher"]:
        return {"ok": False, "error": "飞书配置不完整，请先配置 app_id 和 app_secret"}
    try:
        decrypted = decrypt_value(config["app_secret_cipher"])
    except Exception:
        return {"ok": False, "error": "解密密钥失败，密钥数据已损坏"}
    success, message = _test_connection(config["app_id"], decrypted)
    return {"ok": success, "data": {"success": success, "message": message}}


@router.post("/reconnect")
def reconnect_feishu():
    config = _get_config()
    if not config:
        return {"ok": False, "error": "飞书配置不存在，请先配置"}
    if not config["app_id"] or not config["app_secret_cipher"]:
        return {"ok": False, "error": "飞书配置不完整，请先配置 app_id 和 app_secret"}
    try:
        decrypt_value(config["app_secret_cipher"])
    except Exception:
        return {"ok": False, "error": "解密密钥失败，密钥数据已损坏"}
    existing_pids = _get_bot_pids()
    for pid in existing_pids:
        try:
            subprocess.run(["kill", pid], timeout=5)
        except Exception:
            pass
    backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    bot_script = os.path.join(backend_dir, "feishu", "bot.py")
    if not os.path.exists(bot_script):
        return {"ok": False, "error": f"飞书机器人脚本不存在: {bot_script}"}
    try:
        subprocess.Popen(
            [sys.executable, bot_script],
            cwd=backend_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        return {"ok": False, "error": f"启动飞书机器人失败: {e}"}
    conn, lock = get_admin_db()
    with lock:
        try:
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE admin_feishu_config SET status = 'enabled', updated_at = ? WHERE id = ?",
                (now, config["id"]),
            )
            conn.commit()
        finally:
            conn.close()
    return {"ok": True, "data": {"message": "飞书机器人已重启", "killed_pids": existing_pids}}
