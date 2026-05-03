from __future__ import annotations

import streamlit as st

from lib.api_client import run_agent
from lib.theme import apply_theme


apply_theme()
st.title("AI 对话机器人")
st.caption("Streamlit 仅用于对话机器人界面，其它业务页面统一在 React 控制台。")

if "history" not in st.session_state:
    st.session_state["history"] = []

for item in st.session_state["history"]:
    with st.chat_message(item["role"]):
        st.markdown(item["text"])

prompt = st.chat_input("输入你的量化问题，例如：请生成今日晨会简报")
if prompt:
    st.session_state["history"].append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("正在调用统一 Agent..."):
            try:
                data = run_agent(prompt)
                text = f"路由：`{data['route']['target']}`\n\n```json\n{data}\n```"
            except Exception as exc:
                text = f"请求失败：{exc}"
            st.markdown(text)
            st.session_state["history"].append({"role": "assistant", "text": text})
