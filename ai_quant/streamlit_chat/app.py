from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import streamlit as st

from lib.api_client import (
    add_message,
    create_conversation,
    delete_conversation,
    get_agent_runs,
    get_status,
    get_tools,
    get_conversation,
    list_conversations,
    stream_agent,
)
from lib.theme import apply_theme

st.set_page_config(page_title="AI 投资助手", page_icon="A", layout="wide", initial_sidebar_state="collapsed")
apply_theme()


def _init_state() -> None:
    defaults: dict[str, Any] = {
        "conv_list": [],
        "current_conv_id": "",
        "chat_history": [],
        "_pending_report": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _load_conversation(conv_id: str) -> None:
    conv = get_conversation(conv_id)
    items = []
    for m in conv.get("messages", []) or []:
        role = m.get("role") or "user"
        content = m.get("content") or ""
        items.append({"role": role, "content": content, "metadata": m.get("metadata") or {}})
    st.session_state["current_conv_id"] = conv_id
    st.session_state["chat_history"] = items


def _ensure_conversation() -> str:
    cid = st.session_state.get("current_conv_id") or ""
    if cid:
        return cid
    conv = create_conversation("新对话")
    st.session_state["current_conv_id"] = conv["id"]
    st.session_state["chat_history"] = []
    return conv["id"]


def _render_header() -> None:
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:12px;padding:8px 0 4px">
                <div>
                    <div style="font-weight:700;font-size:1.05rem;color:#1e293b">AI 投资助手</div>
                    <div style="font-size:0.78rem;color:#64748b">量化投研 · 多模块协同 · 流式响应</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        if st.button("新建对话", use_container_width=True, type="primary", key="new_conv_header"):
            conv = create_conversation("新对话")
            st.session_state["current_conv_id"] = conv["id"]
            st.session_state["chat_history"] = []
            st.rerun()


def _render_status_row() -> None:
    sc1, sc2, sc3 = st.columns(3)
    try:
        _ = get_status()
        sc1.success("Agent 就绪")
    except Exception:
        sc1.error("Agent 未连接")
    try:
        tools = get_tools()
        sc2.info(f"工具数量：{len(tools)}")
    except Exception:
        sc2.warning("工具获取失败")
    try:
        runs = get_agent_runs(10)
        sc3.info(f"最近运行：{len(runs)}")
    except Exception:
        sc3.warning("运行记录获取失败")


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 对话管理")

        if st.button("新建对话", use_container_width=True, type="primary", key="new_conv_sidebar"):
            conv = create_conversation("新对话")
            st.session_state["current_conv_id"] = conv["id"]
            st.session_state["chat_history"] = []
            st.rerun()

        st.divider()
        st.markdown("#### 历史对话")

        try:
            convs = list_conversations()
        except Exception:
            convs = []
        st.session_state["conv_list"] = convs

        for conv in convs:
            cid = conv.get("id") or ""
            if not cid:
                continue
            title = (conv.get("title") or "无标题").strip() or "无标题"
            is_active = st.session_state.get("current_conv_id") == cid

            cols = st.columns([4, 1])
            with cols[0]:
                label = f"{title}" + ("（当前）" if is_active else "")
                if st.button(label[:28], key=f"conv_{cid}", use_container_width=True):
                    _load_conversation(cid)
                    st.rerun()
            with cols[1]:
                if st.button("删除", key=f"del_{cid}", use_container_width=True):
                    try:
                        delete_conversation(cid)
                    except Exception:
                        pass
                    if st.session_state.get("current_conv_id") == cid:
                        st.session_state["current_conv_id"] = ""
                        st.session_state["chat_history"] = []
                    st.rerun()

        st.divider()
        st.caption(datetime.now().strftime("%Y-%m-%d"))


def _render_history() -> None:
    for msg in st.session_state.get("chat_history", []):
        role = msg.get("role") or "user"
        content = msg.get("content") or ""
        with st.chat_message(role):
            st.markdown(content)


def _handle_prompt(prompt: str) -> None:
    conv_id = _ensure_conversation()

    st.session_state["chat_history"].append({"role": "user", "content": prompt})
    add_message(conv_id, "user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    status_box = st.empty()
    assistant_placeholder = None
    tool_calls: list[dict[str, Any]] = []

    full_text = ""
    report_html = ""
    done_result: Any = None
    last_status = ""

    try:
        for ev in stream_agent(prompt):
            ev_type = ev.get("_event") or ""
            payload = {k: v for k, v in ev.items() if k != "_event"}

            if ev_type == "route":
                route = payload.get("route") or {}
                target = route.get("target") or ""
                reason = route.get("reason") or ""
                status_box.info(f"路由：{target}（{reason}）")

            elif ev_type == "status":
                last_status = payload.get("message") or ""
                status_box.info(last_status)

            elif ev_type == "tools":
                tools = payload.get("tools") or []
                status_box.info(f"识别到工具：{len(tools)}")

            elif ev_type == "tool_end":
                tn = payload.get("tool") or "unknown"
                rs = payload.get("result")
                tool_calls.append(
                    {
                        "name": tn,
                        "status": "done",
                        "detail": json.dumps(rs or {}, ensure_ascii=False, indent=2)[:2000],
                    }
                )
                status_box.info(f"工具完成：{tn}")

            elif ev_type == "message":
                m = payload.get("message") or {}
                content = m.get("content") or ""
                if content:
                    full_text = (full_text + "\n\n" + content).strip()
                    if assistant_placeholder is None:
                        with st.chat_message("assistant"):
                            assistant_placeholder = st.empty()
                    assistant_placeholder.markdown(full_text)

            elif ev_type == "report":
                report_html = (payload.get("report_html") or "").strip()

            elif ev_type == "done":
                done_result = payload.get("result")

    except Exception as exc:
        status_box.error(f"请求失败：{exc}")
        full_text = full_text or f"请求失败：{exc}"

    if not full_text and done_result is not None:
        try:
            full_text = json.dumps(done_result, ensure_ascii=False, indent=2)[:4000]
        except Exception:
            full_text = str(done_result)

    if assistant_placeholder is None:
        with st.chat_message("assistant"):
            assistant_placeholder = st.empty()
    assistant_placeholder.markdown(full_text or last_status or "已完成")

    st.session_state["chat_history"].append(
        {
            "role": "assistant",
            "content": full_text or last_status or "已完成",
            "tool_calls": tool_calls,
            "report_html": report_html,
        }
    )
    add_message(conv_id, "assistant", full_text or last_status or "已完成", {"tool_calls": tool_calls})

    if tool_calls:
        with st.expander("工具调用详情"):
            for t in tool_calls:
                st.markdown(f"{t.get('name')}：{t.get('status')}")
                detail = t.get("detail") or ""
                if detail:
                    st.code(detail, language="json")

    if report_html:
        st.divider()
        st.subheader("晨会简报")
        st.html(report_html[:8000])

    status_box.empty()


_init_state()
_render_sidebar()
_render_header()
_render_status_row()
st.divider()
_render_history()

prompt = st.chat_input("输入您的问题，例如：请生成今日晨会简报")
if prompt:
    _handle_prompt(prompt)
