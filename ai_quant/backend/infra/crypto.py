"""
Fernet 加密解密工具模块

提供 API 密钥等敏感信息的加密存储功能：
- encrypt_value: 加密明文
- decrypt_value: 解密密文
- 密钥优先从环境变量 AI_QUANT_ENCRYPTION_KEY 读取
- 环境变量不存在时自动生成密钥并持久化到 .data/encryption_key.txt
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / ".data"


def _get_or_create_key() -> bytes:
    key_str = os.getenv("AI_QUANT_ENCRYPTION_KEY", "").strip()
    if key_str:
        return key_str.encode()

    key_file = _DATA_DIR / "encryption_key.txt"
    if key_file.exists():
        raw = key_file.read_text().strip()
        if raw:
            return raw.encode()

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    key_file.write_text(key.decode())
    return key


_KEY = _get_or_create_key()
_CIPHER = Fernet(_KEY)


def encrypt_value(plain_text: str) -> str:
    return _CIPHER.encrypt(plain_text.encode()).decode()


def decrypt_value(cipher_text: str) -> str:
    return _CIPHER.decrypt(cipher_text.encode()).decode()
