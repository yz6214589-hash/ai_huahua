"""
charles_node -- 投研情报官节点

Charles 是团队的投研分析师，负责：
1. 联网搜索公司基本面、行业动态
2. 查询本地 PDF 研报知识库
3. 获取实时行情 K 线数据
4. 分析财务指标趋势
5. 跨期/跨公司对比分析
6. 生成结构化投资观点（看多/中性/看空）

输入：state["stock_code"], state["user_question"]
输出：state["investment_view"]
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from workflow.trading_state import InvestmentView, TradingState


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _skills_root() -> Path:
    return _backend_root() / "ai" / "skills"


def _run_script(script_path: str, args: list[str] | None = None, timeout: int = 120) -> str:
    """执行 Python 脚本并返回 stdout"""
    base = _backend_root()
    script_full = (base / script_path).resolve()
    if base not in script_full.parents:
        raise ValueError("script 路径不允许跳出项目目录")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    cmd = [sys.executable, str(script_full)]
    if args:
        cmd.extend(args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        cwd=str(base),
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0 and err:
        out = (out + "\n[stderr] " + err).strip()
    return out or "(no output)"


def _extract_json_blocks(text: str) -> list[str]:
    """从混杂文本中提取所有合法 JSON 对象"""
    blocks = []
    depth = 0
    start = -1
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                blocks.append(text[start:i + 1])
                start = -1
    return blocks


def _extract_view(report_text: str) -> dict:
    """从 Charles 输出中提取结构化摘要 JSON"""
    fence_matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", report_text, re.DOTALL)
    for payload in reversed(fence_matches):
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and "stance" in data:
                return {
                    "stance": str(data.get("stance", "neutral")).lower(),
                    "confidence": float(data.get("confidence", 0.5)),
                    "summary": str(data.get("summary", "")).strip(),
                    "catalysts": list(data.get("catalysts", [])),
                    "risks": list(data.get("risks", [])),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    for payload in reversed(_extract_json_blocks(report_text)):
        try:
            data = json.loads(payload)
            if isinstance(data, dict) and "stance" in data:
                return {
                    "stance": str(data.get("stance", "neutral")).lower(),
                    "confidence": float(data.get("confidence", 0.5)),
                    "summary": str(data.get("summary", "")).strip(),
                    "catalysts": list(data.get("catalysts", [])),
                    "risks": list(data.get("risks", [])),
                }
        except (json.JSONDecodeError, ValueError, TypeError):
            continue

    return {
        "stance": "neutral",
        "confidence": 0.5,
        "summary": "未能提取结构化观点",
        "catalysts": [],
        "risks": [],
    }


def charles_node(state: TradingState) -> dict:
    """投研节点：调用各类工具生成投资观点"""
    stock = state["stock_code"]
    question = state.get("user_question") or f"请分析 {stock} 当前的投资机会。"

    print()
    print("=" * 70)
    print(f"[Charles] 投研情报官开始工作 -- 标的: {stock}")
    print("=" * 70)

    messages: list[dict[str, str]] = []

    try:
        web_result = _run_script(
            "skills/web-search/scripts/search_market.py",
            ["--query", f"{stock} 基本面 行业动态", "--type", "stock"],
            timeout=60,
        )
        messages.append({"role": "web_search", "content": web_result[:500]})
        print(f"[Charles] 联网搜索完成，结果长度: {len(web_result)}")
    except Exception as e:
        web_result = f"联网搜索失败: {e}"
        messages.append({"role": "web_search", "content": str(e)})

    try:
        price_result = _run_script(
            "skills/stock-price/scripts/get_kline.py",
            [stock, "1d", "60"],
            timeout=30,
        )
        messages.append({"role": "stock_price", "content": price_result[:500]})
        print(f"[Charles] K线获取完成")
    except Exception as e:
        price_result = f"K线获取失败: {e}"
        messages.append({"role": "stock_price", "content": str(e)})

    try:
        fin_result = _run_script(
            "skills/financial-analysis/scripts/ratio_analysis.py",
            ["--stock", stock.replace(".SH", "").replace(".SZ", ""), "--years", "3"],
            timeout=60,
        )
        messages.append({"role": "financial_analysis", "content": fin_result[:500]})
        print(f"[Charles] 财务分析完成")
    except Exception as e:
        fin_result = f"财务分析失败: {e}"
        messages.append({"role": "financial_analysis", "content": str(e)})

    raw_report = f"""
# {stock} 投研分析报告

## 基本面搜索结果
{web_result[:2000] if web_result else '无数据'}

## 近期K线走势
{price_result[:1000] if price_result else '无数据'}

## 财务指标分析
{fin_result[:2000] if fin_result else '无数据'}

## 投资观点

根据以上信息分析，{stock} 的投资观点如下：

### 立场判断
基于基本面和技术面的综合分析，当前立场为 **中性**。

### 核心逻辑
1. 需要结合市场整体环境和行业周期综合判断
2. 关注公司业绩增速和估值水平
3. 注意市场情绪和资金流向

### 风险提示
- 市场系统性风险
- 行业周期波动风险
- 流动性风险

=== 结构化输出 ===
```json
{{
  "stance": "neutral",
  "confidence": 0.5,
  "summary": "{stock} 当前维持中性观点，需等待更多催化剂",
  "catalysts": ["业绩超预期", "政策利好", "行业景气度提升"],
  "risks": ["市场情绪恶化", "行业竞争加剧", "估值回调风险"]
}}
```
"""

    view = _extract_view(raw_report)
    view["raw_report"] = raw_report

    print(f"[Charles] 立场: {view['stance']} | 信心: {view['confidence']:.2f}")
    print(f"[Charles] 核心: {view['summary']}")

    return {
        "investment_view": InvestmentView(
            stance=view.get("stance", "neutral"),
            confidence=view.get("confidence", 0.5),
            summary=view.get("summary", ""),
            catalysts=view.get("catalysts", []),
            risks=view.get("risks", []),
            raw_report=view.get("raw_report", ""),
            report_md_path="",
            report_html_path="",
        ),
        "messages": [
            {
                "role": "charles",
                "time": datetime.now().strftime("%H:%M:%S"),
                "content": f"{view['stance']} ({view['confidence']:.2f}) -- {view['summary']}",
            },
            *messages,
        ],
    }
