# -*- coding: utf-8 -*-
"""
主力行为识别 - 数据结构定义

包含时间范围预设、主力类型常量等共享数据结构。
"""

from typing import Any

# 时间范围预设值：定义每个时间范围对应的分钟数据周期和特征窗口
TIME_RANGE_PRESETS: dict[str, dict[str, Any]] = {
    "today": {
        "label": "今日",
        "period": "1m",
        "window": 60,           # 特征计算窗口（60个1分钟K线）
        "min_bars": 20,         # 最少需要的数据条数
        "expected_bars": 240,   # 期望数据条数（完整交易日）
    },
    "yesterday": {
        "label": "昨日",
        "period": "1m",
        "window": 60,
        "min_bars": 20,
        "expected_bars": 240,   # 完整交易日约240根1分钟K线
    },
    "last_5_days": {
        "label": "近五日",
        "period": "1m",
        "window": 60,
        "min_bars": 100,
        "expected_bars": 1200,  # 5天 × 240根
    },
}

# 主力类型常量
TYPE_INSTITUTION = "institution"   # 机构主力
TYPE_HOT_MONEY = "hot_money"       # 游资
TYPE_RETAIL = "retail"             # 散户

# 主力类型中文名称映射
TYPE_LABELS = {
    "institution": "机构主力",
    "hot_money": "游资",
    "retail": "散户",
}
