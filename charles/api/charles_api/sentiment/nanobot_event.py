from __future__ import annotations

import json
import os
from typing import Any


EVENT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "利好": {
        "资产重组": ["资产重组", "重大资产", "借壳上市", "资产注入", "资产置换"],
        "回购增持": ["回购", "增持", "股份回购", "大股东增持", "实控人增持"],
        "业绩预增": ["业绩预增", "业绩大增", "净利润增长", "营收增长", "扭亏为盈"],
        "股权激励": ["股权激励", "限制性股票", "股票期权", "员工持股"],
        "大额订单": ["中标", "大额订单", "重大合同", "战略合作", "签约"],
        "分红送转": ["分红", "送股", "转增", "派息", "高送转"],
    },
    "利空": {
        "业绩预减": ["业绩预减", "业绩下滑", "亏损", "营收下降", "净利润下降"],
        "违规处罚": ["违规", "处罚", "立案调查", "行政处罚", "警示函"],
        "股东减持": ["减持", "股东减持", "大股东减持", "高管减持", "清仓"],
        "商誉减值": ["商誉减值", "资产减值", "计提减值", "坏账准备"],
        "退市风险": ["退市", "ST", "*ST", "暂停上市", "终止上市"],
        "诉讼仲裁": ["诉讼", "仲裁", "被诉", "索赔", "判决"],
    },
    "政策": {
        "货币政策": ["降准", "降息", "MLF", "逆回购", "LPR", "流动性"],
        "产业政策": ["产业政策", "补贴", "扶持", "规划", "纲要"],
        "监管政策": ["监管", "新规", "征求意见", "暂停", "整顿", "规范"],
    },
}


SIGNAL_MAP: dict[str, dict[str, Any]] = {
    "利好": {
        "default_signal": "关注",
        "资产重组": {"signal": "强烈关注", "reason": "资产重组可能带来基本面质变"},
        "回购增持": {"signal": "看多", "reason": "大股东/公司用真金白银表达信心"},
        "业绩预增": {"signal": "看多", "reason": "业绩超预期增长"},
        "股权激励": {"signal": "中性偏多", "reason": "管理层利益绑定，长期利好"},
        "大额订单": {"signal": "看多", "reason": "订单驱动业绩确定性增长"},
        "分红送转": {"signal": "关注", "reason": "高分红体现公司现金流充裕"},
    },
    "利空": {
        "default_signal": "回避",
        "业绩预减": {"signal": "看空", "reason": "基本面恶化"},
        "违规处罚": {"signal": "回避", "reason": "合规风险不确定性大"},
        "股东减持": {"signal": "谨慎", "reason": "内部人士减持可能释放负面信号"},
        "商誉减值": {"signal": "看空", "reason": "减值压力影响利润"},
        "退市风险": {"signal": "强烈回避", "reason": "退市风险极高"},
        "诉讼仲裁": {"signal": "谨慎", "reason": "诉讼结果不确定"},
    },
    "政策": {
        "default_signal": "关注",
        "货币政策": {"signal": "关注宏观", "reason": "影响市场整体流动性"},
        "产业政策": {"signal": "关注板块", "reason": "政策利好相关板块"},
        "监管政策": {"signal": "谨慎观望", "reason": "监管收紧可能影响行业格局"},
    },
}


EVENT_DETECTION_PROMPT = """你是一位专业的金融事件分析师。请从以下新闻中识别重大金融事件。

新闻内容：
{news_text}

请以严格的 JSON 格式输出（不要输出其他内容）：
{{
    "has_event": true或false,
    "event_type": "利好/利空/政策/无",
    "event_category": "具体事件类别（如：资产重组、业绩预增、股东减持等）",
    "event_description": "事件描述，一句话",
    "urgency": "高/中/低",
    "confidence": 1到5的整数
}}"""


def extract_news_text(news_item: dict[str, Any]) -> str:
    text_fields = ["新闻内容", "content", "内容", "新闻标题", "title", "标题", "公告标题"]
    parts = []
    for field in text_fields:
        if field in news_item and news_item[field]:
            parts.append(str(news_item[field]))
    return " ".join(parts) if parts else ""


def keyword_based_detection(news_text: str) -> list[dict[str, Any]]:
    detected: list[dict[str, Any]] = []
    for event_type, categories in EVENT_KEYWORDS.items():
        for category, keywords in categories.items():
            matched_keywords = [kw for kw in keywords if kw in news_text]
            if matched_keywords:
                detected.append({"event_type": event_type, "event_category": category, "matched_keywords": matched_keywords})
    return detected


def generate_signal(event_type: str, event_category: str) -> dict[str, Any]:
    type_signals = SIGNAL_MAP.get(event_type, {})
    category_signal = type_signals.get(event_category)
    if category_signal:
        return category_signal
    default = type_signals.get("default_signal", "观望")
    return {"signal": default, "reason": f"{event_type}事件 - {event_category}"}


def llm_event_detection(news_text: str, *, model: str = "qwen-turbo") -> dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY required for llm event detection")
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    prompt = EVENT_DETECTION_PROMPT.format(news_text=news_text[:2000])
    resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0.1)
    content = (resp.choices[0].message.content or "").strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    return json.loads(content)


def detect_events(news_item: dict[str, Any], *, use_llm: bool = False, model: str = "qwen-turbo") -> list[dict[str, Any]]:
    news_text = extract_news_text(news_item)
    if not news_text.strip():
        return []
    kw = keyword_based_detection(news_text)
    out: list[dict[str, Any]] = []
    if kw:
        for ev in kw:
            sig = generate_signal(ev["event_type"], ev["event_category"])
            out.append(
                {
                    "event_type": ev["event_type"],
                    "event_category": ev["event_category"],
                    "signal": sig.get("signal"),
                    "signal_reason": sig.get("reason"),
                    "confidence": 4,
                    "urgency": "中",
                    "impact": sig.get("reason"),
                }
            )
        return out
    if not use_llm:
        return []
    det = llm_event_detection(news_text, model=model)
    if not det.get("has_event"):
        return []
    event_type = str(det.get("event_type") or "")
    if event_type not in ("利好", "利空", "政策"):
        return []
    event_category = str(det.get("event_category") or "")
    sig = generate_signal(event_type, event_category)
    urgency = str(det.get("urgency") or "中")
    confidence = int(det.get("confidence") or 3)
    out.append(
        {
            "event_type": event_type,
            "event_category": event_category,
            "signal": sig.get("signal"),
            "signal_reason": sig.get("reason"),
            "confidence": max(1, min(confidence, 5)),
            "urgency": urgency if urgency in ("高", "中", "低") else "中",
            "impact": str(det.get("event_description") or sig.get("reason") or ""),
        }
    )
    return out

