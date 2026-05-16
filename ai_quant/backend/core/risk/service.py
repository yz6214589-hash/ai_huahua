"""
风控模块 - 风险管理与订单审批
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from infra.storage.logging_service import get_logger

logger = get_logger("risk")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


_AUDIT_DIR = _project_root() / ".ai_quant" / "risk" / "audit"


def _ensure_audit_dir() -> None:
    path = _AUDIT_DIR
    path.mkdir(parents=True, exist_ok=True)
    logger.info("审计日志目录已就绪", extra={"dir_path": str(path)})


def _list_audit_files() -> list[Path]:
    _ensure_audit_dir()
    files = sorted(_AUDIT_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    logger.debug("审计日志目录扫描完成", extra={
        "dir": str(_AUDIT_DIR),
        "file_count": len(files),
    })
    return files


def _read_audit_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            logger.debug("审计日志文件读取成功", extra={
                "file": path.name,
                "stock_code": data.get("stock_code"),
                "decision": data.get("decision"),
            })
            return data
        else:
            logger.warning("审计日志文件格式异常", extra={
                "file": str(path),
                "expected": "dict",
                "actual": type(data).__name__,
            })
    except Exception as e:
        logger.warning("审计日志文件解析失败，已跳过", extra={
            "file": str(path),
            "error": str(e),
        })
    return None


def _write_audit_entry(entry: dict[str, Any]) -> None:
    _ensure_audit_dir()
    ts = str(entry.get("timestamp") or "")
    stock_code = str(entry.get("stock_code") or "unknown")
    safe_ts = ts.replace(":", "-").replace("T", "_")
    filename = f"{safe_ts}_{stock_code}.json"
    tmp = _AUDIT_DIR / f".{filename}.tmp"
    out = _AUDIT_DIR / filename
    logger.debug("审计日志开始写入文件", extra={
        "filename": filename,
        "decision": entry.get("decision"),
    })
    try:
        tmp.write_text(json.dumps(entry, ensure_ascii=False, default=str), encoding="utf-8")
        tmp.replace(out)
        logger.info("审计日志文件写入成功", extra={
            "file_path": str(out),
            "stock_code": stock_code,
            "decision": entry.get("decision"),
            "file_size": out.stat().st_size if out.exists() else 0,
        })
    except Exception as e:
        logger.error("审计日志文件写入失败", extra={
            "stock_code": stock_code,
            "filename": filename,
            "error": str(e),
            "error_type": type(e).__name__,
        })


def _load_audit_logs() -> list[dict[str, Any]]:
    items: list[tuple[float, dict[str, Any]]] = []
    files = _list_audit_files()
    logger.info("审计日志开始从文件加载", extra={"file_count": len(files)})
    for p in files:
        data = _read_audit_file(p)
        if data is not None:
            try:
                mtime = p.stat().st_mtime
            except Exception:
                mtime = 0.0
            items.append((mtime, data))
    items.sort(key=lambda x: x[0], reverse=True)
    logger.info("审计日志从文件加载完成", extra={
        "total_files": len(files),
        "success_loaded": len(items),
        "skipped": len(files) - len(items),
    })
    return [x[1] for x in items]


#
#  黑名单检查
#

_STOCK_BLACKLIST_PREFIXES = (
    "ST", "*ST", "S*ST", "SST", "NST",
)

_STOCK_BLACKLIST_KEYWORDS = (
    "退市", "退", "ST",
)


def _check_stock_blacklist(stock_code: str, stock_name: str = "") -> bool:
    code_upper = str(stock_code or "").strip().upper()
    name_upper = str(stock_name or "").strip().upper()

    logger.debug("黑名单检查开始", extra={
        "stock_code": stock_code,
        "stock_name": stock_name,
        "code_upper": code_upper,
        "name_upper": name_upper,
    })

    for prefix in _STOCK_BLACKLIST_PREFIXES:
        if code_upper.startswith(prefix):
            logger.info("黑名单检查命中", extra={
                "stock_code": stock_code,
                "reason": f"股票代码前缀匹配黑名单: {prefix}",
                "rule": "stock.blacklist.prefix",
            })
            return True
        if name_upper.startswith(prefix):
            logger.info("黑名单检查命中", extra={
                "stock_code": stock_code,
                "stock_name": stock_name,
                "reason": f"股票名称前缀匹配黑名单: {prefix}",
                "rule": "stock.blacklist.prefix",
            })
            return True

    for keyword in _STOCK_BLACKLIST_KEYWORDS:
        if keyword in name_upper:
            logger.info("黑名单检查命中", extra={
                "stock_code": stock_code,
                "stock_name": stock_name,
                "reason": f"股票名称关键词匹配黑名单: {keyword}",
                "rule": "stock.blacklist.keyword",
            })
            return True

    logger.info("黑名单检查通过", extra={
        "stock_code": stock_code,
        "stock_name": stock_name or "未查询到名称",
    })
    return False


def _query_stock_name_from_mysql(stock_code: str) -> str:
    logger.debug("开始查询股票名称", extra={"stock_code": stock_code})
    try:
        from core.db import connect, load_mysql_config, query_dict
        cfg = load_mysql_config()
        conn = connect(cfg)
        try:
            rows = query_dict(
                conn,
                "SELECT stock_name FROM trade_stock_master WHERE stock_code = %s LIMIT 1",
                (stock_code,),
            )
            if rows and isinstance(rows[0], dict):
                name = str(rows[0].get("stock_name") or "").strip()
                if name:
                    logger.info("股票名称查询成功", extra={
                        "stock_code": stock_code,
                        "stock_name": name,
                    })
                    return name
                else:
                    logger.info("股票名称查询结果为空", extra={"stock_code": stock_code})
            else:
                logger.info("股票名称查询无记录", extra={
                    "stock_code": stock_code,
                    "rows_returned": len(rows) if rows else 0,
                })
        finally:
            conn.close()
    except Exception as e:
        logger.warning("查询股票名称失败，跳过黑名单数据库检查", extra={
            "stock_code": stock_code,
            "error": str(e),
            "error_type": type(e).__name__,
        })
    return ""


_RISK_MANAGER = None


def _get_manager():
    global _RISK_MANAGER
    if _RISK_MANAGER is not None:
        return _RISK_MANAGER
    _RISK_MANAGER = RiskManager()
    logger.info("RiskManager 全局实例创建")
    return _RISK_MANAGER


class Decision(Enum):
    APPROVE = "APPROVE"
    WARN = "WARN"
    REJECT = "REJECT"


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    reason: str
    rule_name: str
    max_position_pct: float
    timestamp: str


@dataclass(frozen=True)
class Order:
    stock_code: str
    direction: str
    amount: float
    price: float
    quantity: int


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class RiskManager:
    def __init__(self) -> None:
        self.audit_log: list[dict[str, Any]] = _load_audit_logs()
        logger.info("RiskManager 实例初始化完成", extra={
            "audit_log_count": len(self.audit_log),
        })

    def get_summary(self) -> dict[str, Any]:
        logger.debug("风控服务状态查询")
        return {"source": "risk", "status": "ready", "features": ["approve", "audit"], "mode": "embedded"}

    def approve_verbose(self, order: Order, portfolio: dict[str, Any], context: dict[str, Any]):
        ts = _now_iso()
        checks: list[DecisionResult] = []

        total_asset = float(portfolio.get("total_asset") or 0.0)
        logger.info("风控审批 - 步骤1: 总资产验证", extra={
            "stock_code": order.stock_code,
            "total_asset": total_asset,
        })
        if total_asset <= 0.0:
            logger.warning("风控审批 - 总资产验证失败", extra={
                "stock_code": order.stock_code,
                "total_asset": total_asset,
                "reason": "total_asset <= 0",
            })
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
        logger.info("风控审批 - 总资产验证通过", extra={
            "stock_code": order.stock_code,
            "total_asset": total_asset,
        })

        direction = str(order.direction or "").lower().strip()
        logger.info("风控审批 - 步骤2: 交易方向验证", extra={
            "stock_code": order.stock_code,
            "direction": direction,
        })
        if direction not in ("buy", "sell"):
            logger.warning("风控审批 - 交易方向验证失败", extra={
                "stock_code": order.stock_code,
                "direction": direction,
                "reason": "direction not in (buy, sell)",
            })
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
        logger.info("风控审批 - 交易方向验证通过", extra={
            "stock_code": order.stock_code,
            "direction": direction,
        })

        amount = float(order.amount or 0.0)
        logger.info("风控审批 - 步骤3: 金额验证", extra={
            "stock_code": order.stock_code,
            "amount": amount,
        })
        if amount <= 0.0:
            logger.warning("风控审批 - 金额验证失败", extra={
                "stock_code": order.stock_code,
                "amount": amount,
                "reason": "amount <= 0",
            })
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
        logger.info("风控审批 - 金额验证通过", extra={
            "stock_code": order.stock_code,
            "amount": amount,
        })

        max_pct = 0.1
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

        logger.info("风控审批 - 步骤4: ATR波动率检查", extra={
            "stock_code": order.stock_code,
            "price": px_f,
            "atr": atr_f,
            "atr_provided": atr is not None,
        })
        if atr_f is not None and px_f > 0:
            vol = atr_f / px_f
            logger.info("ATR波动率计算完成", extra={
                "stock_code": order.stock_code,
                "volatility": round(vol, 6),
                "threshold": 0.06,
            })
            if vol >= 0.06:
                max_pct = min(max_pct, 0.05)
                logger.info("ATR波动率超过阈值，降低仓位上限", extra={
                    "stock_code": order.stock_code,
                    "volatility": round(vol, 6),
                    "max_position_pct": max_pct,
                })
                checks.append(
                    DecisionResult(
                        decision=Decision.WARN,
                        reason="high_volatility",
                        rule_name="portfolio.atr",
                        max_position_pct=max_pct,
                        timestamp=ts,
                    )
                )
            else:
                logger.info("ATR波动率在安全范围内", extra={
                    "stock_code": order.stock_code,
                    "volatility": round(vol, 6),
                })
        else:
            logger.info("ATR数据不完整，跳过波动率检查", extra={
                "stock_code": order.stock_code,
                "atr_f": atr_f,
                "px_f": px_f,
            })

        qty = int(order.quantity or 0)
        logger.info("风控审批 - 步骤5: 数量验证", extra={
            "stock_code": order.stock_code,
            "quantity_input": order.quantity,
            "quantity_parsed": qty,
        })
        if qty <= 0:
            try:
                qty = int(amount / float(order.price) / 100) * 100 if float(order.price) > 0 else 0
                logger.info("根据金额自动计算数量", extra={
                    "stock_code": order.stock_code,
                    "amount": amount,
                    "price": order.price,
                    "quantity_calculated": qty,
                })
            except Exception as e:
                logger.warning("数量自动计算失败", extra={
                    "stock_code": order.stock_code,
                    "error": str(e),
                })
                qty = 0

        if qty <= 0:
            logger.warning("风控审批 - 数量验证失败", extra={
                "stock_code": order.stock_code,
                "reason": "quantity <= 0, 且无法自动计算",
            })
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="invalid_quantity",
                rule_name="order.quantity",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks
        logger.info("风控审批 - 数量验证通过", extra={
            "stock_code": order.stock_code,
            "quantity": qty,
        })

        logger.info("风控审批 - 步骤6: 黑名单检查", extra={
            "stock_code": order.stock_code,
        })
        stock_name = _query_stock_name_from_mysql(order.stock_code)
        if _check_stock_blacklist(order.stock_code, stock_name):
            logger.warning("风控审批 - 黑名单检查命中", extra={
                "stock_code": order.stock_code,
                "stock_name": stock_name,
            })
            final = DecisionResult(
                decision=Decision.REJECT,
                reason="stock_in_blacklist",
                rule_name="stock.blacklist",
                max_position_pct=0.0,
                timestamp=ts,
            )
            checks.append(final)
            self._audit(order, final, ts)
            return final, checks
        logger.info("风控审批 - 黑名单检查通过", extra={
            "stock_code": order.stock_code,
        })

        logger.info("风控审批 - 步骤7: 最大订单金额检查", extra={
            "stock_code": order.stock_code,
            "amount": amount,
            "total_asset": total_asset,
            "limit_pct": 0.5,
        })
        if amount > total_asset * 0.5:
            logger.info("风控审批 - 订单金额超过总资产50%，发出警告", extra={
                "stock_code": order.stock_code,
                "amount": amount,
                "total_asset": total_asset,
                "ratio": round(amount / total_asset, 4),
            })
            checks.append(
                DecisionResult(
                    decision=Decision.WARN,
                    reason="order_amount_exceeds_50pct",
                    rule_name="portfolio.max_order_amount",
                    max_position_pct=0.5,
                    timestamp=ts,
                )
            )
        else:
            logger.info("风控审批 - 订单金额在安全范围内", extra={
                "stock_code": order.stock_code,
                "amount": amount,
                "total_asset": total_asset,
                "ratio": round(amount / total_asset, 4) if total_asset > 0 else 0,
            })

        logger.info("风控审批 - 全部检查通过，最终决策: APPROVE", extra={
            "stock_code": order.stock_code,
            "max_position_pct": max_pct,
            "checks_count": len(checks),
        })
        final_decision = Decision.APPROVE
        final_reason = "ok"
        final_rule = "risk.default"
        final = DecisionResult(
            decision=final_decision,
            reason=final_reason,
            rule_name=final_rule,
            max_position_pct=max_pct,
            timestamp=ts,
        )
        checks.append(final)
        self._audit(order, final, ts)
        return final, checks

    def _audit(self, order: Order, final: DecisionResult, ts: str) -> None:
        raw = getattr(final, "decision", None)
        decision = getattr(raw, "value", None) if raw is not None else None
        if decision is None:
            decision = str(raw or "")
        entry = {
            "timestamp": ts,
            "stock_code": order.stock_code,
            "direction": order.direction,
            "amount": float(order.amount),
            "price": float(order.price),
            "quantity": int(order.quantity),
            "decision": decision,
            "reason": getattr(final, "reason", ""),
            "rule_name": getattr(final, "rule_name", ""),
            "max_position_pct": float(getattr(final, "max_position_pct", 0.0) or 0.0),
        }
        self.audit_log.append(entry)
        logger.info("审计日志已记录（内存）", extra={
            "stock_code": order.stock_code,
            "decision": decision,
            "rule_name": getattr(final, "rule_name", ""),
            "audit_log_total": len(self.audit_log),
        })
        _write_audit_entry(entry)


def _decision_to_dict(d: Any) -> dict[str, Any]:
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
    raw = getattr(final, "decision", None)
    decision = getattr(raw, "value", None) if raw is not None else None
    if decision is None:
        decision = str(raw or "")
    decision = decision.upper()
    logger.debug("计算交易建议", extra={
        "stock_code": order.stock_code if hasattr(order, "stock_code") else "?",
        "decision": decision,
        "amount": order.amount if hasattr(order, "amount") else 0,
    })
    if decision == "WARN":
        pct = float(final.max_position_pct or 0)
        amt = max(0.0, float(order.amount) * pct)
        qty = int(amt / float(order.price) / 100) * 100 if order.price > 0 else 0
        result = (int(round(qty * float(order.price))), qty)
        logger.info("交易建议计算完成（WARN降仓）", extra={
            "original_amount": int(round(order.amount)),
            "suggested_amount": result[0],
            "suggested_qty": result[1],
            "max_pct": pct,
        })
        return result
    if decision == "APPROVE":
        result = (int(round(order.amount)), int(order.quantity))
        logger.info("交易建议计算完成（APPROVE全量）", extra={
            "suggested_amount": result[0],
            "suggested_qty": result[1],
        })
        return result
    logger.info("交易建议计算结果为0（REJECT）")
    return 0, 0


def approve(payload: dict[str, Any]) -> dict[str, Any]:
    logger.info("风控审批请求受理", extra={
        "payload_keys": list(payload.keys()),
        "stock_code": (payload.get("order") or {}).get("stock_code"),
    })
    manager = _get_manager()
    order_in = payload.get("order") or {}
    portfolio_in = payload.get("portfolio") or {}
    context_in = payload.get("context") or {}
    order = Order(
        stock_code=str(order_in.get("stock_code") or ""),
        direction=str(order_in.get("direction") or "buy"),
        amount=float(order_in.get("amount") or 0),
        price=float(order_in.get("price") or 0),
        quantity=int(order_in.get("quantity") or 0),
    )
    portfolio = {
        "total_asset": float(portfolio_in.get("total_asset") or 0),
        "prices": dict(portfolio_in.get("prices") or {}),
        "atr": dict(portfolio_in.get("atr") or {}),
    }
    context = {"news_text": str(context_in.get("news_text") or "")}
    logger.info("风控审批参数解析完成", extra={
        "order": {"stock_code": order.stock_code, "direction": order.direction,
                   "amount": order.amount, "price": order.price, "quantity": order.quantity},
        "portfolio": {"total_asset": portfolio["total_asset"],
                       "prices_count": len(portfolio["prices"]),
                       "atr_count": len(portfolio["atr"])},
        "has_context": bool(context.get("news_text")),
    })
    final, checks = manager.approve_verbose(order, portfolio, context)
    suggested_amount, suggested_quantity = _calc_suggestion(order, final)
    base = _decision_to_dict(final)
    result = {
        **base,
        "suggested_amount": int(suggested_amount),
        "suggested_quantity": int(suggested_quantity),
        "checks": [_decision_to_dict(x) for x in checks],
    }
    logger.info("风控审批结果返回", extra={
        "decision": result.get("decision"),
        "reason": result.get("reason"),
        "checks_count": len(result["checks"]),
        "suggested_amount": result.get("suggested_amount"),
    })
    return result


def audit(last_n: int = 200) -> dict[str, Any]:
    logger.info("风控审计日志查询", extra={
        "last_n": last_n,
    })
    manager = _get_manager()
    n = max(1, min(int(last_n), 2000))
    result = {"items": list(manager.audit_log[-n:])}
    logger.info("风控审计日志查询完成", extra={
        "requested": last_n,
        "returned": len(result["items"]),
        "total_available": len(manager.audit_log),
    })
    return result


def status() -> dict[str, Any]:
    logger.info("风控服务状态查询")
    manager = _get_manager()
    result = manager.get_summary()
    logger.info("风控服务状态返回", extra={"status": result})
    return result
