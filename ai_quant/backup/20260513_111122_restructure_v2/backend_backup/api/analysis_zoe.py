from __future__ import annotations

import json
import os
import uuid
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from db import connect, load_mysql_config, query_dict
from modules.analysis import get_sample_codes, get_signals, get_status as get_analysis_status
from runtime.logging_service import get_logger
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])
logger = get_logger("analysis")


@router.get("/status")
def status() -> dict[str, Any]:
    return get_analysis_status()


@router.get("/stocks/sample")
def sample_stocks(limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    return get_sample_codes(limit)


@router.get("/signals")
def signals(stock_code: str = Query(...), start: str = Query(...), end: str = Query(...)) -> dict[str, Any]:
    return get_signals(stock_code=stock_code, start=start, end=end)


# ============== 策略元数据注册表 ==============

STRATEGIES: list[dict[str, Any]] = [
    {
        "strategy_id": "dual_ma",
        "name": "双均线交叉",
        "description": "快速均线与慢速均线交叉产生买卖信号。快速上穿慢速均线时买入，下穿时卖出。适用于趋势明显的市场，震荡市效果较差。",
        "pros": ["逻辑简单易理解", "趋势行情中收益可观", "参数少，易调优"],
        "cons": ["震荡市易产生频繁虚假信号", "趋势反转滞后", "无法识别趋势强度"],
        "params_schema": {
            "fast": {"type": "int", "label": "快速均线周期", "help": "快速均线的计算周期", "min": 3, "max": 60, "default": 10},
            "slow": {"type": "int", "label": "慢速均线周期", "help": "慢速均线的计算周期", "min": 10, "max": 200, "default": 30},
        },
        "default_params": {"fast": 10, "slow": 30},
    },
    {
        "strategy_id": "macd_basic",
        "name": "MACD基础",
        "description": "利用 DIF 与 DEA 的交叉判断买卖时机。DIF 上穿 DEA 形成金叉买入，下穿形成死叉卖出。MACD 是最经典的趋势指标之一。",
        "pros": ["指标经典，适用范围广", "可判断趋势方向与动能", "参数固定时效果稳定"],
        "cons": ["滞后性明显", "震荡市信号噪音大", "参数调节空间有限"],
        "params_schema": {
            "fast": {"type": "int", "label": "快线周期", "help": "EMA 快线周期", "min": 5, "max": 30, "default": 12},
            "slow": {"type": "int", "label": "慢线周期", "help": "EMA 慢线周期", "min": 15, "max": 60, "default": 26},
            "signal": {"type": "int", "label": "Signal周期", "help": "Signal 线平滑周期", "min": 5, "max": 30, "default": 9},
        },
        "default_params": {"fast": 12, "slow": 26, "signal": 9},
    },
    {
        "strategy_id": "rsi_basic",
        "name": "RSI超买超卖",
        "description": "RSI 低于超卖阈值时买入，高于超买阈值时卖出。适用于震荡市的区间交易，趋势市需配合其他指标。",
        "pros": ["超买超卖判断直观", "适合区间震荡行情", "信号明确"],
        "cons": ["趋势市易被套牢", "参数需根据市场调整", "横盘整理时信号较多"],
        "params_schema": {
            "period": {"type": "int", "label": "RSI周期", "help": "RSI 计算周期", "min": 5, "max": 30, "default": 14},
            "oversold": {"type": "int", "label": "超卖阈值", "help": "低于此值视为超卖", "min": 10, "max": 40, "default": 30},
            "overbought": {"type": "int", "label": "超买阈值", "help": "高于此值视为超买", "min": 60, "max": 90, "default": 70},
        },
        "default_params": {"period": 14, "oversold": 30, "overbought": 70},
    },
    {
        "strategy_id": "boll_basic",
        "name": "布林带策略",
        "description": "价格触及布林下轨时买入，触及上轨时卖出。布林带中轨可作为动态止损参考。适用于有规律波动的个股。",
        "pros": ["自带止损逻辑", "可量化波动区间", "趋势/震荡均适用"],
        "cons": ["单边趋势中持续持仓可能利润回吐", "参数敏感", "极端行情失效"],
        "params_schema": {
            "period": {"type": "int", "label": "布林周期", "help": "中轨计算周期", "min": 10, "max": 60, "default": 20},
            "devfactor": {"type": "float", "label": "标准差倍数", "help": "上下轨偏离倍数", "min": 1.0, "max": 4.0, "step": 0.1, "default": 2.0},
        },
        "default_params": {"period": 20, "devfactor": 2.0},
    },
    {
        "strategy_id": "bias",
        "name": "BIAS乖离率",
        "description": "计算价格与均线的偏离程度。偏离过大时产生均值回归力量，价格过负时买入，过正时卖出。适合波动较大的个股。",
        "pros": ["提前预判价格回归", "适合均值回归型交易", "逻辑清晰"],
        "cons": ["乖离阈值主观性强", "趋势强的股票可能持续偏离", "需配合市场环境判断"],
        "params_schema": {
            "period": {"type": "int", "label": "均线周期", "help": "基准均线周期", "min": 5, "max": 60, "default": 20},
            "buy_threshold": {"type": "float", "label": "买入乖离阈值", "help": "负向偏离多少时买入", "min": -20.0, "max": -0.5, "step": 0.1, "default": -6.0},
            "sell_threshold": {"type": "float", "label": "卖出乖离阈值", "help": "正向偏离多少时卖出", "min": 0.5, "max": 20.0, "step": 0.1, "default": 3.0},
        },
        "default_params": {"period": 20, "buy_threshold": -6.0, "sell_threshold": 3.0},
    },
    {
        "strategy_id": "momentum",
        "name": "动量策略",
        "description": "基于动量指标（ROC/变化率）判断短期涨跌趋势。动量持续为正时持有，转负时卖出。适合趋势跟踪型操作。",
        "pros": ["趋势跟随能力强", "参数简单", "在大趋势行情中表现优秀"],
        "cons": ["震荡市持续亏损", "滞后于价格变化", "无法预判趋势反转"],
        "params_schema": {
            "period": {"type": "int", "label": "动量周期", "help": "动量计算周期（天）", "min": 5, "max": 60, "default": 20},
            "threshold": {"type": "float", "label": "动量阈值", "help": "触发买入/卖出的动量临界值", "min": 0.5, "max": 20.0, "step": 0.5, "default": 5.0},
        },
        "default_params": {"period": 20, "threshold": 5.0},
    },
    {
        "strategy_id": "rsi_ma_confirm",
        "name": "RSI+MA交叉确认",
        "description": "RSI 超卖且均线黄金交叉时买入，RSI 超买或均线死叉时卖出。通过双重过滤减少假信号。",
        "pros": ["双重过滤降低假信号", "信号可靠性高", "趋势行情中稳定"],
        "cons": ["信号较少，机会成本高", "参数组合需仔细调优", "均线周期选择影响大"],
        "params_schema": {
            "period": {"type": "int", "label": "RSI周期", "help": "RSI 计算周期", "min": 5, "max": 30, "default": 14},
            "oversold": {"type": "int", "label": "超卖阈值", "help": "买入参考", "min": 10, "max": 40, "default": 30},
            "overbought": {"type": "int", "label": "超买阈值", "help": "卖出参考", "min": 60, "max": 90, "default": 70},
        },
        "default_params": {"period": 14, "oversold": 30, "overbought": 70},
    },
    {
        "strategy_id": "macd_vol_confirm",
        "name": "MACD+成交量确认",
        "description": "MACD 金叉且成交量放大时买入，死叉时卖出。成交量确认可过滤掉无量的虚假突破。",
        "pros": ["成交量过滤增强信号可靠性", "避免无量假突破", "适用于有流动性的股票"],
        "cons": ["需等待成交量确认，反应较慢", "无量市场信号稀少", "参数组合敏感"],
        "params_schema": {
            "fast": {"type": "int", "label": "快线周期", "help": "MACD 快线", "min": 5, "max": 30, "default": 12},
            "slow": {"type": "int", "label": "慢线周期", "help": "MACD 慢线", "min": 15, "max": 60, "default": 26},
            "signal": {"type": "int", "label": "Signal周期", "help": "MACD Signal", "min": 5, "max": 30, "default": 9},
            "vol_period": {"type": "int", "label": "成交量均线周期", "help": "判断成交量是否放大", "min": 5, "max": 60, "default": 20},
            "vol_mult": {"type": "float", "label": "成交量倍数", "help": "放量标准：超过均量的倍数", "min": 0.3, "max": 2.0, "step": 0.1, "default": 0.9},
        },
        "default_params": {"fast": 12, "slow": 26, "signal": 9, "vol_period": 20, "vol_mult": 0.9},
    },
    {
        "strategy_id": "macd_profit_lock",
        "name": "MACD+浮动止盈",
        "description": "MACD 金叉买入，死叉平仓；持仓期间利润达到触发条件后启动移动止损保护利润。兼顾趋势跟踪与利润保护。",
        "pros": ["趋势跟踪能力强", "浮动止损保护利润", "可避免利润大幅回吐"],
        "cons": ["浮动止盈参数主观性强", "震荡市持续止损", "触发条件复杂"],
        "params_schema": {
            "fast": {"type": "int", "label": "快线周期", "help": "MACD 快线", "min": 5, "max": 30, "default": 12},
            "slow": {"type": "int", "label": "慢线周期", "help": "MACD 慢线", "min": 15, "max": 60, "default": 26},
            "signal": {"type": "int", "label": "Signal周期", "help": "MACD Signal", "min": 5, "max": 30, "default": 9},
            "profit_trigger": {"type": "float", "label": "止盈触发（%）", "help": "利润达到多少时启动移动止损", "min": 1.0, "max": 30.0, "step": 0.5, "default": 5.0},
            "trail_pct": {"type": "float", "label": "移动止损回撤（%）", "help": "从峰值回落多少时触发止盈", "min": 1.0, "max": 20.0, "step": 0.5, "default": 3.0},
        },
        "default_params": {"fast": 12, "slow": 26, "signal": 9, "profit_trigger": 5.0, "trail_pct": 3.0},
    },
    {
        "strategy_id": "boll_mid_stop",
        "name": "布林中轨止损",
        "description": "价格触及布林下轨买入，触及布林中轨时卖出（动态止盈），触及上轨时强制平仓。止损逻辑清晰。",
        "pros": ["中轨提供动态止盈参考", "止损明确", "参数直观"],
        "cons": ["趋势市中轨止盈过早", "单边行情利润有限", "参数选择影响大"],
        "params_schema": {
            "period": {"type": "int", "label": "布林周期", "help": "布林中轨计算周期", "min": 10, "max": 60, "default": 20},
            "devfactor": {"type": "float", "label": "标准差倍数", "help": "上下轨偏离倍数", "min": 1.0, "max": 4.0, "step": 0.1, "default": 2.0},
        },
        "default_params": {"period": 20, "devfactor": 2.0},
    },
    {
        "strategy_id": "grid",
        "name": "网格交易",
        "description": "在固定价格区间内等距布单，高抛低吸。适合震荡行情，无需预判方向，长期稳健收益。",
        "pros": ["无需预判方向", "震荡市收益稳定", "逻辑清晰易实现"],
        "cons": ["趋势市可能爆仓", "资金利用率低", "需合理设置网格密度和上下限"],
        "params_schema": {
            "grid_count": {"type": "int", "label": "网格数量", "help": "上下限之间布多少个网格", "min": 3, "max": 20, "default": 10},
            "position_pct": {"type": "float", "label": "每格仓位比例（%）", "help": "每格占总资金的比例", "min": 5, "max": 30, "step": 1.0, "default": 10.0},
            "upper_price": {"type": "float", "label": "上限价格", "help": "网格上限价格", "min": 0, "max": 100000, "default": 100.0},
            "lower_price": {"type": "float", "label": "下限价格", "help": "网格下限价格", "min": 0, "max": 100000, "default": 50.0},
        },
        "default_params": {"grid_count": 10, "position_pct": 10.0, "upper_price": 100.0, "lower_price": 50.0},
    },
    {
        "strategy_id": "grid_martingale",
        "name": "马丁格尔网格",
        "description": "在标准网格基础上，每次买入仓位加倍（亏损加仓），回到初始基准价时全部平仓获利。适合长周期低波动品种。",
        "pros": ["回本概率高", "长周期稳健", "无需精准抄底"],
        "cons": ["单边趋势可能爆仓", "资金需求大", "心理压力大"],
        "params_schema": {
            "grid_count": {"type": "int", "label": "网格数量", "help": "网格数量", "min": 3, "max": 20, "default": 10},
            "base_position": {"type": "float", "label": "基础仓位数量", "help": "第一格的买入数量", "min": 100, "max": 100000, "default": 1000.0},
            "multiplier": {"type": "float", "label": "仓位倍数", "help": "每次加仓的仓位倍数", "min": 1.5, "max": 3.0, "step": 0.1, "default": 2.0},
        },
        "default_params": {"grid_count": 10, "base_position": 1000.0, "multiplier": 2.0},
    },
    {
        "strategy_id": "turtle",
        "name": "经典海龟交易",
        "description": "基于唐安奇通道突破规则。价格突破20日高点买入，跌破10日低点卖出。经典的趋势跟踪系统。",
        "pros": ["经典趋势跟踪系统", "参数少", "经过长期市场验证"],
        "cons": ["趋势反转时滞后", "震荡市频繁止损", "趋势反转假突破多"],
        "params_schema": {
            "entry_period": {"type": "int", "label": "入场周期", "help": "入场通道计算周期（天）", "min": 10, "max": 60, "default": 20},
            "exit_period": {"type": "int", "label": "出场周期", "help": "出场通道计算周期（天）", "min": 5, "max": 30, "default": 10},
            "atr_period": {"type": "int", "label": "ATR周期", "help": "计算真实波幅的周期", "min": 5, "max": 30, "default": 20},
            "risk_per_trade": {"type": "float", "label": "每笔风险（%）", "help": "每笔交易占总资金的比例", "min": 0.5, "max": 5.0, "step": 0.1, "default": 2.0},
        },
        "default_params": {"entry_period": 20, "exit_period": 10, "atr_period": 20, "risk_per_trade": 2.0},
    },
    {
        "strategy_id": "turtle_short",
        "name": "海龟做空",
        "description": "与海龟做多对称，价格跌破20日低点做空，涨回10日高点平仓。做空市场下跌行情。",
        "pros": ["下跌行情中盈利", "与做多策略互补", "趋势信号明确"],
        "cons": ["做空成本高（利息）", "单边上涨风险大", "需配合做多策略使用"],
        "params_schema": {
            "entry_period": {"type": "int", "label": "入场周期", "help": "做空入场通道", "min": 10, "max": 60, "default": 20},
            "exit_period": {"type": "int", "label": "出场周期", "help": "平仓通道", "min": 5, "max": 30, "default": 10},
        },
        "default_params": {"entry_period": 20, "exit_period": 10},
    },
    {
        "strategy_id": "kdj",
        "name": "KDJ随机指标",
        "description": "利用随机指标判断超买超卖。金叉（K上穿D）且在低位时买入，死叉且在高位时卖出。适合短线交易。",
        "pros": ["对价格变化敏感", "适合短线操作", "超买超卖信号明确"],
        "cons": ["噪音多，假信号多", "不适合长线持仓", "需结合其他指标过滤"],
        "params_schema": {
            "n": {"type": "int", "label": "RSV周期", "help": "计算RSV的周期", "min": 5, "max": 30, "default": 9},
            "k_period": {"type": "int", "label": "K线平滑周期", "help": "K值的平滑周期", "min": 1, "max": 10, "default": 3},
            "d_period": {"type": "int", "label": "D线平滑周期", "help": "D值的平滑周期", "min": 1, "max": 10, "default": 3},
        },
        "default_params": {"n": 9, "k_period": 3, "d_period": 3},
    },
    {
        "strategy_id": "kdj_macd_combo",
        "name": "KDJ+MACD组合",
        "description": "KDJ 和 MACD 同时发出同向信号时才操作，过滤假信号。KDJ 确认方向，MACD 确认趋势。",
        "pros": ["双重过滤，假信号少", "信号可靠性高", "趋势确认能力强"],
        "cons": ["信号稀少", "趋势初期入场滞后", "参数组合多，调优复杂"],
        "params_schema": {
            "kdj_n": {"type": "int", "label": "KDJ RSV周期", "help": "KDJ RSV计算周期", "min": 5, "max": 30, "default": 9},
            "macd_fast": {"type": "int", "label": "MACD快线", "help": "MACD 快线周期", "min": 5, "max": 30, "default": 12},
            "macd_slow": {"type": "int", "label": "MACD慢线", "help": "MACD 慢线周期", "min": 15, "max": 60, "default": 26},
            "macd_signal": {"type": "int", "label": "MACD Signal", "help": "MACD Signal周期", "min": 5, "max": 30, "default": 9},
        },
        "default_params": {"kdj_n": 9, "macd_fast": 12, "macd_slow": 26, "macd_signal": 9},
    },
    {
        "strategy_id": "sar_follow",
        "name": "SAR趋势跟随",
        "description": "抛物线转向指标（SAR）跟踪趋势。SAR 在价格下方时持有多仓，在价格上方时持有空仓或空仓。自动追踪止损。",
        "pros": ["自动提供止损位", "趋势跟随清晰", "无需主观判断趋势"],
        "cons": ["横盘震荡时频繁转向", "趋势初期信号不稳定", "参数需根据波动性调整"],
        "params_schema": {
            "af_step": {"type": "float", "label": "加速因子步长", "help": "SAR 加速因子每次增加量", "min": 0.01, "max": 0.1, "step": 0.005, "default": 0.02},
            "af_max": {"type": "float", "label": "加速因子上限", "help": "SAR 加速因子最大值", "min": 0.1, "max": 0.5, "step": 0.05, "default": 0.2},
        },
        "default_params": {"af_step": 0.02, "af_max": 0.2},
    },
    {
        "strategy_id": "tide",
        "name": "顺势指标（CCI）",
        "description": "利用 CCI 顺势指标判断超买超卖和趋势。CCI 突破 +100 做多，跌破 -100 平仓并做空。适用于趋势明显的商品和指数。",
        "pros": ["适合商品期货", "趋势信号明确", "参数简单"],
        "cons": ["震荡市失效", "滞后性明显", "期货专用（需注意做空成本）"],
        "params_schema": {
            "period": {"type": "int", "label": "CCI周期", "help": "CCI 计算周期", "min": 5, "max": 30, "default": 14},
            "buy_level": {"type": "float", "label": "买入水平", "help": "CCI 超过此值做多", "min": 50, "max": 200, "step": 10, "default": 100.0},
            "sell_level": {"type": "float", "label": "卖出水平", "help": "CCI 跌破此值做空", "min": -200, "max": -50, "step": 10, "default": -100.0},
        },
        "default_params": {"period": 14, "buy_level": 100.0, "sell_level": -100.0},
    },
    {
        "strategy_id": "dmi_adx",
        "name": "DMI+ADX趋势强度",
        "description": "DMI 判断方向，ADX 判断趋势强度。ADX 上升且 +DI > -DI 时做多，ADX 下降或 -DI > +DI 时平仓。",
        "pros": ["ADX 可判断是否有趋势", "避免在震荡市交易", "方向判断准确"],
        "cons": ["ADX 需达到一定水平才有效", "信号产生较慢", "参数需结合市场调整"],
        "params_schema": {
            "period": {"type": "int", "label": "DMI/ADX周期", "help": "计算周期", "min": 7, "max": 30, "default": 14},
            "adx_threshold": {"type": "float", "label": "ADX阈值", "help": "认为有趋势的最低ADX值", "min": 10, "max": 40, "step": 1, "default": 25.0},
        },
        "default_params": {"period": 14, "adx_threshold": 25.0},
    },
    {
        "strategy_id": "ddi",
        "name": "DDY涨跌意愿",
        "description": "基于涨跌意愿指标（DDY），反映主动买卖力量。DDY 为正且上升时买入，为负且下降时卖出。",
        "pros": ["捕捉主力动向", "适合中短线", "数据来源直接"],
        "cons": ["需Level2数据支持", "短期噪音大", "需结合价格一起看"],
        "params_schema": {
            "period": {"type": "int", "label": "DDY均线周期", "help": "DDY 平滑周期", "min": 3, "max": 20, "default": 5},
            "threshold": {"type": "float", "label": "触发阈值", "help": "DDY 超过此值触发信号", "min": 0.1, "max": 10.0, "step": 0.1, "default": 1.0},
        },
        "default_params": {"period": 5, "threshold": 1.0},
    },
]


# ============== 实例存储路径 ==============

def _instances_path() -> Path:
    base = Path(__file__).parent.parent.parent.parent
    p = base / ".ai_quant" / "strategy_instances.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_instances() -> list[dict[str, Any]]:
    p = _instances_path()
    if not p.exists():
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f) or []
    except Exception:
        return []


