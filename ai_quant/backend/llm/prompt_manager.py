"""
提示词管理器模块

负责从 admin_prompts 表读取自定义提示词模板，支持变量替换。
若数据库中无自定义配置，则返回模块内提供的默认值。

提供以下方法：
- get_prompt: 通用提示词获取
- get_system_prompt: 获取系统提示词
- get_rag_prompt: 获取RAG研报提示词
- get_zoe_prompt: 获取Zoe信号提示词
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..api.admin_db import get_admin_db

_DEFAULT_SYSTEM_PROMPT = (
    "你是 AI 量化投资助手，负责数据查询、研报分析、舆情监控、策略回测与交易辅助。\n"
    "\n"
    "=== 可用工具 ===\n"
    "可通过工具查询数据、分析股票、搜索信息、生成报告。\n"
    "\n"
    "=== 核心工作方法论 ===\n"
    "当用户要求写研报、深度分析、五步法分析时，你应该自己做研究和分析。\n"
    "核心方法论: 国泰君安\"五步法\"（信息差 -> 逻辑差 -> 预期差 -> 催化剂 -> 结论+风险闭环）。\n"
    "\n"
    "=== 规则 ===\n"
    "- 优先选择最匹配的工具\n"
    "- 最终回答必须是中文\n"
    "- 投资建议需附带风险提示\n"
)

_DEFAULT_RAG_PROMPT = (
    "你是资深买方研究员与投资经理助理。"
    "请基于用户提供的数据快照与RAG材料，生成一份严谨、结构化、可读性强的中文个股研报。"
    "必须输出 Markdown，包含所有章节；不要输出与任务无关的解释。"
)

_DEFAULT_ZOE_PROMPT = (
    "你是行业研究员 Zoe，专注于基本面分析、财务分析和行业研究。"
    "你擅长分析上市公司的财务数据、行业格局和竞争态势。"
    "请基于提供的财务数据和行业信息，给出专业的基本面分析结论。"
)


def _get_prompt_from_db(category: str, name: str | None = None) -> dict[str, Any] | None:
    """从数据库获取指定分类和名称的提示词模板"""
    conn, lock = get_admin_db()
    with lock:
        try:
            cur = conn.cursor()
            if name:
                cur.execute(
                    "SELECT id, category, name, content, version, variables FROM admin_prompts "
                    "WHERE category = ? AND name = ? ORDER BY version DESC LIMIT 1",
                    (category, name),
                )
            else:
                cur.execute(
                    "SELECT id, category, name, content, version, variables FROM admin_prompts "
                    "WHERE category = ? ORDER BY version DESC LIMIT 1",
                    (category,),
                )
            row = cur.fetchone()
            if not row:
                return None
            result = dict(row)
            try:
                result["variables"] = json.loads(result["variables"]) if isinstance(result["variables"], str) else (result["variables"] or [])
            except Exception:
                result["variables"] = []
            return result
        finally:
            conn.close()


def _render_template(content: str, variables: dict[str, str] | None) -> str:
    """替换模板中的 {变量} 占位符"""
    if not variables:
        return content
    rendered = content
    for var_name, var_value in variables.items():
        placeholder = "{" + var_name + "}"
        rendered = rendered.replace(placeholder, str(var_value))
    return rendered


class PromptManager:
    """提示词管理器，支持从数据库读取自定义模板"""

    @staticmethod
    def get_prompt(category: str, name: str | None = None, variables: dict[str, str] | None = None) -> str:
        """获取提示词模板，支持变量替换

        Args:
            category: 模板分类 (system, rag, zoe, other)
            name: 模板名称，为 None 时返回该分类下第一个模板
            variables: 替换变量字典

        Returns:
            str: 渲染后的提示词内容
        """
        record = _get_prompt_from_db(category, name)
        if record:
            return _render_template(record["content"], variables)

        if category == "system":
            return _render_template(_DEFAULT_SYSTEM_PROMPT, variables)
        elif category == "rag":
            return _render_template(_DEFAULT_RAG_PROMPT, variables)
        elif category == "zoe":
            return _render_template(_DEFAULT_ZOE_PROMPT, variables)
        else:
            return _render_template("", variables)

    @staticmethod
    def get_system_prompt() -> str:
        """获取系统提示词（默认 + 自定义覆盖）"""
        return PromptManager.get_prompt("system", "default")

    @staticmethod
    def get_rag_prompt() -> str:
        """获取RAG研报提示词"""
        return PromptManager.get_prompt("rag", "default")

    @staticmethod
    def get_zoe_prompt() -> str:
        """获取Zoe信号提示词"""
        return PromptManager.get_prompt("zoe", "default")
