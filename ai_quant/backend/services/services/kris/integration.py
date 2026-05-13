"""
Kris 服务模块 - 风险管理与订单审批服务

本模块提供以下核心功能：
- 订单审批决策：对交易订单进行风险检查和审批
- 多种决策类型：APPROVE（批准）、WARN（警告）、REJECT（拒绝）
- 审计日志：记录所有订单审批的详细信息
- 风险规则检查：包括资产验证、方向验证、波动率检查、持仓限制等

使用单例模式的 RiskManager 管理风险检查逻辑和审计日志。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


# 单例模式的 RiskManager 实例
_KRIS_MANAGER = None


def _get_manager():
    """
    获取 RiskManager 单例实例
    
    Returns:
        RiskManager: 风险管理器实例
    """
    global _KRIS_MANAGER
    if _KRIS_MANAGER is not None:
        return _KRIS_MANAGER
    _KRIS_MANAGER = RiskManager()
    return _KRIS_MANAGER


class Decision(Enum):
    """
    订单审批决策枚举
    
    - APPROVE: 批准订单
    - WARN: 警告/限制订单（降低交易量）
    - REJECT: 拒绝订单
    """
    APPROVE = "APPROVE"
    WARN = "WARN"
    REJECT = "REJECT"


@dataclass(frozen=True)
class DecisionResult:
    """
    审批决策结果数据类
    
    Attributes:
        decision: 决策类型（APPROVE/WARN/REJECT）
        reason: 决策原因描述
        rule_name: 触发决策的规则名称
        max_position_pct: 最大持仓比例
        timestamp: 决策时间戳
    """
    decision: Decision
    reason: str
    rule_name: str
    max_position_pct: float
    timestamp: str


@dataclass(frozen=True)
class Order:
    """
    订单数据类
    
    Attributes:
        stock_code: 股票代码
        direction: 交易方向（buy/sell）
        amount: 交易金额
        price: 交易价格
        quantity: 交易数量
    """
    stock_code: str
    direction: str
    amount: float
    price: float
    quantity: int


def _now_iso() -> str:
    """
    获取当前时间的ISO格式字符串（秒级精度）
    
    Returns:
        str: ISO格式的当前时间字符串
    """
    return datetime.now().isoformat(timespec="seconds")


class RiskManager:
    """
    风险管理器
    
    负责执行订单的风险检查和审批决策。
    """
    
    def __init__(self) -> None:
        """初始化风险管理器，创建空审计日志"""
        self.audit_log: list[dict[str, Any]] = []

    def get_summary(self) -> dict[str, Any]:
        """
        获取风险管理器摘要信息
        
        Returns:
            dict[str, Any]: 服务状态和功能列表
        """
        return {"source": "kris", "status": "ready", "features": ["approve", "audit"], "mode": "embedded"}

    def approve_verbose(self, order: Order, portfolio: dict[str, Any], context: dict[str, Any]):
        """
        执行详细的风险审批检查
        
        执行多层风险检查，返回最终决策和所有检查结果。
        
        Args:
            order: 待审批的订单
            portfolio: 投资组合信息（总资产、价格、ATR等）
            context: 额外上下文信息（如新闻文本）
        
        Returns:
            tuple[DecisionResult, list[DecisionResult]]: (最终决策, 所有检查结果列表)
        """
        ts = _now_iso()
        checks: list[DecisionResult] = []

        # 检查1：验证总资产是否有效
        total_asset = float(portfolio.get("total_asset") or 0.0)
        if total_asset <= 0.0:
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_total_asset",
                rule_name="portfolio.total_asset",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        # 检查2：验证交易方向
        direction = str(order.direction or "").lower().strip()
        if direction not in ("buy", "sell"):
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_direction",
                rule_name="order.direction",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        # 检查3：验证交易金额
        amount = float(order.amount or 0.0)
        if amount <= 0.0:
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_amount",
                rule_name="order.amount",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        # 初始化默认最大持仓比例（10%）
        max_pct = 0.1
        # 获取价格和ATR数据
        prices = portfolio.get("prices") if isinstance(portfolio.get("prices"), dict) else {}
        atrs = portfolio.get("atr") if isinstance(portfolio.get("atr"), dict) else {}
        px = prices.get(order.stock_code)
        atr = atrs.get(order.stock_code)
        try:
            px_f = float(px) if px is not None else float(order.price or 0.0)
        except Exception:
            px_f = float(order.price or 0.0)
        try:
            atr_f = float(atr) if atr is not None else None
        except Exception:
            atr_f = None

        # 检查4：波动率检查（基于ATR）
        # 如果波动率高于6%，降低最大持仓比例到5%
        if atr_f is not None and px_f > 0:
            vol = atr_f / px_f
            if vol >= 0.06:
                max_pct = min(max_pct, 0.05)
                checks.append(
                    DecisionResult(
                        decision=Decision.WARN,
                        reason="high_volatility",
                        rule_name="portfolio.atr",
                        max_position_pct=max_pct,
                        timestamp=ts,
                    )
                )

        # 检查5：负面新闻检查
        news_text = str(context.get("news_text") or "")
        if news_text and any(x in news_text for x in ("暴雷", "立案", "退市", "重大风险", "风险提示")):
            checks.append(
                DecisionResult(
                    decision=Decision.WARN,
                    reason="negative_news",
                    rule_name="context.news",
                    max_position_pct=max_pct,
                    timestamp=ts,
                )
            )

        # 检查6：硬性持仓限制（超过20%直接拒绝）
        req_pct = amount / total_asset if total_asset > 0 else 0.0
        if req_pct > 0.2:
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="exceeds_hard_limit",
                rule_name="position.hard_limit",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        # 检查7：超过最大持仓比例警告
        if req_pct > max_pct:
            final = DecisionResult(
                decision=Decision.WARN,
                reason="exceeds_max_position_pct",
                rule_name="position.max_pct",
                max_position_pct=max_pct,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks

        # 所有检查通过，批准订单
        final = DecisionResult(
            decision=Decision.APPROVE,
            reason="approved",
            rule_name="ok",
            max_position_pct=max_pct,
            timestamp=ts,
        )
        checks.append(final)
        self._audit(order, final, ts)
        return final, checks

    def _audit(self, order: Order, final: DecisionResult, ts: str) -> None:
        """
        记录审批决策到审计日志
        
        Args:
            order: 被审批的订单
            final: 最终决策结果
            ts: 时间戳
        """
        self.audit_log.append(
            {
                "timestamp": ts,
                "stock_code": order.stock_code,
                "direction": order.direction,
                "amount": float(order.amount),
                "price": float(order.price),
                "quantity": int(order.quantity),
                "decision": final.decision.value,
                "reason": final.reason,
                "rule_name": final.rule_name,
                "max_position_pct": float(final.max_position_pct),
            }
        )


def _decision_to_dict(d: Any) -> dict[str, Any]:
    """
    将 DecisionResult 对象转换为字典格式
    
    Args:
        d: DecisionResult 对象或类似对象
    
    Returns:
        dict[str, Any]: 包含决策信息的字典
    """
    raw = getattr(d, "decision", None)
    decision = getattr(raw, "value", None) if raw is not None else None
    if decision is None:
        decision = str(raw or "")
    return {
        "decision": decision,
        "reason": getattr(d, "reason", ""),
        "rule_name": getattr(d, "rule_name", ""),
        "max_position_pct": float(getattr(d, "max_position_pct", 0.0) or 0.0),
        "timestamp": getattr(d, "timestamp", ""),
    }


def _calc_suggestion(order: Any, final: Any) -> tuple[int, int]:
    """
    根据决策结果计算建议的交易参数
    
    - APPROVE: 返回原始订单的金额和数量
    - WARN: 按最大持仓比例缩减交易量
    - REJECT: 返回0
    
    Args:
        order: 原始订单对象
        final: 最终决策结果
    
    Returns:
        tuple[int, int]: (建议金额, 建议数量)
    """
    raw = getattr(final, "decision", None)
    decision = getattr(raw, "value", None) if raw is not None else None
    if decision is None:
        decision = str(raw or "")
    decision = decision.upper()
    if decision == "WARN":
        # 按最大持仓比例缩减
        pct = float(final.max_position_pct or 0)
        amt = max(0.0, float(order.amount) * pct)
        qty = int(amt / float(order.price) / 100) * 100 if order.price > 0 else 0
        return int(round(qty * float(order.price))), qty
    if decision == "APPROVE":
        return int(round(order.amount)), int(order.quantity)
    return 0, 0


def approve(payload: dict[str, Any]) -> dict[str, Any]:
    """
    审批订单
    
    对订单执行完整的风险检查流程，返回审批决策和建议参数。
    
    Args:
        payload: 包含order（订单）、portfolio（投资组合）、context（上下文）的字典
    
    Returns:
        dict[str, Any]: 包含决策、原因、建议参数和所有检查结果的字典
    """
    manager = _get_manager()
    order_in = payload.get("order") or {}
    portfolio_in = payload.get("portfolio") or {}
    context_in = payload.get("context") or {}
    # 构建订单对象
    order = Order(
        stock_code=str(order_in.get("stock_code") or ""),
        direction=str(order_in.get("direction") or "buy"),
        amount=float(order_in.get("amount") or 0),
        price=float(order_in.get("price") or 0),
        quantity=int(order_in.get("quantity") or 0),
    )
    # 构建投资组合数据
    portfolio = {
        "total_asset": float(portfolio_in.get("total_asset") or 0),
        "prices": dict(portfolio_in.get("prices") or {}),
        "atr": dict(portfolio_in.get("atr") or {}),
    }
    # 构建上下文数据
    context = {"news_text": str(context_in.get("news_text") or "")}
    # 执行风险检查
    final, checks = manager.approve_verbose(order, portfolio, context)
    # 计算建议的交易参数
    suggested_amount, suggested_quantity = _calc_suggestion(order, final)
    base = _decision_to_dict(final)
    return {
        **base,
        "suggested_amount": int(suggested_amount),
        "suggested_quantity": int(suggested_quantity),
        "checks": [_decision_to_dict(x) for x in checks],
    }


def audit(last_n: int = 200) -> dict[str, Any]:
    """
    获取审计日志
    
    返回最近的订单审批记录。
    
    Args:
        last_n: 返回的记录数量上限（最大2000）
    
    Returns:
        dict[str, Any]: 包含items（审计日志列表）的字典
    """
    manager = _get_manager()
    n = max(1, min(int(last_n), 2000))
    return {"items": list(manager.audit_log[-n:])}


def status() -> dict[str, Any]:
    """
    获取 Kris 服务状态信息
    
    Returns:
        dict[str, Any]: 服务状态和功能列表
    """
    manager = _get_manager()
    return manager.get_summary()