def _save_instances(instances: list[dict[str, Any]]) -> None:
    p = _instances_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(instances, f, ensure_ascii=False, indent=2)


# ============== 数据加载 ==============

def _load_daily(stock_code: str, start: str, end: str) -> pd.DataFrame:
    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception:
        return pd.DataFrame()
    try:
        rows = query_dict(
            conn,
            """
            SELECT trade_date, open, high, low, close, volume, amount, stock_name
            FROM trade_stock_daily
            WHERE stock_code = %s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
            """,
            (stock_code, start, end),
        )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for col in ["open", "high", "low", "close", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df
    finally:
        conn.close()


# ============== 简化回测引擎 ==============

def _run_simple_backtest(
    df: pd.DataFrame,
    strategy_id: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    df = df.copy().reset_index(drop=True)
    close = df["close"].values
    n = len(close)
    cash = 100000.0
    position = 0
    trades: list[dict[str, Any]] = []
    equity: list[dict[str, Any]] = []

    p = params.copy()
    price_arr = close

    for i in range(1, n):
        date_str = str(df.iloc[i]["trade_date"].date())
        current_price = price_arr[i]
        signal = ""

        if strategy_id == "dual_ma":
            fast = int(p.get("fast", 10))
            slow = int(p.get("slow", 30))
            if i < slow:
                equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
                continue
            ma_fast_curr = price_arr[i - fast + 1:i + 1].mean() if i >= fast else None
            ma_slow_curr = price_arr[i - slow + 1:i + 1].mean() if i >= slow else None
            ma_fast_prev = price_arr[i - fast:i].mean() if i >= fast else None
            ma_slow_prev = price_arr[i - slow:i].mean() if i >= slow else None
            if ma_fast_curr is not None and ma_slow_curr is not None and ma_fast_prev is not None and ma_slow_prev is not None:
                if ma_fast_prev <= ma_slow_prev and ma_fast_curr > ma_slow_curr and not position:
                    position = int(cash * 0.95 / current_price)
                    cost = position * current_price
                    cash -= cost
                    trades.append({"date": date_str, "action": "buy", "price": round(current_price, 2), "qty": position, "cost": round(cost, 2)})
                    signal = "买入"
                elif ma_fast_prev >= ma_slow_prev and ma_fast_curr < ma_slow_curr and position > 0:
                    proceeds = position * current_price
                    cash += proceeds
                    trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                    position = 0
                    signal = "卖出"

        elif strategy_id == "macd_basic":
            fast, slow_s, sig = int(p.get("fast", 12)), int(p.get("slow", 26)), int(p.get("signal", 9))
            if i < slow_s + sig:
                equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
                continue
            ema_fast = pd.Series(price_arr[:i + 1]).ewm(span=fast, adjust=False).mean().iloc[-1]
            ema_slow = pd.Series(price_arr[:i + 1]).ewm(span=slow_s, adjust=False).mean().iloc[-1]
            dif_curr = ema_fast - ema_slow
            ema_dif_prev = pd.Series(price_arr[:i]).ewm(span=sig, adjust=False).mean().ewm(span=sig, adjust=False).mean().iloc[-1] if i > sig else 0
            dif_prev = pd.Series(price_arr[:i]).ewm(span=fast, adjust=False).mean().ewm(span=slow_s, adjust=False).mean().ewm(span=sig, adjust=False).mean().iloc[-1] if i > sig else 0
            if dif_prev <= 0 and dif_curr > 0 and not position:
                position = int(cash * 0.95 / current_price)
                cost = position * current_price
                cash -= cost
                trades.append({"date": date_str, "action": "buy", "price": round(current_price, 2), "qty": position, "cost": round(cost, 2)})
                signal = "买入"
            elif dif_prev >= 0 and dif_curr < 0 and position > 0:
                proceeds = position * current_price
                cash += proceeds
                trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                position = 0
                signal = "卖出"

        elif strategy_id == "rsi_basic":
            period = int(p.get("period", 14))
            oversold = float(p.get("oversold", 30))
            overbought = float(p.get("overbought", 70))
            if i < period:
                equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
                continue
            gains = []
            losses = []
            for j in range(i - period + 1, i + 1):
                delta = price_arr[j] - price_arr[j - 1]
                gains.append(max(delta, 0))
                losses.append(max(-delta, 0))
            avg_gain = sum(gains) / period
            avg_loss = sum(losses) / period
            rs = avg_gain / avg_loss if avg_loss != 0 else 100
            rsi = 100 - (100 / (1 + rs)) if rs != 0 else 50
            if rsi < oversold and not position:
                position = int(cash * 0.95 / current_price)
                cost = position * current_price
                cash -= cost
                trades.append({"date": date_str, "action": "buy", "price": round(current_price, 2), "qty": position, "cost": round(cost, 2)})
                signal = "买入"
            elif rsi > overbought and position > 0:
                proceeds = position * current_price
                cash += proceeds
                trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                position = 0
                signal = "卖出"

        elif strategy_id == "boll_basic":
            period = int(p.get("period", 20))
            dev = float(p.get("devfactor", 2.0))
            if i < period:
                equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
                continue
            mean = price_arr[i - period + 1:i + 1].mean()
            std = price_arr[i - period + 1:i + 1].std(ddof=0)
            upper = mean + dev * std
            lower = mean - dev * std
            if current_price <= lower and not position:
                position = int(cash * 0.95 / current_price)
                cost = position * current_price
                cash -= cost
                trades.append({"date": date_str, "action": "buy", "price": round(current_price, 2), "qty": position, "cost": round(cost, 2)})
                signal = "买入"
            elif current_price >= upper and position > 0:
                proceeds = position * current_price
                cash += proceeds
                trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                position = 0
                signal = "卖出"

        elif strategy_id == "kdj":
            n_kdj = int(p.get("n", 9))
            k_p = int(p.get("k_period", 3))
            d_p = int(p.get("d_period", 3))
            if i < n_kdj:
                equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
                continue
            window = price_arr[i - n_kdj + 1:i + 1]
            low_n = window.min()
            high_n = window.max()
            rsv = (current_price - low_n) / (high_n - low_n) * 100 if high_n != low_n else 50
            k = (2 / 3) * 50 + (1 / 3) * rsv
            d = (2 / 3) * 50 + (1 / 3) * k
            if k > d and k < 30 and not position:
                position = int(cash * 0.95 / current_price)
                cost = position * current_price
                cash -= cost
                trades.append({"date": date_str, "action": "buy", "price": round(current_price, 2), "qty": position, "cost": round(cost, 2)})
                signal = "买入"
            elif k < d and k > 70 and position > 0:
                proceeds = position * current_price
                cash += proceeds
                trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                position = 0
                signal = "卖出"

        elif strategy_id == "grid":
            grid_count = int(p.get("grid_count", 10))
            upper = float(p.get("upper_price", current_price * 1.1))
            lower = float(p.get("lower_price", current_price * 0.9))
            grid_step = (upper - lower) / grid_count
            current_price = float(current_price)
            if lower <= current_price <= upper:
                grid_idx = int((current_price - lower) / grid_step)
                grid_idx = max(0, min(grid_count - 1, grid_idx))
                if not position:
                    position = int(cash * 0.95 / current_price)
                    cost = position * current_price
                    cash -= cost
                    trades.append({"date": date_str, "action": "buy", "price": round(current_price, 2), "qty": position, "cost": round(cost, 2), "note": f"网格{grid_idx}"})
                    signal = "买入"
            else:
                if position > 0:
                    proceeds = position * current_price
                    cash += proceeds
                    trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                    position = 0
                    signal = "卖出"

        elif strategy_id == "momentum":
            period = int(p.get("period", 20))
            threshold = float(p.get("threshold", 5.0))
            if i < period:
                equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
                continue
            roc = (current_price - price_arr[i - period]) / price_arr[i - period] * 100
            if roc > threshold and not position:
                position = int(cash * 0.95 / current_price)
                cost = position * current_price
                cash -= cost
                trades.append({"date": date_str, "action": "buy", "price": round(current_price, 2), "qty": position, "cost": round(cost, 2)})
                signal = "买入"
            elif roc < -threshold and position > 0:
                proceeds = position * current_price
                cash += proceeds
                trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                position = 0
                signal = "卖出"

        elif strategy_id == "sar_follow":
            af_step = float(p.get("af_step", 0.02))
            af_max = float(p.get("af_max", 0.2))
            if i < 2:
                equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
                continue
            is_long = p.get("_sar_long", True)
            sar = p.get("_sar", current_price * 0.99)
            af = p.get("_af", af_step)
            ep = p.get("_ep", price_arr[i - 1])
            low_prev = price_arr[i - 1]
            high_prev = price_arr[i - 1]
            for j in range(max(0, i - 20), i):
                if price_arr[j] < low_prev:
                    low_prev = price_arr[j]
                if price_arr[j] > high_prev:
                    high_prev = price_arr[j]
            new_sar = sar + af * (ep - sar)
            new_sar = min(new_sar, price_arr[i - 1], price_arr[i - 2] if i >= 2 else price_arr[i - 1])
            if current_price > new_sar:
                if not is_long and position > 0:
                    proceeds = position * current_price
                    cash += proceeds
                    trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                    position = 0
                    signal = "平仓"
                is_long = True
                ep = high_prev
                af = min(af + af_step, af_max)
            else:
                if is_long and position > 0:
                    proceeds = position * current_price
                    cash += proceeds
                    trades.append({"date": date_str, "action": "sell", "price": round(current_price, 2), "qty": position, "proceeds": round(proceeds, 2)})
                    position = 0
                    signal = "平仓"
                is_long = False
                ep = low_prev
                af = min(af + af_step, af_max)
            p["_sar_long"] = is_long
            p["_sar"] = new_sar
            p["_af"] = af
            p["_ep"] = ep

        else:
            equity.append({"date": date_str, "nav": round(cash + position * current_price, 2)})
            continue

        nav = cash + position * current_price
        equity.append({"date": date_str, "nav": round(nav, 2)})

    final_nav = cash + position * close[-1]
    initial_nav = 100000.0
    total_return = (final_nav - initial_nav) / initial_nav * 100
    num_trades = len([t for t in trades if t["action"] == "buy"])
    wins = sum(1 for i in range(len(trades) - 1) if trades[i]["action"] == "buy" and i + 1 < len(trades) and trades[i + 1]["action"] == "sell" for _ in [1] if (trades[i + 1].get("proceeds", 0) or 0) > trades[i].get("cost", 0))
    win_rate = wins / num_trades * 100 if num_trades > 0 else 0

    return {
        "metrics": {
            "initial_nav": round(initial_nav, 2),
            "final_nav": round(final_nav, 2),
            "total_return": round(total_return, 2),
            "num_trades": num_trades,
            "win_rate": round(win_rate, 2),
        },
        "trades": trades,
        "nav_log": equity,
        "strategy_id": strategy_id,
        "stock_code": df.iloc[0]["stock_code"] if "stock_code" in df.columns else "",
        "start_date": str(df.iloc[0]["trade_date"].date()) if len(df) > 0 else "",
        "end_date": str(df.iloc[-1]["trade_date"].date()) if len(df) > 0 else "",
    }


# ============== 请求模型 ==============

class InstanceCreateReq(BaseModel):
    strategy_id: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)


class BacktestReq(BaseModel):
    stock_code: str
    start: str
    end: str
    strategy_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    initial_cash: float = 100000.0


# ============== API 路由 ==============

@router.get("/strategies")
def list_strategies() -> dict[str, Any]:
    return {"strategies": STRATEGIES}


@router.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str) -> dict[str, Any]:
    for s in STRATEGIES:
        if s["strategy_id"] == strategy_id:
            return {"strategy": s}
    raise HTTPException(status_code=404, detail="strategy_not_found")


