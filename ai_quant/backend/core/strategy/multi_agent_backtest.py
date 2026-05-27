from __future__ import annotations

import concurrent.futures
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from queue import Queue
from threading import Event, Lock
from typing import Any, Callable

import pandas as pd

from core.strategy.backtest_engine import run_backtest
from infra.storage.logging_service import get_logger

logger = get_logger("multi_agent_backtest")


class BacktestTaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BacktestTask:
    task_id: str
    stock_code: str
    strategy_id: str
    strategy_cls: Any
    strategy_params: dict[str, Any]
    initial_cash: float
    start_date: str
    end_date: str
    # 新增：交易成本配置字段
    commission_buy: float = 0.0003
    commission_sell: float = 0.0013
    slippage_pct: float = 0.0
    slippage_fixed: float = 0.0
    min_commission: float = 5.0
    status: BacktestTaskStatus = BacktestTaskStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class BatchBacktestResult:
    batch_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    results: list[BacktestTask]
    aggregated_metrics: dict[str, Any]
    created_at: str
    completed_at: str | None = None


class DataLoaderAgent:
    """数据加载智能体：负责批量加载多只股票的数据"""

    def __init__(self, load_func: Callable[[str, str, str], pd.DataFrame]):
        self.load_func = load_func
        self.cache: dict[str, pd.DataFrame] = {}
        self._lock = Lock()

    def load_data(self, stock_code: str, start: str, end: str) -> pd.DataFrame | None:
        cache_key = f"{stock_code}:{start}:{end}"
        with self._lock:
            if cache_key in self.cache:
                return self.cache[cache_key].copy()

        try:
            df = self.load_func(stock_code, start, end)
            if not df.empty:
                with self._lock:
                    self.cache[cache_key] = df.copy()
                return df
            else:
                logger.warning(
                    "数据加载返回空结果",
                    extra={"stock_code": stock_code, "start": start, "end": end}
                )
        except Exception as e:
            logger.error(
                "数据加载失败",
                extra={"stock_code": stock_code, "error": str(e), "error_type": type(e).__name__}
            )
        return None


class BacktestExecutorAgent:
    """回测执行智能体：负责单只股票的策略回测"""

    def __init__(self, task: BacktestTask, data_agent: DataLoaderAgent):
        self.task = task
        self.data_agent = data_agent

    def execute(self) -> BacktestTask:
        self.task.status = BacktestTaskStatus.RUNNING
        self.task.started_at = datetime.now().isoformat()
        logger.info("开始执行回测", extra={"task_id": self.task.task_id, "stock_code": self.task.stock_code})

        try:
            df = self.data_agent.load_data(self.task.stock_code, self.task.start_date, self.task.end_date)
            if df is None or df.empty:
                self.task.status = BacktestTaskStatus.FAILED
                self.task.error = "无可用数据"
                return self.task

            bt_result = run_backtest(
                df=df,
                strategy_cls=self.task.strategy_cls,
                strategy_params=self.task.strategy_params,
                initial_cash=self.task.initial_cash,
                # 传递交易成本参数
                commission_buy=self.task.commission_buy,
                commission_sell=self.task.commission_sell,
                slippage_pct=self.task.slippage_pct,
                slippage_fixed=self.task.slippage_fixed,
                min_commission=self.task.min_commission,
            )

            if "error" in bt_result.metrics:
                self.task.status = BacktestTaskStatus.FAILED
                self.task.error = bt_result.metrics["error"]
                return self.task

            self.task.result = bt_result
            self.task.status = BacktestTaskStatus.COMPLETED
            logger.info("回测完成", extra={"task_id": self.task.task_id, "stock_code": self.task.stock_code})

        except Exception as e:
            self.task.status = BacktestTaskStatus.FAILED
            self.task.error = str(e)
            logger.error("回测执行异常", extra={"task_id": self.task.task_id, "error": str(e)})

        finally:
            self.task.completed_at = datetime.now().isoformat()

        return self.task


