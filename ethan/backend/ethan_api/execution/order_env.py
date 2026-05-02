from __future__ import annotations

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from ..rl.data_loader import generate_intraday_data


class MarketImpactModel:
    def __init__(self, adv: float, sigma: float, eta: float = 0.1, gamma: float = 0.05, beta: float = 0.5) -> None:
        self.adv = float(adv)
        self.sigma = float(sigma)
        self.eta = float(eta)
        self.gamma = float(gamma)
        self.beta = float(beta)

    def calc_impact(self, volume: float, current_price: float) -> tuple[float, float, float]:
        if volume <= 0:
            return 0.0, 0.0, float(current_price)
        participation = float(volume) / float(self.adv)
        temp_impact = float(self.eta) * float(self.sigma) * (participation ** float(self.beta))
        perm_impact = float(self.gamma) * float(self.sigma) * participation
        impacted_price = float(current_price) * (1.0 + temp_impact + perm_impact)
        return temp_impact, perm_impact, impacted_price


class OrderExecutionEnv(gym.Env):
    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        total_order: int,
        daily_data_list: list,
        adv: float,
        num_steps: int = 48,
        impact_eta: float = 0.1,
        impact_gamma: float = 0.05,
    ) -> None:
        super().__init__()

        self.total_order = int(total_order)
        self.daily_data_list = daily_data_list
        self.adv = float(adv)
        self.num_steps = int(num_steps)

        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32)
        self.action_space = spaces.Box(low=np.array([0.0], dtype=np.float32), high=np.array([1.0], dtype=np.float32))

        self.sigma = 0.02
        self.impact_model = MarketImpactModel(adv=self.adv, sigma=self.sigma, eta=impact_eta, gamma=impact_gamma)

        self.current_step = 0
        self.remaining_qty = self.total_order
        self.arrival_price = 0.0
        self.executed_qty = 0
        self.executed_cost = 0.0
        self.intraday = None

        self.history: dict[str, list] = {"step": [], "price": [], "exec_qty": [], "exec_price": [], "remaining": [], "vwap": []}
        self._day_idx = 0

    def _load_day(self, day_idx: int) -> None:
        row = self.daily_data_list[day_idx % len(self.daily_data_list)]
        self.sigma = float(row["high"] - row["low"]) / float(row["close"])
        self.impact_model.sigma = self.sigma
        self.intraday = generate_intraday_data(row, self.num_steps, seed=day_idx)
        self.arrival_price = float(self.intraday["prices"][0])

    def _get_obs(self) -> np.ndarray:
        remaining_ratio = float(self.remaining_qty) / float(self.total_order)
        time_ratio = float(self.num_steps - self.current_step) / float(self.num_steps)

        current_price = float(self.intraday["prices"][self.current_step])
        price_drift = (current_price - float(self.arrival_price)) / float(self.arrival_price)

        vol = float(self.sigma)
        if self.executed_qty > 0:
            current_vwap = float(self.executed_cost) / float(self.executed_qty)
            vwap_drift = (current_vwap - float(self.arrival_price)) / float(self.arrival_price)
        else:
            vwap_drift = 0.0

        return np.array([remaining_ratio, time_ratio, float(price_drift), vol, float(vwap_drift)], dtype=np.float32)

    def reset(self, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        self.current_step = 0
        self.remaining_qty = self.total_order
        self.executed_qty = 0
        self.executed_cost = 0.0
        self.history = {"step": [], "price": [], "exec_qty": [], "exec_price": [], "remaining": [], "vwap": []}

        self._load_day(self._day_idx)
        self._day_idx += 1

        return self._get_obs(), {}

    def step(self, action):
        exec_ratio = float(np.clip(float(action[0]), 0.0, 1.0))

        if self.current_step == self.num_steps - 1:
            exec_qty = int(self.remaining_qty)
        else:
            exec_qty = int(int(self.remaining_qty) * exec_ratio)
            exec_qty = min(exec_qty, int(self.remaining_qty))

        market_price = float(self.intraday["prices"][self.current_step + 1])
        if exec_qty > 0:
            _, _, impacted_price = self.impact_model.calc_impact(exec_qty, market_price)
            exec_price = float(impacted_price)
        else:
            exec_price = market_price

        self.executed_cost += float(exec_qty) * float(exec_price)
        self.executed_qty += int(exec_qty)
        self.remaining_qty -= int(exec_qty)

        current_vwap = float(self.executed_cost) / float(self.executed_qty) if self.executed_qty > 0 else 0.0
        self.history["step"].append(int(self.current_step))
        self.history["price"].append(float(market_price))
        self.history["exec_qty"].append(int(exec_qty))
        self.history["exec_price"].append(float(exec_price) if exec_qty > 0 else 0.0)
        self.history["remaining"].append(int(self.remaining_qty))
        self.history["vwap"].append(float(current_vwap))

        self.current_step += 1
        terminated = self.current_step >= self.num_steps

        reward = 0.0
        if exec_qty > 0:
            impact_cost = (float(exec_price) - float(market_price)) / float(market_price)
            reward -= float(impact_cost) * 50.0

            uniform_qty = float(self.total_order) / float(self.num_steps)
            if float(exec_qty) > uniform_qty * 2.0:
                excess = (float(exec_qty) - uniform_qty * 2.0) / float(self.total_order)
                reward -= float(excess) * 5.0

        time_left = float(self.num_steps - self.current_step) / float(self.num_steps)
        remaining_ratio = float(self.remaining_qty) / float(self.total_order)
        if time_left < 0.2 and remaining_ratio > 0.5:
            reward -= remaining_ratio * 2.0

        if terminated and self.executed_qty > 0:
            actual_vwap = float(self.executed_cost) / float(self.executed_qty)
            is_cost = (actual_vwap - float(self.arrival_price)) / float(self.arrival_price)
            reward -= abs(float(is_cost)) * 30.0

        return self._get_obs(), float(reward), bool(terminated), False, {"exec_qty": int(exec_qty), "exec_price": float(exec_price)}

    def get_execution_summary(self) -> dict | None:
        if self.executed_qty <= 0:
            return None
        actual_vwap = float(self.executed_cost) / float(self.executed_qty)
        is_cost = (actual_vwap - float(self.arrival_price)) / float(self.arrival_price)
        market_vwap = float(self.intraday["vwap"])
        vwap_slip = (actual_vwap - market_vwap) / market_vwap
        return {
            "arrival_price": float(self.arrival_price),
            "actual_vwap": float(actual_vwap),
            "market_vwap": float(market_vwap),
            "implementation_shortfall": float(is_cost),
            "vwap_slippage": float(vwap_slip),
            "total_executed": int(self.executed_qty),
            "num_slices": int(sum(1 for q in self.history["exec_qty"] if int(q) > 0)),
        }


class TWAPStrategy:
    def __init__(self, total_order: int, num_steps: int) -> None:
        self.qty_per_step = int(total_order) // int(num_steps)
        self.total_order = int(total_order)
        self.step = 0
        self.num_steps = int(num_steps)

    def get_action(self, obs: np.ndarray) -> np.ndarray:
        self.step += 1
        if self.step == self.num_steps:
            ratio = 1.0
        else:
            remaining_qty = float(obs[0]) * float(self.total_order)
            ratio = float(self.qty_per_step) / max(remaining_qty, 1.0)
            ratio = float(np.clip(ratio, 0.0, 1.0))
        return np.array([ratio], dtype=np.float32)


class VWAPStrategy:
    def __init__(self, total_order: int, num_steps: int) -> None:
        x = np.linspace(0, 1, int(num_steps))
        weights = 1.5 * (x - 0.5) ** 2 + 0.3
        self.weights = weights / float(weights.sum())
        self.num_steps = int(num_steps)
        self.step = 0

    def get_action(self, obs: np.ndarray) -> np.ndarray:
        remaining_ratio = float(obs[0])
        if self.step < self.num_steps:
            target_ratio = float(self.weights[self.step])
            ratio = target_ratio / remaining_ratio if remaining_ratio > 0 else 0.0
            self.step += 1
        else:
            ratio = 1.0
        return np.array([float(np.clip(ratio, 0.0, 1.0))], dtype=np.float32)
