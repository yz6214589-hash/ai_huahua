from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GridSignal:
    action: str
    price: float
    shares: int
    grid_level: int


class GridEngine:
    def __init__(self, lower: float, upper: float, num_grids: int, total_capital: float):
        self.lower = float(lower)
        self.upper = float(upper)
        self.num_grids = int(num_grids)
        self.total_capital = float(total_capital)

        self.grid_size = (self.upper - self.lower) / float(self.num_grids)
        self.levels = [self.lower + i * self.grid_size for i in range(self.num_grids + 1)]
        self.current_grid = None
        self.position_at = [False] * self.num_grids
        self.capital_per_grid = self.total_capital / float(self.num_grids) if self.num_grids > 0 else 0.0
        self.total_profit = 0.0
        self.trades_count = 0

    def _get_grid_index(self, price: float) -> int:
        if price <= self.lower:
            return 0
        if price >= self.upper:
            return self.num_grids - 1
        idx = int((price - self.lower) / self.grid_size)
        return max(0, min(self.num_grids - 1, idx))

    def _get_shares(self, price: float) -> int:
        if price <= 0:
            return 0
        shares = int(self.capital_per_grid / price)
        shares = (shares // 100) * 100
        return max(100, shares) if shares > 0 else 0

    def update(self, price: float) -> list[GridSignal]:
        price = float(price)
        if self.num_grids <= 0:
            return []

        grid = self._get_grid_index(price)
        if self.current_grid is None:
            self.current_grid = grid
            return []

        signals: list[GridSignal] = []

        if grid < self.current_grid:
            for g in range(self.current_grid - 1, grid - 1, -1):
                if not self.position_at[g]:
                    p = self.levels[g]
                    shares = self._get_shares(p)
                    if shares > 0:
                        self.position_at[g] = True
                        signals.append(GridSignal(action="BUY", price=p, shares=shares, grid_level=g))
        elif grid > self.current_grid:
            for g in range(self.current_grid, grid):
                if self.position_at[g]:
                    p = self.levels[g + 1]
                    shares = self._get_shares(p)
                    if shares > 0:
                        self.position_at[g] = False
                        signals.append(GridSignal(action="SELL", price=p, shares=shares, grid_level=g))

        self.current_grid = grid
        return signals


class ChanGridEngine(GridEngine):
    def __init__(self, zg: float, zd: float, num_grids: int, total_capital: float):
        super().__init__(lower=float(zd), upper=float(zg), num_grids=int(num_grids), total_capital=float(total_capital))
        self.zg = float(zg)
        self.zd = float(zd)
        self.active = True

    def switch_zhongshu(self, new_zg: float, new_zd: float) -> None:
        self.zg = float(new_zg)
        self.zd = float(new_zd)
        self.lower = self.zd
        self.upper = self.zg
        self.grid_size = (self.upper - self.lower) / float(self.num_grids)
        self.levels = [self.lower + i * self.grid_size for i in range(self.num_grids + 1)]
        self.current_grid = None
        self.position_at = [False] * self.num_grids

    def deactivate(self) -> None:
        self.active = False

    def update(self, price: float) -> list[GridSignal]:
        if not self.active:
            return []
        return super().update(price)