class AggregatorAgent:
    """结果聚合智能体：负责将多只股票的回测结果进行聚合分析"""

    def __init__(self, results: list[BacktestTask]):
        self.results = results
        self.success_tasks = [r for r in results if r.status == BacktestTaskStatus.COMPLETED]

    def aggregate(self) -> dict[str, Any]:
        if not self.success_tasks:
            return {
                "avg_total_return": 0.0,
                "avg_annual_return": 0.0,
                "avg_max_drawdown": 0.0,
                "avg_sharpe": 0.0,
                "avg_win_rate": 0.0,
                "total_trades": 0,
                "win_stocks": 0,
                "total_stocks": len(self.results),
                "best_stock": None,
                "worst_stock": None,
            }

        total_returns = []
        annual_returns = []
        max_drawdowns = []
        sharpes = []
        win_rates = []
        total_trades = 0
        win_stocks = 0
        best_stock = None
        worst_stock = None
        max_return = -float("inf")
        min_return = float("inf")

        for task in self.success_tasks:
            metrics = task.result.metrics
            tr = metrics.get("total_return", 0.0)
            ar = metrics.get("annual_return", 0.0)
            md = metrics.get("max_drawdown", 0.0)
            sh = metrics.get("sharpe", 0.0)
            wr = metrics.get("win_rate", 0.0)
            tt = metrics.get("total_trades", 0)

            total_returns.append(tr)
            annual_returns.append(ar)
            max_drawdowns.append(md)
            if isinstance(sh, (int, float)) and not pd.isna(sh):
                sharpes.append(sh)
            win_rates.append(wr)
            total_trades += tt

            if tr > 0:
                win_stocks += 1

            if tr > max_return:
                max_return = tr
                best_stock = {"code": task.stock_code, "return": tr}

            if tr < min_return:
                min_return = tr
                worst_stock = {"code": task.stock_code, "return": tr}

        n = len(self.success_tasks)
        return {
            "avg_total_return": sum(total_returns) / n if n > 0 else 0.0,
            "avg_annual_return": sum(annual_returns) / n if n > 0 else 0.0,
            "avg_max_drawdown": sum(max_drawdowns) / n if n > 0 else 0.0,
            "avg_sharpe": sum(sharpes) / len(sharpes) if len(sharpes) > 0 else 0.0,
            "avg_win_rate": sum(win_rates) / n if n > 0 else 0.0,
            "total_trades": total_trades,
            "win_stocks": win_stocks,
            "total_stocks": len(self.results),
            "best_stock": best_stock,
            "worst_stock": worst_stock,
        }


class MultiAgentBacktestEngine:
    """多智能体协作回测引擎主控制器"""

    def __init__(
        self,
        load_data_func: Callable[[str, str, str], pd.DataFrame],
        max_workers: int = 4,
    ):
        self.data_loader = DataLoaderAgent(load_data_func)
        self.max_workers = max_workers
        self._batch_cache: dict[str, BatchBacktestResult] = {}

    def create_batch(
        self,
        stock_codes: list[str],
        strategy_id: str,
        strategy_cls: Any,
        strategy_params: dict[str, Any],
        initial_cash: float,
        start_date: str,
        end_date: str,
        # 新增：交易成本配置参数
        commission_buy: float = 0.0003,
        commission_sell: float = 0.0013,
        slippage_pct: float = 0.0,
        slippage_fixed: float = 0.0,
        min_commission: float = 5.0,
    ) -> BatchBacktestResult:
        batch_id = str(uuid.uuid4())[:8]

        tasks = []
        for code in stock_codes:
            task_id = str(uuid.uuid4())[:8]
            task = BacktestTask(
                task_id=task_id,
                stock_code=code,
                strategy_id=strategy_id,
                strategy_cls=strategy_cls,
                strategy_params=strategy_params,
                initial_cash=initial_cash,
                start_date=start_date,
                end_date=end_date,
                # 传递成本配置
                commission_buy=commission_buy,
                commission_sell=commission_sell,
                slippage_pct=slippage_pct,
                slippage_fixed=slippage_fixed,
                min_commission=min_commission,
            )
            tasks.append(task)

        batch = BatchBacktestResult(
            batch_id=batch_id,
            total_tasks=len(tasks),
            completed_tasks=0,
            failed_tasks=0,
            results=tasks,
            aggregated_metrics={},
            created_at=datetime.now().isoformat(),
        )

        self._batch_cache[batch_id] = batch
        return batch

    def execute_batch(
        self,
        batch: BatchBacktestResult,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> BatchBacktestResult:
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for task in batch.results:
                executor_agent = BacktestExecutorAgent(task, self.data_loader)
                futures.append(executor.submit(executor_agent.execute))

            completed = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                    completed += 1
                    if on_progress:
                        on_progress(completed, len(batch.results))
                except Exception as e:
                    logger.error("任务执行异常", extra={"error": str(e)})

        completed_count = sum(1 for t in batch.results if t.status == BacktestTaskStatus.COMPLETED)
        failed_count = sum(1 for t in batch.results if t.status == BacktestTaskStatus.FAILED)

        aggregator = AggregatorAgent(batch.results)
        aggregated_metrics = aggregator.aggregate()

        batch.completed_tasks = completed_count
        batch.failed_tasks = failed_count
        batch.aggregated_metrics = aggregated_metrics
        batch.completed_at = datetime.now().isoformat()

        self._batch_cache[batch.batch_id] = batch
        return batch

    def get_batch(self, batch_id: str) -> BatchBacktestResult | None:
        return self._batch_cache.get(batch_id)
