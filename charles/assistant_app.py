import json
import os
import uuid

import httpx
import streamlit as st


API_BASE = os.getenv("CHARLES_API_BASE", "http://127.0.0.1:8000")


def stream_sse(message: str, *, session_id: str, context: dict):
    url = f"{API_BASE}/api/assistant/chat_stream"
    payload = {"message": message, "session_id": session_id, "context": context}

    with httpx.stream("POST", url, json=payload, timeout=None) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            data = line[len("data:") :].strip()
            if not data:
                continue
            yield json.loads(data)
            if data.find('"type":"done"') != -1:
                break


st.set_page_config(page_title="Charles 对话机器人", layout="wide")

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("Charles 对话机器人")

with st.sidebar:
    st.subheader("参数")
    mode = st.selectbox("模式", options=["normal", "deep"], index=0)
    days = st.selectbox("days", options=[3, 7, 14], index=1)
    show_tools = st.checkbox("展示工具日志", value=True)
    stock_codes = st.text_input("股票代码（可选，逗号分隔）", value="")
    st.divider()
    st.subheader("快捷场景")
    if st.button("场景1 宏观+舆情联动", use_container_width=True):
        st.session_state.draft = "现在适合买入A股吗？帮我做全面评估（宏观风险+预测市场+热点新闻+市场情绪）。"
    if st.button("场景2 个股舆情（比亚迪）", use_container_width=True):
        st.session_state.draft = "持有比亚迪（002594），最近消息面如何？请给出整体情绪、风险/机会与操作建议。"
    if st.button("场景3 重大事件检测", use_container_width=True):
        st.session_state.draft = "最近A股有没有资产重组/回购等重大事件？请给出事件数量、利好/利空判断和标的建议。"
    if st.button("场景4 全球市场情绪", use_container_width=True):
        st.session_state.draft = "全球市场情绪如何？适合加仓吗？请解释VIX/OVX/GVZ/美债收益率，并给出短期与中长期建议。"
    if st.button("场景5 全链路决策", use_container_width=True):
        st.session_state.draft = "请给我完整投资决策：市场环境+关注事件+标的研究（含财报RAG与五步法研报任务）。"

for m in st.session_state.messages:
    role = m["role"]
    title = "User" if role == "user" else "Assistant"
    st.markdown(f"**{title}**")
    st.markdown(m["content"])
    if show_tools and m.get("tool_runs"):
        with st.expander("工具调用日志", expanded=False):
            for tr in m["tool_runs"]:
                st.markdown(f"- {tr.get('name')} ({tr.get('status')})")
                if tr.get("args"):
                    st.code(json.dumps(tr.get("args"), ensure_ascii=False), language="json")
                if tr.get("output"):
                    st.code(str(tr.get("output"))[:8000], language="text")

draft = st.session_state.get("draft", "")
col1, col2 = st.columns([1, 0.18])
with col1:
    prompt = st.text_area("输入你的问题", value=draft, height=120)
with col2:
    send = st.button("发送", use_container_width=True)

if draft:
    st.session_state.draft = ""

if send and prompt.strip():
    prompt = prompt.strip()
    st.session_state.messages.append({"role": "user", "content": prompt})

    ctx_codes = [x.strip() for x in stock_codes.split(",") if x.strip()]
    ctx = {"mode": mode, "days": int(days), "stock_codes": ctx_codes}

    st.markdown("**Assistant**")
    placeholder = st.empty()
    placeholder.markdown("分析中…")
    answer = ""
    tool_runs = []
    for evt in stream_sse(prompt, session_id=st.session_state.session_id, context=ctx):
        t = evt.get("type")
        if t == "token":
            answer += str(evt.get("content") or "")
            placeholder.markdown(answer + "▌")
        elif t == "tool_start":
            tool_runs.append({"name": evt.get("name"), "args": evt.get("args"), "status": "running", "output": ""})
        elif t == "tool_end":
            tool_runs.append({"name": evt.get("name"), "args": evt.get("args"), "status": evt.get("status"), "output": evt.get("output")})
        elif t == "report_task":
            tool_runs.append({"name": "report_task", "args": None, "status": "ok", "output": json.dumps(evt.get("task") or {}, ensure_ascii=False)})
        elif t == "error":
            tool_runs.append({"name": "error", "args": None, "status": "error", "output": evt.get("message")})
        elif t == "done":
            break
    placeholder.markdown(answer or "（无输出）")
    if show_tools:
        with st.expander("工具调用日志", expanded=False):
            for tr in tool_runs:
                st.markdown(f"- {tr.get('name')} ({tr.get('status')})")
                if tr.get("args"):
                    st.code(json.dumps(tr.get("args"), ensure_ascii=False), language="json")
                if tr.get("output"):
                    st.code(str(tr.get("output"))[:8000], language="text")

    st.session_state.messages.append({"role": "assistant", "content": answer, "tool_runs": tool_runs})
