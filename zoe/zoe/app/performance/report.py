from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import quantstats as qs


def generate_report_html(
    returns: pd.Series,
    benchmark: pd.Series | None,
    output_dir: str,
    title: str = "QuantStats 绩效分析",
) -> dict[str, Any]:
    os.makedirs(output_dir, exist_ok=True)

    report_id = str(uuid4())
    filename = f"{report_id}.html"
    report_path = os.path.join(output_dir, filename)

    r = returns.copy()
    r.index = pd.to_datetime(r.index)
    r = r.sort_index().astype(float).fillna(0.0)

    b = None
    if benchmark is not None:
        b = benchmark.copy()
        b.index = pd.to_datetime(b.index)
        b = b.sort_index().astype(float).fillna(0.0)

    qs.reports.html(r, benchmark=b, title=title, output=report_path)
    return {"report_id": report_id, "report_filename": filename, "report_path": report_path}
