from __future__ import annotations

import json
import os
from typing import Any


SENTIMENT_PROMPT = """你是一位专业金融舆情分析师。请对下面的新闻进行结构化分析，并严格输出 JSON（不要输出其他内容）：

新闻：
{news_text}

输出 JSON 字段：
{{
  "sentiment": "正面/负面/中性",
  "strength": 1到5整数（情绪强度，5最强烈）,
  "entities": ["相关实体/公司/人物/产品"],
  "keywords": ["关键词"],
  "summary": "一句话摘要",
  "market_impact": "对股价可能影响（短期/中期）一句话"
}}"""


def score_one(news_text: str, *, model: str = "qwen-turbo") -> dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY required for sentiment scoring")
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    prompt = SENTIMENT_PROMPT.format(news_text=news_text[:2500])
    resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.2)
    content = (resp.choices[0].message.content or "").strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    obj = json.loads(content)
    sentiment = str(obj.get("sentiment") or "")
    if sentiment not in ("正面", "负面", "中性"):
        sentiment = "中性"
    strength = int(obj.get("strength") or 3)
    strength = max(1, min(strength, 5))
    return {
        "sentiment": sentiment,
        "strength": strength,
        "entities": obj.get("entities") if isinstance(obj.get("entities"), list) else [],
        "keywords": obj.get("keywords") if isinstance(obj.get("keywords"), list) else [],
        "summary": str(obj.get("summary") or ""),
        "market_impact": str(obj.get("market_impact") or ""),
    }

