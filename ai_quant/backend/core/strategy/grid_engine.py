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
        self.position_at = [0] * (self.num_grids + 1)
        self.capital_per_grid = self.total_capital / float(self.num_grids) if self.num_grids > 0 else 0.0
        self.total_profit = 0.0
        self.buy_count = 0
        self.sell_count = 0
        self.max_layers = 0

    def _get_cell(self, price: float) -> int:
        if price < self.lower:
            return -1
        if price >= self.upper:
            return self.num_grids
        return int((price - self.lower) / self.grid_size)

    def _calc_shares(self, price: float) -> int:
        if price <= 0:
            return 0
        shares = self.capital_per_grid / price
        shares = int(shares // 100) * 100
        return max(shares, 100)

    def _current_layers(self) -> int:
        return sum(1 for s in self.position_at if s > 0)

    def update(self, price: float) -> list[GridSignal]:
        price = float(price)
        if self.num_grids <= 0:
            return []

        curr_cell = self._get_cell(price)
        if self.current_grid is None:
            self.current_grid = curr_cell
            return []

        signals: list[GridSignal] = []
        prev_cell = self.current_grid

        if curr_cell < prev_cell:
            for cell in range(prev_cell - 1, curr_cell - 1, -1):
                if 0 <= cell < self.num_grids and self.position_at[cell] == 0:
                    p = self.levels[cell]
                    size = self._calc_shares(p)
                    if size > 0:
                        self.position_at[cell] = size
                        self.buy_count += 1
                        signals.append(GridSignal(action="BUY", price=p, shares=size, grid_level=cell))

        elif curr_cell > prev_cell:
            for cell in range(prev_cell, curr_cell):
                if 0 <= cell < self.num_grids and self.position_at[cell] > 0:
                    size = self.position_at[cell]
                    sell_price = self.levels[cell + 1]
                    profit = (sell_price - self.levels[cell]) * size
                    self.total_profit += profit
                    self.position_at[cell] = 0
                    self.sell_count += 1
                    signals.append(GridSignal(action="SELL", price=sell_price, shares=size, grid_level=cell))

        layers = self._current_layers()
        self.max_layers = max(self.max_layers, layers)
        self.current_grid = curr_cell
        return signals


class ChanGridEngine(GridEngine):
    def __init__(self, zg: float, zd: float, num_grids: int, total_capital: float):
        super().__init__(lower=float(zd), upper=float(zg), num_grids=int(num_grids), total_capital=float(total_capital))
        self.zg = float(zg)
        self.zd = float(zd)
        self.active = True
        self.switch_count = 0

    def switch_zhongshu(self, new_zg: float, new_zd: float) -> None:
        self.zg = float(new_zg)
        self.zd = float(new_zd)
        self.lower = self.zd
        self.upper = self.zg
        self.grid_size = (self.upper - self.lower) / float(self.num_grids)
        self.levels = [self.lower + i * self.grid_size for i in range(self.num_grids + 1)]
        self.current_grid = None
        self.position_at = [0] * (self.num_grids + 1)
        self.active = True
        self.switch_count += 1

    def deactivate(self) -> None:
        self.active = False

    def update(self, price: float) -> list[GridSignal]:
        if not self.active:
            return []
        return super().update(price)
