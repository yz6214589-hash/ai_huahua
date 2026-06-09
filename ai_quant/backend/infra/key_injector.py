"""
密钥注入器模块

从 admin_api_keys 表读取所有状态为 active 的密钥，
解密后注入到 os.environ 中。
"""

from __future__ import annotations

import os
from typing import Any

from ..api.admin_db import get_admin_db
from ..infra.crypto import decrypt_value


# 密钥名称到环境变量名的映射关系
_KEY_ENV_MAP: dict[str, str] = {
    "DASHSCOPE_KEY": "DASHSCOPE_API_KEY",
    "DEEPSEEK_KEY": "DEEPSEEK_API_KEY",
    "TAVILY_KEY": "TAVILY_API_KEY",
    "TUSHARE_KEY": "TUSHARE_API_KEY",
}


class KeyInjector:
    """密钥注入器，从 admin_api_keys 表读取密钥并注入环境变量"""

    @staticmethod
    def inject_all():
        """从 admin_api_keys 表读取所有密钥，解密后注入 os.environ"""
        try:
            conn, lock = get_admin_db()
            with lock:
                cur = conn.cursor()
                cur.execute(
                    "SELECT name, cipher_key, key_type FROM admin_api_keys WHERE status = 'active'"
                )
                rows = cur.fetchall()
                conn.close()

            for row in rows:
                name = row["name"]
                cipher_key = row["cipher_key"]
                try:
                    plain_key = decrypt_value(cipher_key)
                except Exception:
                    continue
                env_name = _KEY_ENV_MAP.get(name, name)
                if not os.environ.get(env_name):
                    os.environ[env_name] = plain_key
        except Exception:
            pass

    @staticmethod
    def inject_key(name: str):
        """注入指定密钥"""
        try:
            conn, lock = get_admin_db()
            with lock:
                cur = conn.cursor()
                cur.execute(
                    "SELECT cipher_key FROM admin_api_keys WHERE name = ? AND status = 'active'",
                    (name,),
                )
                row = cur.fetchone()
                conn.close()
            if row:
                plain_key = decrypt_value(row["cipher_key"])
                env_name = _KEY_ENV_MAP.get(name, name)
                os.environ[env_name] = plain_key
        except Exception:
            pass

    @staticmethod
    def get_key(name: str) -> str | None:
        """获取解密后的密钥值"""
        try:
            conn, lock = get_admin_db()
            with lock:
                cur = conn.cursor()
                cur.execute(
                    "SELECT cipher_key FROM admin_api_keys WHERE name = ? AND status = 'active'",
                    (name,),
                )
                row = cur.fetchone()
                conn.close()
            if row:
                return decrypt_value(row["cipher_key"])
        except Exception:
            pass
        return None
