# -*- coding: utf-8 -*-
"""
策略注册中心测试
"""
import pytest


class TestStrategyRegistry:
    """策略注册中心基本验证"""

    def test_all_strategies_registered(self):
        """验证策略数量不少于最低预期"""
        from core.strategy.strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        assert len(registry) >= 20, f"注册策略数量不足: {len(registry)}"

    def test_all_strategies_have_required_fields(self):
        """验证每个策略都包含必要字段"""
        from core.strategy.strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        for sid, meta in registry.items():
            assert meta.strategy_id, f"{sid} 缺少 strategy_id"
            assert meta.name, f"{sid} 缺少 name"
            assert isinstance(meta.params_schema, dict), f"{sid} params_schema 不是 dict"
            assert isinstance(meta.default_params, dict), f"{sid} default_params 不是 dict"

    def test_default_params_match_schema_keys(self):
        """验证 default_params 中的 key 都在 params_schema 中定义"""
        from core.strategy.strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        for sid, meta in registry.items():
            schema_keys = set(meta.params_schema.keys())
            default_keys = set(meta.default_params.keys())
            extra = default_keys - schema_keys
            assert not extra, f"{sid} 的 default_params 包含未在 params_schema 中定义的键: {extra}"

    def test_all_strategies_have_factory(self):
        """验证每个策略都有 bt_strategy_factory"""
        from core.strategy.strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        for sid, meta in registry.items():
            assert meta.bt_strategy_factory is not None, f"{sid} 缺少 bt_strategy_factory"

    def test_group_values_valid(self):
        """验证策略分组值合法"""
        from core.strategy.strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        valid_groups = {"basic", "optimized", "combo"}
        for sid, meta in registry.items():
            assert meta.group in valid_groups, f"{sid} 的分组 '{meta.group}' 不在合法值 {valid_groups} 中"

    def test_group_distribution_coverage(self):
        """验证三个分组都有策略覆盖"""
        from core.strategy.strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        groups = set(meta.group for meta in registry.values())
        assert "basic" in groups, "缺少 basic 分组策略"
        assert "optimized" in groups, "缺少 optimized 分组策略"
        assert "combo" in groups, "缺少 combo 分组策略"
