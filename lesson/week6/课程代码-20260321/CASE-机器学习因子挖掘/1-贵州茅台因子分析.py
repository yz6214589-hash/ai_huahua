# -*- coding: utf-8 -*-
"""
贵州茅台因子分析: 因子分类枚举、calc_features、可选基本面、单因子 RankIC。

运行: python 1-贵州茅台因子分析.py
"""

import pandas as pd
import numpy as np
from scipy.stats import spearmanr

from data_loader import load_stock_data, load_financial_data
from feature_engine import (
    FACTOR_TAXONOMY,
    calc_features,
    calc_fundamental_features,
    get_all_feature_cols,
)


def calc_rank_ic(factor_values, forward_returns):
    """单因子 RankIC: Spearman(因子, 未来收益)。有效样本少于 30 返回 nan。"""
    valid = pd.DataFrame({
        'factor': factor_values,
        'fwd_ret': forward_returns
    }).dropna()
    if len(valid) < 30:
        return np.nan
    ic, _ = spearmanr(valid['factor'], valid['fwd_ret'])
    return ic


if __name__ == '__main__':

    STOCK_CODE = '600519.SH'
    START_DATE = '2023-01-01'
    END_DATE = '2025-12-31'

    # ---------- 1. 因子分类体系(枚举 FACTOR_TAXONOMY) ----------
    print('\n[1] FACTOR_TAXONOMY')
    total_features = 0
    for cat_key, cat_info in FACTOR_TAXONOMY.items():
        n = len(cat_info['features'])
        total_features += n
        feat_str = ', '.join(cat_info['features'][:5])
        if n > 5:
            feat_str += f' ... (共{n}个)'
        print(f"  {cat_info['name']} ({cat_key}): {n} 个 | {feat_str}")
    print(f'  技术因子合计: {total_features} | 课件中另含 4 个基本面定义')

    # ---------- 2. 日K + 技术因子 ----------
    print(f'\n[2] load_stock_data + calc_features | {STOCK_CODE} {START_DATE}~{END_DATE}')
    df = load_stock_data(STOCK_CODE, START_DATE, END_DATE)
    print(f'  交易日: {len(df)} | {df.index[0].strftime("%Y-%m-%d")} ~ {df.index[-1].strftime("%Y-%m-%d")}')
    print(f'  close: {df["close"].min():.2f} ~ {df["close"].max():.2f}')

    df = calc_features(df)
    tech_cols = get_all_feature_cols()
    available_tech = [c for c in tech_cols if c in df.columns]
    print(f'  技术因子列数: {len(available_tech)}')

    df['fwd_ret_1d'] = df['close'].pct_change(1).shift(-1)

    # ---------- 3. 基本面因子(可选) ----------
    print('\n[3] load_financial_data + calc_fundamental_features')
    fundamental_cols = []
    try:
        fin_df = load_financial_data(report_date_min='2022-01-01')
        if fin_df.empty:
            print('  财务表为空, 跳过')
        else:
            print(f'  财务记录: {len(fin_df)} | 股票数: {fin_df["stock_code"].nunique()}')
            fund_features = calc_fundamental_features(df, fin_df, STOCK_CODE)
            for col in fund_features.columns:
                df[col] = fund_features[col]
                if df[col].notna().sum() > 0:
                    fundamental_cols.append(col)
            print(f'  合并基本面列: {fundamental_cols}')
    except Exception as e:
        print(f'  异常: {e}')

    # ---------- 4. 行业 One-Hot 演示(pd.get_dummies) ----------
    print('\n[4] 行业哑变量示例 get_dummies')
    industry_demo = pd.DataFrame({
        'stock_code': ['600519.SH', '000858.SZ', '601318.SH', '600036.SH', '000001.SZ'],
        'stock_name': ['贵州茅台', '五粮液', '中国平安', '招商银行', '平安银行'],
        'industry': ['食品饮料', '食品饮料', '非银金融', '银行', '银行'],
    })
    industry_dummies = pd.get_dummies(industry_demo['industry'], prefix='ind')
    demo_out = pd.concat([industry_demo[['stock_code', 'stock_name']], industry_dummies], axis=1)
    print(demo_out.to_string(index=False))
    print(f'  哑变量列数: {industry_dummies.shape[1]}')

    # ---------- 5. 单因子 RankIC ----------
    print('\n[5] 单因子 RankIC vs fwd_ret_1d')
    all_factor_cols = available_tech + fundamental_cols
    ic_results = []
    for col in all_factor_cols:
        ic_val = calc_rank_ic(df[col], df['fwd_ret_1d'])
        if np.isnan(ic_val):
            continue
        cat_name = '基本面'
        for cat_key, cat_info in FACTOR_TAXONOMY.items():
            if col in cat_info['features']:
                cat_name = cat_info['name']
                break
        ic_results.append({
            'factor': col,
            'category': cat_name,
            'RankIC': round(ic_val, 4),
            '|IC|': round(abs(ic_val), 4),
        })

    ic_df = pd.DataFrame(ic_results).sort_values('|IC|', ascending=False)
    ic_df = ic_df.reset_index(drop=True)
    ic_df.index = ic_df.index + 1
    ic_df.index.name = '排名'

    # ---------- 6. 汇总输出 ----------
    print(f'\n[6] 完成检验因子数: {len(ic_df)} | {STOCK_CODE}')
    top_n = min(15, len(ic_df))
    print('\nTOP 15 by |IC|')
    print(ic_df.head(top_n).to_string())

    strong = ic_df[ic_df['|IC|'] >= 0.05]
    effective = ic_df[(ic_df['|IC|'] >= 0.03) & (ic_df['|IC|'] < 0.05)]
    weak = ic_df[(ic_df['|IC|'] >= 0.02) & (ic_df['|IC|'] < 0.03)]
    ineffective = ic_df[ic_df['|IC|'] < 0.02]
    print(f'\n分档: >=0.05={len(strong)} | [0.03,0.05)={len(effective)} | '
          f'[0.02,0.03)={len(weak)} | <0.02={len(ineffective)}')

    cat_ic = ic_df.groupby('category')['|IC|'].agg(['mean', 'max', 'count'])
    cat_ic.columns = ['平均|IC|', '最大|IC|', '因子数']
    cat_ic = cat_ic.sort_values('平均|IC|', ascending=False)
    print('\n按类别 |IC|')
    print(cat_ic.to_string())
