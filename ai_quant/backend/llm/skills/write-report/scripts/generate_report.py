#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自包含的研报生成器（无需 FAISS/RAG 依赖）

通过通义千问的联网搜索能力（enable_search=True），自动搜索上市公司信息，
然后按照国泰君安五步法框架生成完整的深度分析研报。

用法:
    python generate_report.py --stock_name 海南发展
    python generate_report.py --stock_name 海南发展 --model qwen-max
"""

import argparse
import json
import os
import sys
from openai import OpenAI


def generate_report(stock_name: str, model: str = "qwen-plus") -> dict:
    """生成五步法深度研报"""
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        return {"status": "error", "message": "缺少环境变量 DASHSCOPE_API_KEY"}

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )

    system_prompt = f"""你是国泰君安研究所的资深分析师，擅长使用"五步法"框架进行深度股票分析。
请对{stock_name}进行全面、深入的调研分析，输出结构化的投资研报。

## 核心方法论：国泰君安"五步法"

### Step 1：信息差 — 市场还不知道/忽视了什么？
分析{stock_name}被市场忽视的关键信息：
- 公司基本面中的隐藏亮点（新业务、新增长点）
- 市场尚未充分反应的财报数据
- 行业变化中的先发优势
- 提供3-5个具体的数据点佐证

### Step 2：逻辑差 — 市场的推理错在哪里？
识别市场对{stock_name}的常见误读：
- 市场的主流叙事是什么？
- 这个叙事可能错在哪里？
- 正确的因果逻辑链是什么？
- 数据依据是什么？

### Step 3：预期差 — 一致预期 vs 实际偏离多大？
量化市场预期与实际的偏离：
- 营收/净利润/毛利率等核心指标的市场一致预期
- 基于分析得出的合理预期
- 偏离幅度定量分析
- 判断偏离是一次性还是可持续的

### Step 4：催化剂 — 什么事件会引爆重估？
识别可能触发价值重估的事件：
- 短期催化剂（1-3个月）
- 中期催化剂（3-12个月）
- 潜在负面催化剂

### Step 5：结论 + 风险闭环
- 核心观点（一句话总结）
- 投资逻辑（3-5个要点）
- 投资评级（强烈推荐/推荐/中性/回避）
- 关键假设与失效条件
- 必须明确指出"哪个假设出错会导致整个结论崩塌"

## 输出要求
1. 格式：结构化 Markdown
2. 必须有公司概况/行业背景介绍
3. 每个步骤的分析必须附具体数据支撑
4. 数据必须标注来源
5. 末尾附免责声明

请现在开始对{stock_name}进行完整分析。"""

    user_prompt = f"请对{stock_name}进行全面、深度的五步法分析，输出完整研报。"

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=8192,
        extra_body={"enable_search": True},
    )

    report = response.choices[0].message.content

    return {
        "status": "success",
        "stock_name": stock_name,
        "model": model,
        "report": report,
        "report_length": len(report),
    }


def main():
    parser = argparse.ArgumentParser(description="五步法研报生成器")
    parser.add_argument("--stock_name", required=True, help="公司名称，如：海南发展")
    parser.add_argument("--model", default="qwen-plus", help="LLM 模型（默认 qwen-plus）")
    args = parser.parse_args()

    result = generate_report(args.stock_name, args.model)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
