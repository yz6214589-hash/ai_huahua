from __future__ import annotations

import json
import os
from functools import lru_cache

from langchain_core.tools import tool


@tool
def web_search(query: str, type: str = "general") -> str:
    """联网搜索最新市场信息并返回文本结果。"""
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY required for web_search")
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    resp = client.chat.completions.create(
        model=os.getenv("QWEN_MODEL", "qwen-max"),
        messages=[
            {"role": "system", "content": "你是专业投研助手，请基于联网搜索结果回答，并标注来源与时间。"},
            {"role": "user", "content": f"[{type}] {query}"},
        ],
        extra_body={"enable_search": True},
    )
    return resp.choices[0].message.content or ""


@lru_cache(maxsize=2)
def _load_vectorstore(index_dir: str):
    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY required for embeddings")
    from langchain_community.embeddings import DashScopeEmbeddings
    from langchain_community.vectorstores import FAISS

    embeddings = DashScopeEmbeddings(model="text-embedding-v4", dashscope_api_key=api_key)
    return FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)


@tool
def rag_search(query: str, stock_codes: str = "", k: int = 6) -> str:
    """从本地 PDF 研报/财报向量索引检索相关内容并返回 JSON（含页码溯源）。"""
    root = os.getenv("CHARLES_REPORT_DATA_DIR") or os.path.join(os.getcwd(), "api", "data")
    index_dir = os.path.join(root, "vector_store")
    vs = _load_vectorstore(index_dir)
    codes = [c.strip() for c in (stock_codes or "").split(",") if c.strip()]
    docs = []
    kk = max(1, int(k or 6))
    if codes:
        for c in codes:
            docs.extend(vs.similarity_search(query, k=kk, filter={"stock_code": c}))
    else:
        docs = vs.similarity_search(query, k=kk)
    out = []
    for d in docs[:kk]:
        m = d.metadata or {}
        out.append(
            {
                "stock_code": m.get("stock_code"),
                "stock_name": m.get("stock_name"),
                "title": m.get("title"),
                "source": m.get("source"),
                "publish_date": m.get("publish_date"),
                "page": m.get("page"),
                "text": d.page_content,
            }
        )
    return json.dumps({"query": query, "hits": out}, ensure_ascii=False, indent=2)