@router.get("/strategy-instances")
def list_instances(strategy_id: str | None = Query(default=None)) -> dict[str, Any]:
    instances = _load_instances()
    if strategy_id:
        instances = [x for x in instances if x.get("strategy_id") == strategy_id]
    return {"instances": instances}


@router.post("/strategy-instances")
def create_instance(req: InstanceCreateReq = Body(...)) -> dict[str, Any]:
    for s in STRATEGIES:
        if s["strategy_id"] == req.strategy_id:
            break
    else:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="empty_name")

    defaults = {}
    for s in STRATEGIES:
        if s["strategy_id"] == req.strategy_id:
            defaults = dict(s.get("default_params", {}))
            break
    params = {**defaults, **req.params}

    instances = _load_instances()
    next_id = str(uuid.uuid4())[:8]
    instances.append({
        "instance_id": next_id,
        "strategy_id": req.strategy_id,
        "name": name,
        "params": params,
    })
    _save_instances(instances)
    return {"instance_id": next_id}


@router.delete("/strategy-instances/{instance_id}")
def delete_instance(instance_id: str) -> dict[str, Any]:
    instances = _load_instances()
    before = len(instances)
    instances = [x for x in instances if x.get("instance_id") != instance_id]
    _save_instances(instances)
    return {"deleted": instance_id, "removed": before - len(instances)}


