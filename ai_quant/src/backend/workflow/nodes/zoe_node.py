"""
zoe_node -- 信号官节点

Zoe 是团队的技术分析师，负责：
1. 运行策略回测获取 MACD 等技术信号
2. 结合 Charles 的基本面观点
3. 决定交易方向和仓位

输入：state["stock_code"], state["capital"], state["investment_view"], state.get("risk_verdict")
输出：state["trade_signal"]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from workflow.trading_state import InvestmentView, RiskVerdict, TradeSignal, TradingState


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _run_script(script_path: str, args: list[str] | None = None, timeout: int = 180) -> str:
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
    return (result.stdout or "").strip() or "(no output)"


def _extract_json_object(text: str) -> dict:
    """从混杂文本中提取最后一个合法 JSON 对象"""
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

    for blk in reversed(blocks):
        try:
            data = json.loads(blk)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return {}


def _decide_position_pct(stance: str, confidence: float) -> float:
    """根据 Charles 立场和信心决定基础开仓比例"""
    base = {"bullish": 0.30, "neutral": 0.10, "bearish": 0.0}.get(stance, 0.10)
    return base * confidence


def zoe_node(state: TradingState) -> dict:
    """信号节点：跑 MACD 回测 + 结合投研观点 -> TradeSignal"""
    stock = state["stock_code"]
    capital = float(state.get("capital", 100_000))
    view: InvestmentView = state.get("investment_view", {})
    last_verdict: RiskVerdict = state.get("risk_verdict", {})

    print()
    print("=" * 70)
    print(f"[Zoe] 信号官开始工作 -- 标的: {stock}")
    print("=" * 70)

    bt_data = {}
    try:
        bt_result = _run_script(
            "skills/strategy-backtest/scripts/run_backtest.py",
            ["--code", stock, "--strategy", "macd", "--count", "250"],
            timeout=180,
        )
        bt_data = _extract_json_object(bt_result)
        print(f"[Zoe] 回测结果: {bt_data}")
    except Exception as e:
        print(f"[Zoe] 回测失败: {e}")

    latest_signal = bt_data.get("latest_signal", "none")
    latest_close = float(bt_data.get("latest_close", 0) or 0)
    win_rate = float(bt_data.get("win_rate", 0) or 0)
    total_return = float(bt_data.get("total_return", 0) or 0)

    stance = view.get("stance", "neutral")
    confidence = float(view.get("confidence", 0.5))
    catalysts = view.get("catalysts", []) or []
    risks = view.get("risks", []) or []

    if catalysts:
        print(f"[Zoe] Charles 催化剂参考: {catalysts[0][:60] if catalysts else ''}")
    if risks:
        print(f"[Zoe] Charles 风险提醒: {risks[0][:60] if risks else ''}")

    if latest_signal in ("golden_cross", "bullish") and stance == "bullish":
        direction = "buy"
        pos_pct = _decide_position_pct(stance, confidence)
        reason = f"共振: MACD {latest_signal} + Charles bullish({confidence:.2f})"
    elif latest_signal in ("death_cross", "bearish") and stance == "bearish":
        direction = "sell"
        pos_pct = 0.0
        reason = f"共振: MACD {latest_signal} + Charles bearish"
    elif stance == "bullish" and confidence >= 0.7 and latest_signal in ("bearish", "death_cross"):
        direction = "buy"
        pos_pct = _decide_position_pct(stance, confidence) * 0.5
        reason = f"分歧: Charles 强势 bullish({confidence:.2f}), MACD {latest_signal} -> 小仓试探"
    elif stance == "neutral" and latest_signal in ("golden_cross", "bullish"):
        direction = "buy"
        pos_pct = _decide_position_pct(stance, confidence)
        reason = f"技术面驱动: MACD {latest_signal} + Charles 中性"
    else:
        direction = "hold"
        pos_pct = 0.0
        reason = f"观望: MACD {latest_signal} + Charles {stance}({confidence:.2f})"

    suggested_max = float(last_verdict.get("suggested_max_pct", 1.0))
    if suggested_max < 1.0 and direction == "buy":
        old_pct = pos_pct
        pos_pct = min(pos_pct, suggested_max)
        print(f"[Zoe] 上一轮 Kris 建议仓位上限 {suggested_max:.0%}，缩量 {old_pct:.0%} -> {pos_pct:.0%}")

    if direction == "buy" and latest_close > 0:
        amount = capital * pos_pct
        quantity = int(amount / latest_close / 100) * 100
        if quantity == 0:
            quantity = 100
            print(f"[Zoe] 算出仓位不足 1 手，按最小试探单 100 股出单")
    elif direction == "sell":
        quantity = 0
    else:
        quantity = 0

    signal = {
        "stock_code": stock,
        "direction": direction,
        "quantity": quantity,
        "price": latest_close,
        "reason": reason,
        "strategy": bt_data.get("strategy", "MACD"),
        "latest_signal": latest_signal,
        "latest_close": latest_close,
        "backtest_winrate": win_rate,
        "backtest_total_return": total_return,
    }

    print(f"[Zoe] 决策: {direction.upper()} {quantity}股 @ {latest_close} | {reason}")

    return {
        "trade_signal": TradeSignal(**signal),
        "messages": [
            {
                "role": "zoe",
                "time": datetime.now().strftime("%H:%M:%S"),
                "content": f"{direction} {quantity}股 @ {latest_close} ({reason})",
            }
        ],
    }
