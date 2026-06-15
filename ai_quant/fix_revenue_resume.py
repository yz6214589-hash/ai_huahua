#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
营收增速断点续传补采脚本
支持从中断点继续，避免重复采集
"""

import time
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.db import MySQLConfig, connect, query_dict


def _log(msg: str):
    """打印带时间戳的日志"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [revenue_resume] {msg}")


def _safe_value(val) -> Optional[float]:
    """安全转换值"""
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf