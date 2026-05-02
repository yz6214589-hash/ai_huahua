from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass
class TickDataGenerator:
    base_price: float = 100.0
    seed: int | None = None

    def __post_init__(self) -> None:
        self.rng = np.random.RandomState(self.seed)

    def generate_retail(self, n_ticks: int = 500) -> pd.DataFrame:
        price = float(self.base_price)
        ticks: list[dict[str, Any]] = []
        for i in range(int(n_ticks)):
            dt = float(self.rng.exponential(2.0))
            direction = int(self.rng.choice([1, -1]))
            if abs(price - self.base_price) / self.base_price > 0.01:
                if price > self.base_price:
                    direction = int(self.rng.choice([1, -1], p=[0.7, 0.3]))
                else:
                    direction = int(self.rng.choice([1, -1], p=[0.3, 0.7]))
            volume = int(self.rng.choice([100, 200, 300]))
            if float(self.rng.random()) < 0.05:
                volume = int(self.rng.randint(1000, 3000))
            price += direction * float(self.rng.uniform(0.01, 0.05))
            cancel = 1 if float(self.rng.random()) < 0.05 else 0
            ticks.append(
                {
                    "timestamp": i * dt,
                    "price": round(price, 4),
                    "volume": volume,
                    "direction": direction,
                    "order_type": "market" if float(self.rng.random()) < 0.6 else "limit",
                    "cancel": cancel,
                }
            )
        return pd.DataFrame(ticks)

    def generate_mm_rl(self, n_ticks: int = 500) -> pd.DataFrame:
        price = float(self.base_price)
        ticks: list[dict[str, Any]] = []
        inventory = 0.0
        for i in range(int(n_ticks)):
            dt = float(self.rng.uniform(0.1, 0.3))
            if float(self.rng.random()) < 0.7:
                if inventory > 200:
                    direction = -1
                elif inventory < -200:
                    direction = 1
                else:
                    direction = int(self.rng.choice([1, -1]))
            else:
                direction = int(self.rng.choice([1, -1]))
            volume = 100
            price += direction * float(self.rng.uniform(0.005, 0.02))
            inventory += direction * volume
            cancel = 1 if float(self.rng.random()) < 0.30 else 0
            ticks.append(
                {
                    "timestamp": i * dt,
                    "price": round(price, 4),
                    "volume": volume,
                    "direction": direction,
                    "order_type": "limit",
                    "cancel": cancel,
                }
            )
        return pd.DataFrame(ticks)

    def generate_execution_rl(self, n_ticks: int = 500) -> pd.DataFrame:
        price = float(self.base_price)
        ticks: list[dict[str, Any]] = []
        total_target = 50000
        executed = 0
        for i in range(int(n_ticks)):
            dt = float(self.rng.uniform(0.3, 0.8))
            direction = 1
            progress = float(i) / float(n_ticks)
            u_weight = 1.5 * (progress - 0.5) ** 2 + 0.3
            base_vol = int(total_target / int(n_ticks) * u_weight * 2)
            volume = max(100, min(base_vol, 1000))
            volume = (volume // 100) * 100
            impact = 0.001 * (executed / total_target)
            price += direction * float(self.rng.uniform(0.005, 0.03)) + impact
            if price > self.base_price * 1.01:
                volume = max(100, volume // 2)
            executed += volume
            cancel = 1 if float(self.rng.random()) < 0.15 else 0
            ticks.append(
                {
                    "timestamp": i * dt,
                    "price": round(price, 4),
                    "volume": int(volume),
                    "direction": int(direction),
                    "order_type": "limit" if float(self.rng.random()) < 0.7 else "market",
                    "cancel": int(cancel),
                }
            )
        return pd.DataFrame(ticks)


def extract_features(tick_df: pd.DataFrame, window: int = 50) -> dict[str, float]:
    prices = tick_df["price"].to_numpy(dtype=float)
    volumes = tick_df["volume"].to_numpy(dtype=float)
    directions = tick_df["direction"].to_numpy(dtype=float)
    timestamps = tick_df["timestamp"].to_numpy(dtype=float)
    cancels = tick_df["cancel"].to_numpy(dtype=float)
    n = int(len(tick_df))

    buy_vol = float(np.sum(volumes[directions == 1]))
    sell_vol = float(np.sum(volumes[directions == -1]))
    total_vol = buy_vol + sell_vol
    ofi = (buy_vol - sell_vol) / total_vol if total_vol > 0 else 0.0
    ofi_abs = float(abs(ofi))

    amounts = prices * volumes
    large_threshold = float(amounts.mean() * 3) if n else 0.0
    large_ratio = float(np.sum(amounts > large_threshold) / n) if n else 0.0

    cancel_rate = float(cancels.mean()) if n else 0.0

    if len(timestamps) > 1:
        intervals = np.diff(timestamps)
        interval_cv = float(np.std(intervals) / (np.mean(intervals) + 1e-8))
    else:
        interval_cv = 1.0

    recovery_speeds: list[float] = []
    w = int(window)
    for i in range(n - w):
        if amounts[i] > large_threshold:
            pre_price = float(prices[max(0, i - 5) : i].mean()) if i > 5 else float(prices[i])
            post_prices = prices[i + 1 : i + 11]
            if len(post_prices) > 5:
                recovery = float(abs(post_prices[-1] - prices[i]) / (abs(prices[i] - pre_price) + 1e-8))
                recovery_speeds.append(recovery)
    avg_recovery = float(np.mean(recovery_speeds)) if recovery_speeds else 0.5

    run_lengths: list[int] = []
    current_run = 1
    for i in range(1, n):
        if directions[i] == directions[i - 1]:
            current_run += 1
        else:
            run_lengths.append(current_run)
            current_run = 1
    run_lengths.append(current_run)
    avg_run_length = float(np.mean(run_lengths)) if run_lengths else 1.0

    vol_cv = float(np.std(volumes) / (np.mean(volumes) + 1e-8)) if n else 0.0

    buy_count = float(np.sum(directions == 1))
    sell_count = float(np.sum(directions == -1))
    direction_symmetry = float(min(buy_count, sell_count) / (max(buy_count, sell_count) + 1e-8))

    limit_ratio = float(np.sum(tick_df["order_type"] == "limit") / n) if n else 0.0

    price_vol = float(np.std(np.diff(prices)) / np.mean(prices)) if len(prices) > 1 else 0.0

    return {
        "ofi_abs": ofi_abs,
        "large_ratio": large_ratio,
        "cancel_rate": cancel_rate,
        "interval_cv": interval_cv,
        "recovery_speed": avg_recovery,
        "run_length": avg_run_length,
        "vol_cv": vol_cv,
        "direction_symmetry": direction_symmetry,
        "limit_ratio": limit_ratio,
        "price_volatility": price_vol,
    }


def build_dataset(n_samples_per_class: int = 200, seed: int = 42, n_ticks: int = 300, window: int = 50):
    gen = TickDataGenerator(seed=seed)
    features_list: list[dict[str, float]] = []
    labels: list[int] = []
    label_names = {0: "散户交易", 1: "RL做市", 2: "RL拆单"}

    for cls, (gen_fn, label) in enumerate(
        [
            (gen.generate_retail, 0),
            (gen.generate_mm_rl, 1),
            (gen.generate_execution_rl, 2),
        ]
    ):
        for i in range(int(n_samples_per_class)):
            gen.rng = np.random.RandomState(int(seed) + cls * 1000 + i)
            ticks = gen_fn(n_ticks=int(n_ticks))
            feats = extract_features(ticks, window=int(window))
            features_list.append(feats)
            labels.append(int(label))

    feature_names = list(features_list[0].keys())
    x = np.array([[f[fn] for fn in feature_names] for f in features_list], dtype=float)
    y = np.array(labels, dtype=int)
    return x, y, feature_names, label_names


def plot_feature_radar(x: np.ndarray, y: np.ndarray, feature_names: list[str], label_names: dict[int, str], out_path: str) -> str:
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, len(feature_names), endpoint=False).tolist()
    angles += angles[:1]
    colors = ["#3498db", "#e74c3c", "#2ecc71"]
    mins = x.min(axis=0)
    maxs = x.max(axis=0)
    for cls in range(3):
        mask = y == cls
        means = x[mask].mean(axis=0)
        normalized = (means - mins) / (maxs - mins + 1e-8)
        values = normalized.tolist()
        values += values[:1]
        ax.plot(angles, values, "o-", linewidth=2, label=label_names[cls], color=colors[cls])
        ax.fill(angles, values, alpha=0.1, color=colors[cls])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(feature_names, fontsize=9)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_typical_patterns(seed: int, out_path: str, n_ticks: int = 300) -> str:
    gen = TickDataGenerator(seed=seed)
    fig, axes = plt.subplots(3, 3, figsize=(14, 9))
    data_configs = [
        ("散户交易", gen.generate_retail, "#3498db"),
        ("RL做市商", gen.generate_mm_rl, "#e74c3c"),
        ("RL拆单执行", gen.generate_execution_rl, "#2ecc71"),
    ]
    for row, (name, gen_fn, color) in enumerate(data_configs):
        ticks = gen_fn(int(n_ticks))
        ax = axes[row, 0]
        ax.plot(ticks["timestamp"], ticks["price"], color=color, linewidth=0.8)
        ax.set_title(f"{name}-价格")
        ax.grid(True, alpha=0.3)

        ax = axes[row, 1]
        buy_mask = ticks["direction"] == 1
        sell_mask = ticks["direction"] == -1
        ax.bar(ticks.index[buy_mask], ticks.loc[buy_mask, "volume"], color="#e74c3c", alpha=0.6, width=1.5)
        ax.bar(ticks.index[sell_mask], -ticks.loc[sell_mask, "volume"], color="#2ecc71", alpha=0.6, width=1.5)
        ax.set_title(f"{name}-买卖量")
        ax.grid(True, alpha=0.3)

        ax = axes[row, 2]
        intervals = np.diff(ticks["timestamp"].to_numpy(dtype=float))
        ax.hist(intervals, bins=20, color=color, alpha=0.7, edgecolor="white")
        ax.set_title(f"{name}-间隔")
        ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_confusion_matrix(cm: np.ndarray, label_names: dict[int, str], out_path: str) -> str:
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(cm, cmap="Blues")
    labels = [label_names[i] for i in range(len(label_names))]
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_yticklabels(labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            val = int(cm[i, j])
            color = "white" if val > cm.max() / 2 else "black"
            ax.text(j, i, f"{val}", ha="center", va="center", color=color, fontsize=14)
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_feature_importance(clf: RandomForestClassifier, feature_names: list[str], out_path: str) -> str:
    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    names = [feature_names[i] for i in indices]
    values = [float(importances[i]) for i in indices]
    colors = plt.cm.RdYlBu_r(np.linspace(0.2, 0.8, len(names)))
    ax.barh(range(len(names)), values, color=colors, edgecolor="white")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.grid(True, alpha=0.3, axis="x")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _infer_behavior_from_stock_code(stock_code: str) -> int:
    s = str(stock_code or "").strip()
    if not s:
        return 0
    v = sum(ord(c) for c in s) % 3
    return int(v)


def run_mainforce_job(
    output_dir: str,
    n_samples_per_class: int = 200,
    seed: int = 42,
    n_ticks: int = 300,
    window: int = 50,
    stock_code: str | None = None,
) -> dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    x, y, feature_names, label_names = build_dataset(
        n_samples_per_class=int(n_samples_per_class),
        seed=int(seed),
        n_ticks=int(n_ticks),
        window=int(window),
    )

    total = int(len(y))
    n_classes = 3
    test_n = max(n_classes, int(round(total * 0.3)))
    test_n = min(test_n, max(n_classes, total - n_classes))
    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=test_n, random_state=int(seed), stratify=y)
    clf = RandomForestClassifier(n_estimators=60, max_depth=8, random_state=int(seed), n_jobs=-1)
    clf.fit(x_train, y_train)
    train_acc = float(clf.score(x_train, y_train))
    test_acc = float(clf.score(x_test, y_test))

    cm = confusion_matrix(y_test, clf.predict(x_test))
    radar_path = plot_feature_radar(x, y, feature_names, label_names, os.path.join(output_dir, "radar.png"))
    patterns_path = plot_typical_patterns(seed=int(seed), out_path=os.path.join(output_dir, "patterns.png"), n_ticks=int(n_ticks))
    confusion_path = plot_confusion_matrix(cm, label_names, os.path.join(output_dir, "confusion.png"))
    importance_path = plot_feature_importance(clf, feature_names, os.path.join(output_dir, "feature_importance.png"))

    probs = None
    pred_label = None
    if stock_code:
        gen = TickDataGenerator(seed=int(seed) + _infer_behavior_from_stock_code(stock_code))
        gen_fn = [gen.generate_retail, gen.generate_mm_rl, gen.generate_execution_rl][_infer_behavior_from_stock_code(stock_code)]
        ticks = gen_fn(int(n_ticks))
        feats = extract_features(ticks, window=int(window))
        vec = np.array([[feats[n] for n in feature_names]], dtype=float)
        if hasattr(clf, "predict_proba"):
            p = clf.predict_proba(vec)[0].tolist()
            probs = {label_names[i]: float(p[i]) for i in range(3)}
        pred = int(clf.predict(vec)[0])
        pred_label = label_names.get(pred, str(pred))

    feature_importance = [
        {"name": feature_names[i], "value": float(v)}
        for i, v in sorted(enumerate(clf.feature_importances_), key=lambda x: float(x[1]), reverse=True)
    ]

    return {
        "train_acc": train_acc,
        "test_acc": test_acc,
        "pred_label": pred_label,
        "pred_proba": probs,
        "feature_importance": feature_importance,
        "artifacts": {
            "radar_png": radar_path,
            "patterns_png": patterns_path,
            "confusion_png": confusion_path,
            "feature_importance_png": importance_path,
        },
    }
