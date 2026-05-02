from __future__ import annotations

import os

from .models import ReportModel


def build_chat_model(model: ReportModel):
    if model == ReportModel.qwen_max:
        from langchain_community.chat_models.tongyi import ChatTongyi

        return ChatTongyi(model="qwen-max")

    if model == ReportModel.deepseek:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY required")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        model_name = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(api_key=api_key, base_url=base_url, model=model_name)

    raise RuntimeError("unknown model")