@router.post("/backtest/run")
def run_backtest(req: BacktestReq = Body(...)) -> dict[str, Any]:
    try:
        start_d = pd.to_datetime(req.start).date()
        end_d = pd.to_datetime(req.end).date()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_date")

    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start_after_end")

    for s in STRATEGIES:
        if s["strategy_id"] == req.strategy_id:
            break
    else:
        raise HTTPException(status_code=400, detail="unknown_strategy")

    df = _load_daily(req.stock_code, str(start_d), str(end_d))
    if df.empty:
        raise HTTPException(status_code=404, detail="no_data_for_stock")

    defaults = {}
    for s in STRATEGIES:
        if s["strategy_id"] == req.strategy_id:
            defaults = dict(s.get("default_params", {}))
            break
    params = {**defaults, **req.params}

    result = _run_simple_backtest(df, req.strategy_id, params)
    return result


@router.get("/backtest/history")
def backtest_history(
    stock_code: str | None = Query(default=None),
    strategy_id: str | None = Query(default=None),
) -> dict[str, Any]:
    history_path = Path(__file__).parent.parent.parent.parent / ".ai_quant" / "backtest_history.json"
    if not history_path.exists():
        return {"items": []}
    try:
        with open(history_path, "r", encoding="utf-8") as f:
            items = json.load(f) or []
    except Exception:
        items = []
    if stock_code:
        items = [x for x in items if x.get("stock_code") == stock_code]
    if strategy_id:
        items = [x for x in items if x.get("strategy_id") == strategy_id]
    return {"items": items}
