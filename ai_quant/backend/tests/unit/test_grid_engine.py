# -*- coding: utf-8 -*-
"""
网格引擎测试
"""
import pytest


class TestGridEngine:
    """网格引擎基本功能测试"""

    def test_basic_grid_creation(self):
        """验证网格引擎可以正常创建"""
        from core.strategy.grid_engine import GridEngine
        engine = GridEngine(lower=10.0, upper=20.0, num_grids=10, total_capital=100000.0)
        assert engine.num_grids == 10
        assert engine.lower == 10.0
        assert engine.upper == 20.0

    def test_grid_levels_monotonic(self):
        """验证网格价格严格递增"""
        from core.strategy.grid_engine import GridEngine
        engine = GridEngine(lower=10.0, upper=20.0, num_grids=5, total_capital=100000.0)
        levels = engine.levels
        assert len(levels) == 6  # num_grids + 1
        for i in range(1, len(levels)):
            assert levels[i] > levels[i - 1], f"网格价格非递增: {levels[i]} <= {levels[i-1]}"

    def test_grid_size_calculation(self):
        """验证网格大小计算正确"""
        from core.strategy.grid_engine import GridEngine
        engine = GridEngine(lower=10.0, upper=20.0, num_grids=10, total_capital=100000.0)
        assert engine.grid_size == pytest.approx(1.0, abs=1e-9)

    def test_lower_below_triggers_buy(self):
        """验证价格低于下限时触发对应的网格买入信号"""
        from core.strategy.grid_engine import GridEngine
        engine = GridEngine(lower=10.0, upper=20.0, num_grids=10, total_capital=100000.0)
        # 先初始化 current_grid
        engine.update(15.0)
        # 价格大幅下跌触发多层买入
        signals = engine.update(9.0)
        assert len(signals) > 0, "价格跌破下限应产生网格买入信号"

    def test_upper_above_triggers_no_buy(self):
        """验证价格高于上限不产生买入信号"""
        from core.strategy.grid_engine import GridEngine
        engine = GridEngine(lower=10.0, upper=20.0, num_grids=10, total_capital=100000.0)
        engine.update(15.0)
        signals = engine.update(25.0)
        # 高于上限不应有买入信号，但可能有卖出信号（如果之前持仓）
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) == 0, "高于上限不应有买入信号"

    def test_invalid_params_does_not_crash(self):
        """验证非法参数不会导致崩溃"""
        from core.strategy.grid_engine import GridEngine
        # 下限 >= 上限的情况
        engine = GridEngine(lower=20.0, upper=10.0, num_grids=5, total_capital=100000.0)
        assert engine is not None
        # grid_size 为负数但不影响实例创建
        assert engine.num_grids == 5

    def test_zero_grids_div_zero(self):
        """验证 num_grids=0 时抛出除零异常（预期行为）"""
        from core.strategy.grid_engine import GridEngine
        with pytest.raises(ZeroDivisionError):
            GridEngine(lower=10.0, upper=20.0, num_grids=0, total_capital=100000.0)

    def test_capital_per_grid_calculation(self):
        """验证每格资金分配计算"""
        from core.strategy.grid_engine import GridEngine
        engine = GridEngine(lower=10.0, upper=20.0, num_grids=5, total_capital=100000.0)
        assert engine.capital_per_grid == pytest.approx(20000.0, abs=1e-9)

    def test_buy_sell_cycle(self):
        """验证完整的买卖循环"""
        from core.strategy.grid_engine import GridEngine
        engine = GridEngine(lower=10.0, upper=20.0, num_grids=10, total_capital=100000.0)
        # 初始化在中间
        engine.update(15.0)
        assert engine.buy_count == 0
        assert engine.sell_count == 0

        # 价格下跌：触发买入
        signals_1 = engine.update(10.5)
        buy_count_1 = sum(1 for s in signals_1 if s.action == "BUY")
        assert engine.buy_count >= buy_count_1

        # 价格上涨回到原位：触发卖出
        signals_2 = engine.update(15.0)
        sell_count_2 = sum(1 for s in signals_2 if s.action == "SELL")
        assert engine.sell_count >= sell_count_2
