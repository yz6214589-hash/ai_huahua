from __future__ import annotations

import io

import pandas as pd


def code_to_standard(raw_code: str) -> str | None:
    code = str(raw_code or "").strip()
    if len(code) == 6:
        if code.startswith(("6", "5")):
            return code + ".SH"
        if code.startswith(("0", "3")):
            return code + ".SZ"
    return None


def load_broker_csv_bytes_list(contents: list[bytes]) -> pd.DataFrame:
    if not contents:
        return pd.DataFrame()

    all_dfs: list[pd.DataFrame] = []
    for content in contents:
        df = None
        for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=enc, dtype={"证券代码": str})
                break
            except Exception:
                df = None
        if df is None or df.empty:
            continue
        all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame()

    merged = pd.concat(all_dfs, ignore_index=True)
    merged.columns = [str(c).strip() for c in merged.columns]
    for col in merged.columns:
        if merged[col].dtype == object:
            merged[col] = merged[col].astype(str).str.strip()

    if "成交日期" not in merged.columns or "证券代码" not in merged.columns:
        raise ValueError("missing_required_columns")

    merged["成交日期"] = pd.to_datetime(merged["成交日期"].astype(str).str.strip(), errors="coerce")
    merged["证券代码"] = merged["证券代码"].astype(str).str.strip()

    num_cols = ["成交数量", "成交价格", "成交金额", "佣金", "印花税", "过户费", "结算费"]
    for c in num_cols:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)

    merged["标准代码"] = merged["证券代码"].apply(code_to_standard)
    merged = merged[merged["标准代码"].notna()].copy()
    merged = merged.dropna(subset=["成交日期"])
    merged = merged.sort_values("成交日期").reset_index(drop=True)
    return merged

