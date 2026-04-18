from __future__ import annotations

from typing import Any

import pandas as pd

from ..db import MySQLConfig, connect, execute, executemany
from ..models import DataSource
from .common import JobStats


INSERT_SQL = """
INSERT INTO trade_macro_indicator
(indicator_date, cpi_yoy, ppi_yoy, pmi, m2_yoy, shrzgm, lpr_1y, lpr_5y, data_source)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
cpi_yoy=COALESCE(VALUES(cpi_yoy), cpi_yoy),
ppi_yoy=COALESCE(VALUES(ppi_yoy), ppi_yoy),
pmi=COALESCE(VALUES(pmi), pmi),
m2_yoy=COALESCE(VALUES(m2_yoy), m2_yoy),
shrzgm=COALESCE(VALUES(shrzgm), shrzgm),
lpr_1y=COALESCE(VALUES(lpr_1y), lpr_1y),
lpr_5y=COALESCE(VALUES(lpr_5y), lpr_5y),
data_source=VALUES(data_source)
"""


def _parse_cn_date(series: pd.Series) -> pd.Series:
    import re

    def _one(s: Any):
        if pd.isna(s):
            return pd.NaT
        s = str(s).strip()
        m = re.match(r"(\d{4})\D+(\d{1,2})", s)
        if m:
            return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=1)
        m = re.match(r"^(\d{4})(\d{2})$", s)
        if m:
            return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=1)
        return pd.NaT

    return series.apply(_one)


def _find_col(columns: list[str], keywords: list[str]) -> str | None:
    for kw in keywords:
        for col in columns:
            if kw in col:
                return col
    return None


def run_macro_indicator(cfg: MySQLConfig, _mode: str | None, _params: dict[str, Any] | None) -> JobStats:
    import akshare as ak

    fallback_chain = [DataSource.akshare]
    conn = connect(cfg)
    try:
        cpi_df = ak.macro_china_cpi()
        ppi_df = ak.macro_china_ppi()
        pmi_df = ak.macro_china_pmi()
        m2_df = ak.macro_china_supply_of_money()
        shrzgm_df = ak.macro_china_shrzgm()
        lpr_df = ak.macro_china_lpr()

        frames = []

        if cpi_df is not None and len(cpi_df) > 0:
            date_col = cpi_df.columns[0]
            value_col = _find_col(list(cpi_df.columns), ["全国-同比增长", "同比增长", "同比"]) or cpi_df.columns[min(2, len(cpi_df.columns) - 1)]
            frames.append(pd.DataFrame({"date": _parse_cn_date(cpi_df[date_col]), "cpi_yoy": pd.to_numeric(cpi_df[value_col], errors="coerce")}))

        if ppi_df is not None and len(ppi_df) > 0:
            date_col = ppi_df.columns[0]
            value_col = _find_col(list(ppi_df.columns), ["当月同比增长", "同比增长", "同比"]) or ppi_df.columns[min(2, len(ppi_df.columns) - 1)]
            frames.append(pd.DataFrame({"date": _parse_cn_date(ppi_df[date_col]), "ppi_yoy": pd.to_numeric(ppi_df[value_col], errors="coerce")}))

        if pmi_df is not None and len(pmi_df) > 0:
            date_col = pmi_df.columns[0]
            value_col = _find_col(list(pmi_df.columns), ["制造业-指标", "制造业", "PMI"]) or pmi_df.columns[1]
            frames.append(pd.DataFrame({"date": _parse_cn_date(pmi_df[date_col]), "pmi": pd.to_numeric(pmi_df[value_col], errors="coerce")}))

        if m2_df is not None and len(m2_df) > 0:
            date_col = m2_df.columns[0]
            value_col = _find_col(list(m2_df.columns), ["M2）同比增长", "M2)同比", "M2同比", "同比"]) or m2_df.columns[min(2, len(m2_df.columns) - 1)]
            frames.append(pd.DataFrame({"date": _parse_cn_date(m2_df[date_col]), "m2_yoy": pd.to_numeric(m2_df[value_col], errors="coerce")}))

        if shrzgm_df is not None and len(shrzgm_df) > 0:
            date_col = shrzgm_df.columns[0]
            value_col = _find_col(list(shrzgm_df.columns), ["社会融资规模增量", "增量", "社融"]) or shrzgm_df.columns[min(1, len(shrzgm_df.columns) - 1)]
            frames.append(pd.DataFrame({"date": _parse_cn_date(shrzgm_df[date_col]), "shrzgm": pd.to_numeric(shrzgm_df[value_col], errors="coerce")}))

        if lpr_df is not None and len(lpr_df) > 0:
            date_col = lpr_df.columns[0]
            one_col = _find_col(list(lpr_df.columns), ["1年", "1Y"]) or lpr_df.columns[min(1, len(lpr_df.columns) - 1)]
            five_col = _find_col(list(lpr_df.columns), ["5年", "5Y"]) or (lpr_df.columns[min(2, len(lpr_df.columns) - 1)] if len(lpr_df.columns) > 2 else one_col)
            frames.append(
                pd.DataFrame(
                    {
                        "date": _parse_cn_date(lpr_df[date_col]),
                        "lpr_1y": pd.to_numeric(lpr_df[one_col], errors="coerce"),
                        "lpr_5y": pd.to_numeric(lpr_df[five_col], errors="coerce"),
                    }
                )
            )

        if not frames:
            return JobStats(
                items_processed=0,
                rows_written=0,
                failed_items=[],
                data_source_final=DataSource.akshare,
                fallback_chain=fallback_chain,
                message="AkShare接口返回空",
            )

        merged = frames[0]
        for f in frames[1:]:
            merged = merged.merge(f, on="date", how="outer")
        merged = merged.dropna(subset=["date"]).sort_values("date")
        merged["indicator_date"] = (merged["date"] + pd.offsets.MonthEnd(0)).dt.date

        rows = []
        for _, r in merged.iterrows():
            rows.append(
                (
                    str(r["indicator_date"]),
                    None if pd.isna(r.get("cpi_yoy")) else float(r.get("cpi_yoy")),
                    None if pd.isna(r.get("ppi_yoy")) else float(r.get("ppi_yoy")),
                    None if pd.isna(r.get("pmi")) else float(r.get("pmi")),
                    None if pd.isna(r.get("m2_yoy")) else float(r.get("m2_yoy")),
                    None if pd.isna(r.get("shrzgm")) else float(r.get("shrzgm")),
                    None if pd.isna(r.get("lpr_1y")) else float(r.get("lpr_1y")),
                    None if pd.isna(r.get("lpr_5y")) else float(r.get("lpr_5y")),
                    "akshare",
                )
            )

        written = executemany(conn, INSERT_SQL, rows)
        conn.commit()
        return JobStats(
            items_processed=len(rows),
            rows_written=written,
            failed_items=[],
            data_source_final=DataSource.akshare,
            fallback_chain=fallback_chain,
            message=None,
        )
    finally:
        conn.close()

