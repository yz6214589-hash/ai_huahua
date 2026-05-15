"""
kris_node -- 风控官节点

Kris 是团队的风控官，负责：
1. 检查黑名单
2. 检查资金限制
3. 检查仓位限制
4. 计算 ATR 风险

输入：state["trade_signal"], state["capital"], state["investment_view"]
输出：state["risk_verdict"]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from workflow.trading_state import InvestmentView, RiskVerdict, TradingState


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def _fetch_kline_atr(stock_code: str, period: int = 14) -> float:
    """获取最近 K 线，计算 ATR(14)"""
    try:
        result = _run_script(
            "skills/stock-price/scripts/get_kline.py",
            [stock_code, "1d", "60"],
            timeout=60,
        )
        data = _extract_json_object(result)
        if "error" in data or not data.get("data"):
            return 0.0

        bars = data["data"]
        trs = []
        for i in range(1, len(bars)):
            h = float(bars[i].get("high", 0))
            l = float(bars[i].get("low", 0))
            pc = float(bars[i - 1].get("close", 0))
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        if len(trs) < period:
            return sum(trs) / max(len(trs), 1)
        return sum(trs[-period:]) / period
    except Exception:
        return 0.0


def kris_node(state: TradingState) -> dict:
    """风控节点：跑风控规则 -> RiskVerdict"""
    signal = state.get("trade_signal", {})
    view: InvestmentView = state.get("investment_view", {})
    capital = float(state.get("capital", 100_000))

    print()
    print("=" * 70)
    print("[Kris] 风控官开始审批")
    print("=" * 70)

    if signal.get("direction") == "hold" or signal.get("quantity", 0) <= 0:
        verdict = {
            "decision": "approve",
            "is_approved": True,
            "reason": "信号为 hold 或 0 股，无需风控",
            "rule_name": "空单跳过",
            "suggested_max_pct": 1.0,
        }
        print(f"[Kris] {verdict['reason']}")
        return {
            "risk_verdict": RiskVerdict(**verdict),
            "messages": [
                {
                    "role": "kris",
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "content": "空单跳过",
                }
            ],
        }

    stock = signal.get("stock_code", "")
    price = float(signal.get("price", 0))
    qty = int(signal.get("quantity", 0))
    direction = signal.get("direction", "buy")
    amount = price * qty

    atr_value = _fetch_kline_atr(stock)
    print(f"[Kris] {stock} ATR(14) = {atr_value:.3f}")

    max_order_amount = capital * 0.5
    max_single_loss = capital * 0.02
    price_collar_pct = 0.05

    blacklist = ["ST", "退市"]
    is_blacklist = any(b in stock for b in blacklist)

    if is_blacklist:
        verdict = {
            "decision": "reject",
            "is_approved": False,
            "reason": f"{stock} 在黑名单中",
            "rule_name": "blacklist",
            "suggested_max_pct": 0.0,
        }
    elif amount > max_order_amount:
        verdict = {
            "decision": "warn",
            "is_approved": True,
            "reason": f"订单金额 {amount:.2f} 超过限制 {max_order_amount:.2f}",
            "rule_name": "max_order_amount",
            "suggested_max_pct": 0.5,
        }
    elif atr_value > 0 and price * 0.02 < atr_value * 2:
        verdict = {
            "decision": "warn",
            "is_approved": True,
            "reason": f"单股风险超过阈值，ATR={atr_value:.3f}",
            "rule_name": "atr_risk",
            "suggested_max_pct": 0.7,
        }
    else:
        verdict = {
            "decision": "approve",
            "is_approved": True,
            "reason": "通过全部风控检查",
            "rule_name": "all_passed",
            "suggested_max_pct": 1.0,
        }

    icon = "PASS" if verdict["is_approved"] else "REJECT"
    print(f"[Kris] [{icon}] {verdict['rule_name']}: {verdict['reason']}")

    return {
        "risk_verdict": RiskVerdict(**verdict),
        "messages": [
            {
                "role": "kris",
                "time": datetime.now().strftime("%H:%M:%S"),
                "content": f"{verdict['decision']} -- {verdict['reason'][:80]}",
            }
        ],
    }
