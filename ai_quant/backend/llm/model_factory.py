"""
LLM模型工厂模块

负责从 admin_llm_models 表读取模型配置，通过 api_key_ref 关联
admin_api_keys 表获取解密后的密钥，创建对应的 LLM 实例。

支持的 provider:
- tongyi: langchain_community.chat_models.ChatTongyi
- deepseek: langchain_openai.ChatOpenAI
- openai: langchain_openai.ChatOpenAI
- ollama: langchain_ollama.ChatOllama
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.language_models import BaseChatModel

from ..api.admin_db import get_admin_db
from ..infra.crypto import decrypt_value


def _get_models_from_db(only_active: bool = True) -> list[dict[str, Any]]:
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            if only_active:
                cur.execute(
                    "SELECT m.id, m.name, m.provider, m.model_name, m.api_key_ref, m.base_url, m.status, m.sort_order "
                    "FROM admin_llm_models m WHERE m.status = 'active' ORDER BY m.sort_order ASC"
                )
            else:
                cur.execute(
                    "SELECT m.id, m.name, m.provider, m.model_name, m.api_key_ref, m.base_url, m.status, m.sort_order "
                    "FROM admin_llm_models m ORDER BY m.sort_order ASC"
                )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()


def _get_decrypted_key(api_key_ref: str | None) -> str | None:
    if not api_key_ref:
        return None
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT cipher_key FROM admin_api_keys WHERE id = ? AND status = 'active'",
                (api_key_ref,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return decrypt_value(row["cipher_key"])
        except Exception:
            return None
        finally:
            conn.close()


def _build_llm(model_config: dict[str, Any], **kwargs) -> BaseChatModel:
    provider = model_config.get("provider", "").strip().lower()
    model_name = model_config.get("model_name", "")
    api_key_ref = model_config.get("api_key_ref")
    base_url = model_config.get("base_url")

    merged_kwargs = dict(kwargs)

    if provider == "tongyi":
        api_key = _get_decrypted_key(api_key_ref) or os.environ.get("DASHSCOPE_API_KEY", "")
        from langchain_community.chat_models.tongyi import ChatTongyi

        merged_kwargs.setdefault("model", model_name)
        merged_kwargs.setdefault("dashscope_api_key", api_key)
        if base_url:
            merged_kwargs.setdefault("base_url", base_url)
        return ChatTongyi(**merged_kwargs)

    elif provider == "deepseek":
        api_key = _get_decrypted_key(api_key_ref)
        from langchain_openai import ChatOpenAI

        merged_kwargs.setdefault("model", model_name)
        merged_kwargs.setdefault("api_key", api_key)
        merged_kwargs.setdefault("base_url", base_url or "https://api.deepseek.com")
        return ChatOpenAI(**merged_kwargs)

    elif provider == "openai":
        api_key = _get_decrypted_key(api_key_ref)
        from langchain_openai import ChatOpenAI

        merged_kwargs.setdefault("model", model_name)
        merged_kwargs.setdefault("api_key", api_key)
        if base_url:
            merged_kwargs.setdefault("base_url", base_url)
        return ChatOpenAI(**merged_kwargs)

    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        merged_kwargs.setdefault("model", model_name)
        if base_url:
            merged_kwargs.setdefault("base_url", base_url)
        return ChatOllama(**merged_kwargs)

    else:
        raise ValueError(f"不支持的 provider: {provider}")


class ModelFactory:
    """LLM模型工厂，根据配置创建对应的 LLM 实例"""

    @staticmethod
    def get_llm(model_id: str | None = None, **kwargs) -> BaseChatModel:
        """从 admin_llm_models 表获取模型配置，创建 LLM 实例

        Args:
            model_id: 模型ID，为 None 时返回第一个启用的模型
            **kwargs: 传递给 LLM 构造函数的额外参数

        Returns:
            BaseChatModel: LLM 实例

        Raises:
            ValueError: 当找不到模型配置时
        """
        models = _get_models_from_db(only_active=True)
        if not models:
            raise ValueError("没有可用的模型配置，请先在管理后台添加并启用模型")

        target = None
        if model_id:
            for m in models:
                if m["id"] == model_id:
                    target = m
                    break
            if not target:
                raise ValueError(f"模型配置不存在或未启用: {model_id}")
        else:
            target = models[0]

        return _build_llm(target, **kwargs)

    @staticmethod
    def get_deepagent_llm() -> BaseChatModel:
        """获取 DeepAgent 使用的模型（默认取第一个启用的模型）"""
        return ModelFactory.get_llm()

    @staticmethod
    def list_available_models() -> list[dict[str, Any]]:
        """列出所有启用的模型"""
        return _get_models_from_db(only_active=True)
