# -*- coding: utf-8 -*-
"""
主力行为识别核心引擎模块

提供从 QMT 网关获取 1 分钟 K线数据，提取微观结构特征、
分类主力类型、生成交易信号等功能。
"""

from core.mainforce.engine import MainForceEngine

__all__ = ["MainForceEngine"]
