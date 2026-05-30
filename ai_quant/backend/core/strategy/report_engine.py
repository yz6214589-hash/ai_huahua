# -*- coding: utf-8 -*-
"""
QuantStats 报告引擎

功能:
  1. nav_to_returns()            - 净值序列转收益率序列
  2. generate_chinese_report()   - 生成中文 HTML 绩效报告
  3. configure_matplotlib_chinese() - macOS 中文字体配置
  4. metrics_to_html_cards()     - 指标卡片 HTML
  5. metrics_to_html_table()     - 指标表格 HTML

适配说明:
  - 去掉对 yaml 的依赖，使用内置翻译映射
  - 去掉对 llm_engine 的依赖
  - 去掉对 data_loader 的依赖
  - matplotlib 中文字体配置适配 macOS（使用 PingFang SC）
  - 输出目录改为 backend/static/reports/
"""
from __future__ import annotations

import os
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

import quantstats as qs


# ============================================================
# 净值 / 收益率转换
# ============================================================

def nav_to_returns(nav_series):
    """
    净值序列 -> 日收益率序列

    参数:
        nav_series: Series, 索引为日期, 值为净值

    返回:
        Series, 日收益率
    """
    if isinstance(nav_series, list):
        nav_series = pd.Series(nav_series)
    returns = nav_series.pct_change().dropna()
    returns.index = pd.to_datetime(returns.index)
    return returns


# ============================================================
# matplotlib 中文字体配置
# ============================================================

_matplotlib_chinese_configured = False


def configure_matplotlib_chinese():
    """
    注册本机中文字体文件并写入 rcParams，避免仅写字体名时匹配失败（方框/乱码）。
    macOS 下优先 PingFang SC，其次 Arial Unicode MS。
    """
    global _matplotlib_chinese_configured
    if _matplotlib_chinese_configured:
        return

    import platform
    import matplotlib
    from matplotlib import font_manager as fm

    font_paths = []
    if platform.system() == 'Darwin':
        # macOS 系统字体目录
        mac_font_dirs = [
            '/System/Library/Fonts',
            '/Library/Fonts',
            os.path.expanduser('~/Library/Fonts'),
        ]
        for font_dir in mac_font_dirs:
            for fname in ('PingFang.ttc', 'PingFang SC.ttc',
                          'Arial Unicode.ttf', 'STHeiti Light.ttc',
                          'Songti.ttc', 'Heiti.ttc'):
                fp = os.path.join(font_dir, fname)
                if os.path.isfile(fp):
                    font_paths.append(fp)
    elif platform.system() == 'Windows':
        font_dir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
        for fname in ('msyh.ttc', 'msyhbd.ttc', 'simhei.ttf', 'simsun.ttc',
                      'STSONG.TTF', 'STHEITI.TTF'):
            fp = os.path.join(font_dir, fname)
            if os.path.isfile(fp):
                font_paths.append(fp)

    registered_name = None
    for fp in font_paths:
        try:
            fm.fontManager.addfont(fp)
            registered_name = fm.FontProperties(fname=fp).get_name()
            break
        except Exception:
            continue

    fallback = ['PingFang SC', 'Microsoft YaHei', 'SimHei', 'SimSun',
                'Arial Unicode MS', 'DejaVu Sans']
    if registered_name:
        matplotlib.rcParams['font.sans-serif'] = [registered_name] + fallback
    else:
        matplotlib.rcParams['font.sans-serif'] = fallback
    matplotlib.rcParams['axes.unicode_minus'] = False
    _matplotlib_chinese_configured = True


# ============================================================
# QuantStats 指标计算
# ============================================================

def calc_quantstats_metrics(returns, benchmark=None):
    """
    计算 QuantStats 全量绩效指标

    参数:
        returns: Series, 日收益率序列
        benchmark: Series, 基准日收益率(可选)

    返回:
        dict, 所有绩效指标
    """
    returns = returns.copy()
    returns.index = pd.to_datetime(returns.index)
    # 确保是收益率序列(非累计净值)
    if returns.mean() > 1:
        returns = returns.pct_change().dropna()

    metrics = {}

    def _safe(func, *args, default=0.0, **kwargs):
        """安全调用 quantstats 函数，失败时返回默认值"""
        try:
            val = func(*args, **kwargs)
            if val is None or (isinstance(val, float) and (np.isinf(val) or np.isnan(val))):
                return default
            return val
        except Exception:
            return default

    # -- 收益指标 --
    try:
        metrics['total_return'] = qs.stats.comp(returns)
    except Exception:
        metrics['total_return'] = 0.0
    try:
        metrics['cagr'] = qs.stats.cagr(returns)
    except Exception:
        metrics['cagr'] = 0.0
    try:
        metrics['best_day'] = returns.max()
    except Exception:
        metrics['best_day'] = 0.0
    try:
        metrics['worst_day'] = returns.min()
    except Exception:
        metrics['worst_day'] = 0.0

    # -- 风险指标 --
    try:
        metrics['volatility'] = qs.stats.volatility(returns)
    except Exception:
        metrics['volatility'] = 0.0
    try:
        metrics['max_drawdown'] = qs.stats.max_drawdown(returns)
    except Exception:
        metrics['max_drawdown'] = 0.0
    try:
        metrics['var_95'] = qs.stats.value_at_risk(returns)
    except Exception:
        metrics['var_95'] = 0.0
    try:
        metrics['cvar_95'] = qs.stats.cvar(returns)
    except Exception:
        metrics['cvar_95'] = 0.0

    # -- 风险调整收益 --
    metrics['sharpe'] = _safe(qs.stats.sharpe, returns)
    metrics['sortino'] = _safe(qs.stats.sortino, returns)
    metrics['calmar'] = _safe(qs.stats.calmar, returns)
    metrics['omega'] = _safe(qs.stats.omega, returns, default=1.0)
    metrics['gain_to_pain'] = _safe(qs.stats.gain_to_pain_ratio, returns)

    # -- 分布特征 --
    metrics['skew'] = _safe(qs.stats.skew, returns)
    metrics['kurtosis'] = _safe(qs.stats.kurtosis, returns)

    # -- 胜率统计 --
    metrics['win_rate'] = _safe(qs.stats.win_rate, returns, default=0.5)
    metrics['avg_win'] = _safe(qs.stats.avg_win, returns)
    metrics['avg_loss'] = _safe(qs.stats.avg_loss, returns)
    metrics['profit_factor'] = _safe(qs.stats.profit_factor, returns, default=1.0)
    metrics['payoff_ratio'] = _safe(qs.stats.payoff_ratio, returns, default=1.0)

    # -- 连续统计 --
    metrics['consecutive_wins'] = _safe(qs.stats.consecutive_wins, returns, default=0)
    metrics['consecutive_losses'] = _safe(qs.stats.consecutive_losses, returns, default=0)

    # -- 基准相关(如果提供) --
    if benchmark is not None:
        try:
            benchmark = qs.utils.make_index(benchmark)
            benchmark.index = pd.to_datetime(benchmark.index)
            common_idx = returns.index.intersection(benchmark.index)
            if len(common_idx) > 20:
                r = returns.loc[common_idx]
                b = benchmark.loc[common_idx]
                try:
                    metrics['information_ratio'] = qs.stats.information_ratio(r, b)
                except Exception:
                    metrics['information_ratio'] = 0.0
                try:
                    metrics['alpha'] = r.mean() * 252 - b.mean() * 252
                except Exception:
                    metrics['alpha'] = 0.0
                try:
                    cov = np.cov(r.values, b.values)
                    if cov[1, 1] > 0:
                        metrics['beta'] = cov[0, 1] / cov[1, 1]
                    else:
                        metrics['beta'] = 0.0
                except Exception:
                    metrics['beta'] = 0.0
                try:
                    metrics['tracking_error'] = (r - b).std() * np.sqrt(252)
                except Exception:
                    metrics['tracking_error'] = 0.0
        except Exception:
            pass

    return metrics


# ============================================================
# 中文 HTML 报告生成
# ============================================================

def generate_chinese_report(returns, benchmark=None, title='策略绩效报告',
                            output_path=None):
    """
    生成完全中文化的策略绩效分析报告 (自主渲染, 全中文)

    使用 QuantStats 函数计算指标数据,
    所有图表使用 matplotlib 自主渲染(中文字体),
    所有表格和标签均为中文, 不依赖 QuantStats HTML 模板。

    参数:
        returns: Series, 日收益率序列
        benchmark: Series, 基准日收益率(可选)
        title: str, 报告标题
        output_path: str, 输出文件路径(默认保存到 backend/static/reports/)

    返回:
        str, 输出文件路径
    """
    import base64
    from io import BytesIO
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    configure_matplotlib_chinese()

    # 默认输出目录
    if output_path is None:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        reports_dir = os.path.join(project_root, 'static', 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        from datetime import datetime
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(reports_dir, f'quantstats_{ts}.html')

    os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    returns = returns.copy()
    returns.index = pd.to_datetime(returns.index)

    bench = None
    if benchmark is not None and isinstance(benchmark, pd.Series):
        bench = benchmark.copy()
        bench.index = pd.to_datetime(bench.index)
        common = returns.index.intersection(bench.index)
        if len(common) > 0:
            bench = bench.loc[common]
        else:
            bench = None

    metrics = calc_quantstats_metrics(returns, benchmark=bench)

    def _fig_to_b64(fig):
        """将 matplotlib 图表转为 base64 编码"""
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=130, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('ascii')

    charts = {}

    # ---- 图1: 累计收益曲线 ----
    fig, ax = plt.subplots(figsize=(14, 5))
    cum = (1 + returns).cumprod()
    ax.plot(cum.index, cum.values, '#2980b9', linewidth=1.5, label='策略')
    if bench is not None:
        cum_b = (1 + bench).cumprod()
        ci = cum.index.intersection(cum_b.index)
        if len(ci) > 0:
            ax.plot(ci, cum_b.loc[ci].values, '#95a5a6', linewidth=1,
                    label='基准', alpha=0.7)
    ax.axhline(y=1.0, color='red', linestyle='--', alpha=0.3)
    ax.set_title('累计收益曲线', fontsize=14, fontweight='bold')
    ax.set_ylabel('累计净值')
    ax.set_xlabel('日期')
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3)
    charts['cumulative'] = _fig_to_b64(fig)

    # ---- 图2: 回撤水下图 ----
    fig, ax = plt.subplots(figsize=(14, 4))
    peak = cum.cummax()
    dd = (cum - peak) / peak
    ax.fill_between(dd.index, dd.values, 0, color='#e74c3c', alpha=0.4)
    ax.plot(dd.index, dd.values, '#c0392b', linewidth=0.8)
    ax.set_title('水下图(回撤)', fontsize=14, fontweight='bold')
    ax.set_ylabel('回撤幅度')
    ax.set_xlabel('日期')
    ax.grid(True, alpha=0.3)
    charts['drawdown'] = _fig_to_b64(fig)

    # ---- 图3: 月度收益热力图 ----
    monthly = returns.resample('ME').apply(lambda x: (1 + x).prod() - 1)
    m_df = pd.DataFrame({
        'year': monthly.index.year,
        'month': monthly.index.month,
        'ret': monthly.values,
    })
    if not m_df.empty and len(m_df) > 1:
        pivot = m_df.pivot_table(values='ret', index='year',
                                  columns='month', aggfunc='first')
        mn = {1: '1月', 2: '2月', 3: '3月', 4: '4月', 5: '5月', 6: '6月',
              7: '7月', 8: '8月', 9: '9月', 10: '10月', 11: '11月', 12: '12月'}
        pivot.columns = [mn.get(c, c) for c in pivot.columns]
        fig, ax = plt.subplots(figsize=(14, max(3, len(pivot) * 0.8 + 1)))
        im = ax.imshow(pivot.values, cmap='RdYlGn', aspect='auto',
                       vmin=-0.1, vmax=0.1)
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, fontsize=10)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index, fontsize=10)
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot.values[i, j]
                if not np.isnan(val):
                    ax.text(j, i, f'{val:.1%}', ha='center', va='center',
                            fontsize=9, color='black')
        ax.set_title('月度收益热力图', fontsize=14, fontweight='bold')
        fig.colorbar(im, ax=ax, shrink=0.6)
        charts['monthly_heatmap'] = _fig_to_b64(fig)

    # ---- 图4: 日收益分布 ----
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.hist(returns.dropna().values, bins=50, color='#3498db', alpha=0.7,
            edgecolor='white')
    ax.axvline(x=0, color='red', linestyle='--', alpha=0.5)
    ax.axvline(x=returns.mean(), color='green', linestyle='--', alpha=0.7,
               label=f'均值: {returns.mean():.4%}')
    ax.set_title('日收益分布', fontsize=14, fontweight='bold')
    ax.set_xlabel('日收益率')
    ax.set_ylabel('频次')
    ax.legend()
    ax.grid(True, alpha=0.3)
    charts['distribution'] = _fig_to_b64(fig)

    # ---- 图5: 滚动夏普 + 滚动波动率 ----
    if len(returns) > 60:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7))
        rs = returns.rolling(60).apply(
            lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
        )
        ax1.plot(rs.index, rs.values, '#2980b9', linewidth=1)
        ax1.axhline(y=0, color='red', linestyle='--', alpha=0.3)
        ax1.set_title('滚动夏普比率(60日)', fontsize=13, fontweight='bold')
        ax1.set_ylabel('夏普比率')
        ax1.grid(True, alpha=0.3)
        rv = returns.rolling(20).std() * np.sqrt(252)
        ax2.plot(rv.index, rv.values, '#e74c3c', linewidth=1)
        ax2.set_title('滚动波动率(20日)', fontsize=13, fontweight='bold')
        ax2.set_ylabel('年化波动率')
        ax2.set_xlabel('日期')
        ax2.grid(True, alpha=0.3)
        plt.tight_layout()
        charts['rolling'] = _fig_to_b64(fig)

    # ---- 图6: 年度收益柱状图 ----
    yearly = returns.resample('YE').apply(lambda x: (1 + x).prod() - 1)
    if len(yearly) > 0:
        fig, ax = plt.subplots(figsize=(10, 4))
        colors_bar = ['#27ae60' if v >= 0 else '#e74c3c' for v in yearly.values]
        bars = ax.bar(yearly.index.year, yearly.values * 100,
                      color=colors_bar, width=0.6)
        for bar, val in zip(bars, yearly.values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    f'{val:.1%}', ha='center',
                    va='bottom' if val >= 0 else 'top', fontsize=10)
        ax.set_title('年度收益', fontsize=14, fontweight='bold')
        ax.set_ylabel('收益率 (%)')
        ax.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
        ax.grid(True, alpha=0.3, axis='y')
        charts['yearly'] = _fig_to_b64(fig)

    # ---- 计算 Top 5 回撤区间 ----
    dd_periods = []
    in_dd = False
    start_d = None
    for date, val in dd.items():
        if val < 0 and not in_dd:
            start_d = date
            in_dd = True
        elif val >= 0 and in_dd:
            valley_idx = dd[start_d:date].idxmin()
            valley_val = dd[start_d:date].min()
            dd_periods.append({
                'start': start_d, 'valley': valley_idx, 'end': date,
                'drawdown': valley_val, 'days': (date - start_d).days,
            })
            in_dd = False
    if in_dd and start_d is not None:
        valley_idx = dd[start_d:].idxmin()
        valley_val = dd[start_d:].min()
        dd_periods.append({
            'start': start_d, 'valley': valley_idx, 'end': dd.index[-1],
            'drawdown': valley_val, 'days': (dd.index[-1] - start_d).days,
            'ongoing': True,
        })
    dd_periods.sort(key=lambda x: x['drawdown'])
    top_dd = dd_periods[:5]

    # ---- 月度收益表格 ----
    monthly_table_html = ''
    if not m_df.empty:
        pivot_raw = m_df.pivot_table(values='ret', index='year',
                                      columns='month', aggfunc='first')
        eoy = returns.resample('YE').apply(lambda x: (1 + x).prod() - 1)
        eoy_dict = {y.year: v for y, v in eoy.items()}
        monthly_table_html = '<table class="data-table"><tr><th>年份</th>'
        for m in range(1, 13):
            monthly_table_html += f'<th>{m}月</th>'
        monthly_table_html += '<th>全年</th></tr>'
        for year in sorted(pivot_raw.index):
            monthly_table_html += f'<tr><td style="font-weight:bold">{year}</td>'
            for m in range(1, 13):
                cell_val = None
                if m in pivot_raw.columns:
                    raw_val = pivot_raw.loc[year, m]
                    if not pd.isna(raw_val):
                        cell_val = raw_val
                if cell_val is not None:
                    c = '#27ae60' if cell_val >= 0 else '#e74c3c'
                    monthly_table_html += f'<td style="color:{c}">{cell_val:.1%}</td>'
                else:
                    monthly_table_html += '<td>-</td>'
            eoy_val = eoy_dict.get(year, None)
            if eoy_val is not None:
                ec = '#27ae60' if eoy_val >= 0 else '#e74c3c'
                monthly_table_html += (
                    f'<td style="font-weight:bold;color:{ec}">{eoy_val:.1%}</td>')
            else:
                monthly_table_html += '<td>-</td>'
            monthly_table_html += '</tr>'
        monthly_table_html += '</table>'

    # ---- 绩效指标表格 ----
    start_date = returns.index[0].strftime('%Y-%m-%d')
    end_date = returns.index[-1].strftime('%Y-%m-%d')
    trading_days = len(returns)

    metric_rows = [
        ('开始日期', start_date),
        ('结束日期', end_date),
        ('---', ''),
        ('累计收益', f'{metrics.get("total_return", 0):.2%}'),
        ('年化收益(CAGR)', f'{metrics.get("cagr", 0):.2%}'),
        ('年化波动率', f'{metrics.get("volatility", 0):.2%}'),
        ('---', ''),
        ('夏普比率', f'{metrics.get("sharpe", 0):.4f}'),
        ('索提诺比率', f'{metrics.get("sortino", 0):.4f}'),
        ('卡玛比率', f'{metrics.get("calmar", 0):.4f}'),
        ('欧米伽比率', f'{metrics.get("omega", 1):.4f}'),
        ('盈亏比(Gain/Pain)', f'{metrics.get("gain_to_pain", 0):.4f}'),
        ('---', ''),
        ('最大回撤', f'{metrics.get("max_drawdown", 0):.2%}'),
        ('VaR(95%)', f'{metrics.get("var_95", 0):.2%}'),
        ('CVaR(95%)', f'{metrics.get("cvar_95", 0):.2%}'),
        ('---', ''),
        ('最佳单日', f'{metrics.get("best_day", 0):.2%}'),
        ('最差单日', f'{metrics.get("worst_day", 0):.2%}'),
        ('日胜率', f'{metrics.get("win_rate", 0):.2%}'),
        ('平均盈利', f'{metrics.get("avg_win", 0):.4%}'),
        ('平均亏损', f'{metrics.get("avg_loss", 0):.4%}'),
        ('利润因子', f'{metrics.get("profit_factor", 0):.4f}'),
        ('赔付比率', f'{metrics.get("payoff_ratio", 0):.4f}'),
        ('最大连胜', f'{metrics.get("consecutive_wins", 0):.0f}'),
        ('最大连亏', f'{metrics.get("consecutive_losses", 0):.0f}'),
        ('---', ''),
        ('偏度(Skew)', f'{metrics.get("skew", 0):.4f}'),
        ('峰度(Kurtosis)', f'{metrics.get("kurtosis", 0):.4f}'),
    ]
    if bench is not None:
        metric_rows.append(('---', ''))
        if 'alpha' in metrics:
            metric_rows.append(('Alpha(年化超额)', f'{metrics["alpha"]:.2%}'))
        if 'beta' in metrics:
            metric_rows.append(('Beta(贝塔)', f'{metrics["beta"]:.4f}'))
        if 'information_ratio' in metrics:
            metric_rows.append(('信息比率', f'{metrics["information_ratio"]:.4f}'))
        if 'tracking_error' in metrics:
            metric_rows.append(('跟踪误差', f'{metrics["tracking_error"]:.2%}'))

    metrics_html = '<table class="metrics-table">'
    metrics_html += '<tr><th style="width:45%">指标</th><th style="width:55%">数值</th></tr>'
    for label, value in metric_rows:
        if label == '---':
            metrics_html += ('<tr><td colspan="2" style="border-bottom:2px solid '
                             '#eee;padding:2px;"></td></tr>')
        else:
            metrics_html += f'<tr><td>{label}</td><td>{value}</td></tr>'
    metrics_html += '</table>'

    # ---- 回撤区间表格 ----
    dd_table_html = ''
    if top_dd:
        dd_table_html = ('<table class="data-table"><tr><th>序号</th>'
                         '<th>开始日期</th><th>谷底日期</th><th>恢复日期</th>'
                         '<th>回撤幅度</th><th>持续天数</th></tr>')
        for i, d in enumerate(top_dd, 1):
            ongoing = d.get('ongoing', False)
            end_str = '未恢复' if ongoing else d['end'].strftime('%Y-%m-%d')
            dd_table_html += (
                f'<tr><td>{i}</td>'
                f'<td>{d["start"].strftime("%Y-%m-%d")}</td>'
                f'<td>{d["valley"].strftime("%Y-%m-%d")}</td>'
                f'<td>{end_str}</td>'
                f'<td style="color:#e74c3c;font-weight:bold">{d["drawdown"]:.2%}</td>'
                f'<td>{d["days"]}</td></tr>')
        dd_table_html += '</table>'

    # ---- 组装 HTML ----
    total_return = metrics.get('total_return', 0)
    cagr = metrics.get('cagr', 0)
    max_dd = metrics.get('max_drawdown', 0)
    sharpe = metrics.get('sharpe', 0)
    sortino = metrics.get('sortino', 0)
    calmar = metrics.get('calmar', 0)
    win_rate = metrics.get('win_rate', 0)
    volatility = metrics.get('volatility', 0)

    def _vc(v, reverse=False):
        """根据正负值返回颜色"""
        if reverse:
            return '#27ae60' if v <= 0 else '#e74c3c'
        return '#27ae60' if v >= 0 else '#e74c3c'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: "PingFang SC","Microsoft YaHei","SimHei",sans-serif;
         background: #f0f2f5; color: #2c3e50; }}
  .container {{ max-width: 1100px; margin: 0 auto; background: white;
               box-shadow: 0 4px 20px rgba(0,0,0,0.08); }}
  .header {{ background: linear-gradient(135deg, #1a2a3a 0%, #2980b9 100%);
            color: white; padding: 40px 50px; }}
  .header h1 {{ font-size: 28px; margin-bottom: 8px; }}
  .header .sub {{ font-size: 14px; color: rgba(255,255,255,0.7); }}
  .metric-cards {{ display: flex; flex-wrap: wrap; gap: 12px;
                   padding: 24px 40px; background: #fafbfc;
                   border-bottom: 1px solid #eee; }}
  .card {{ flex: 1; min-width: 120px; max-width: 200px; background: white;
          border-radius: 8px; padding: 16px; text-align: center;
          box-shadow: 0 1px 4px rgba(0,0,0,0.06);
          border-top: 3px solid #3498db; }}
  .card .val {{ font-size: 22px; font-weight: bold; margin: 4px 0; }}
  .card .lbl {{ font-size: 11px; color: #7f8c8d; }}
  .section {{ padding: 30px 40px; border-bottom: 1px solid #f0f0f0; }}
  .section h2 {{ font-size: 18px; color: #2c3e50; margin-bottom: 16px;
                padding-bottom: 8px; border-bottom: 2px solid #3498db; }}
  .chart-box {{ text-align: center; margin: 16px 0; }}
  .chart-box img {{ max-width: 100%; border-radius: 6px;
                    border: 1px solid #e8e8e8; }}
  .metrics-table {{ width: 100%; border-collapse: collapse; }}
  .metrics-table th {{ background: #34495e; color: white; padding: 10px 16px;
                       text-align: left; font-size: 13px; }}
  .metrics-table td {{ padding: 8px 16px; border-bottom: 1px solid #f0f0f0;
                       font-size: 13px; }}
  .metrics-table tr:hover {{ background: #f8f9fa; }}
  .data-table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
  .data-table th {{ background: #34495e; color: white; padding: 10px 12px;
                    text-align: center; font-size: 12px; }}
  .data-table td {{ padding: 8px 12px; border-bottom: 1px solid #f0f0f0;
                    text-align: center; font-size: 12px; }}
  .data-table tr:hover {{ background: #f8f9fa; }}
  .footer {{ text-align: center; padding: 20px; color: #95a5a6;
            font-size: 11px; background: #fafbfc; }}
  @media (max-width: 768px) {{
    .metric-cards {{ flex-direction: column; }}
    .section {{ padding: 20px; }}
    .header {{ padding: 24px; }}
  }}
</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>{title}</h1>
  <div class="sub">{start_date} ~ {end_date} | 共 {trading_days} 个交易日 | 报告生成: {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}</div>
</div>

<div class="metric-cards">
  <div class="card">
    <div class="lbl">累计收益</div>
    <div class="val" style="color:{_vc(total_return)}">{total_return:.2%}</div>
  </div>
  <div class="card">
    <div class="lbl">年化收益(CAGR)</div>
    <div class="val" style="color:{_vc(cagr)}">{cagr:.2%}</div>
  </div>
  <div class="card">
    <div class="lbl">最大回撤</div>
    <div class="val" style="color:#e74c3c">{max_dd:.2%}</div>
  </div>
  <div class="card">
    <div class="lbl">夏普比率</div>
    <div class="val" style="color:{_vc(sharpe)}">{sharpe:.2f}</div>
  </div>
  <div class="card">
    <div class="lbl">索提诺比率</div>
    <div class="val" style="color:{_vc(sortino)}">{sortino:.2f}</div>
  </div>
  <div class="card">
    <div class="lbl">年化波动率</div>
    <div class="val">{volatility:.2%}</div>
  </div>
  <div class="card">
    <div class="lbl">日胜率</div>
    <div class="val">{win_rate:.1%}</div>
  </div>
  <div class="card">
    <div class="lbl">卡玛比率</div>
    <div class="val" style="color:{_vc(calmar)}">{calmar:.2f}</div>
  </div>
</div>

<div class="section">
  <h2>累计收益曲线</h2>
  <div class="chart-box">
    <img src="data:image/png;base64,{charts['cumulative']}" alt="累计收益">
  </div>
</div>

<div class="section">
  <h2>水下图(回撤)</h2>
  <div class="chart-box">
    <img src="data:image/png;base64,{charts['drawdown']}" alt="回撤">
  </div>
</div>
'''

    if 'yearly' in charts:
        html += f'''
<div class="section">
  <h2>年度收益</h2>
  <div class="chart-box">
    <img src="data:image/png;base64,{charts['yearly']}" alt="年度收益">
  </div>
</div>
'''

    if 'monthly_heatmap' in charts:
        html += f'''
<div class="section">
  <h2>月度收益热力图</h2>
  <div class="chart-box">
    <img src="data:image/png;base64,{charts['monthly_heatmap']}" alt="月度热力图">
  </div>
</div>
'''

    html += f'''
<div class="section">
  <h2>日收益分布</h2>
  <div class="chart-box">
    <img src="data:image/png;base64,{charts['distribution']}" alt="日收益分布">
  </div>
</div>
'''

    if 'rolling' in charts:
        html += f'''
<div class="section">
  <h2>滚动风险指标</h2>
  <div class="chart-box">
    <img src="data:image/png;base64,{charts['rolling']}" alt="滚动指标">
  </div>
</div>
'''

    html += f'''
<div class="section">
  <h2>绩效指标明细</h2>
  {metrics_html}
</div>
'''

    if monthly_table_html:
        html += f'''
<div class="section">
  <h2>月度收益明细</h2>
  {monthly_table_html}
</div>
'''

    if dd_table_html:
        html += f'''
<div class="section">
  <h2>Top {len(top_dd)} 回撤区间</h2>
  {dd_table_html}
</div>
'''

    html += '''
<div class="footer">
  <p>本报告基于 QuantStats 计算引擎自主渲染生成 | 仅供参考, 不构成投资建议</p>
</div>

</div>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8-sig') as f:
        f.write(html)

    return output_path


# ============================================================
# 指标卡片 / 表格 HTML 生成
# ============================================================

def metrics_to_html_cards(metrics, card_keys=None):
    """
    将指标 dict 转为 HTML 卡片展示

    参数:
        metrics: dict, 绩效指标字典
        card_keys: list, 需要展示的指标键名列表

    返回:
        str, HTML 内容
    """
    if card_keys is None:
        card_keys = ['total_return', 'cagr', 'max_drawdown', 'sharpe',
                     'sortino', 'calmar', 'win_rate', 'profit_factor']

    label_map = {
        'total_return': '总收益率',
        'cagr': '年化收益(CAGR)',
        'max_drawdown': '最大回撤',
        'sharpe': '夏普比率',
        'sortino': '索提诺比率',
        'calmar': '卡玛比率',
        'omega': 'Omega比率',
        'volatility': '年化波动率',
        'win_rate': '日胜率',
        'profit_factor': '利润因子',
        'var_95': 'VaR(95%)',
        'cvar_95': 'CVaR(95%)',
    }

    fmt_pct = {'total_return', 'cagr', 'max_drawdown', 'volatility',
               'win_rate', 'var_95', 'cvar_95'}

    html = '<div style="margin:15px 0;">'
    for key in card_keys:
        if key not in metrics or metrics[key] is None:
            continue
        val = float(metrics[key])
        label = label_map.get(key, key)
        if key in fmt_pct:
            val_str = f'{val:.2%}'
        else:
            val_str = f'{val:.4f}'
        html += f'<div class="metric-card"><div class="value">{val_str}</div><div class="label">{label}</div></div>'
    html += '</div>'
    return html


def metrics_to_html_table(metrics):
    """
    将指标 dict 转为 HTML 表格

    参数:
        metrics: dict, 绩效指标字典

    返回:
        str, HTML 内容
    """
    label_map = {
        'total_return': ('总收益率', True),
        'cagr': ('年化收益率(CAGR)', True),
        'volatility': ('年化波动率', True),
        'max_drawdown': ('最大回撤', True),
        'sharpe': ('夏普比率', False),
        'sortino': ('索提诺比率', False),
        'calmar': ('卡玛比率', False),
        'omega': ('Omega比率', False),
        'gain_to_pain': ('盈亏比', False),
        'var_95': ('VaR(95%)', True),
        'cvar_95': ('CVaR(95%)', True),
        'skew': ('偏度', False),
        'kurtosis': ('峰度', False),
        'win_rate': ('日胜率', True),
        'profit_factor': ('利润因子', False),
        'best_day': ('最佳单日', True),
        'worst_day': ('最差单日', True),
        'alpha': ('Alpha', True),
        'beta': ('Beta', False),
        'information_ratio': ('信息比率', False),
        'tracking_error': ('跟踪误差', True),
    }

    html = '<table><tr><th>指标</th><th>数值</th></tr>'
    for key, (label, is_pct) in label_map.items():
        if key not in metrics or metrics[key] is None:
            continue
        val = float(metrics[key])
        val_str = f'{val:.2%}' if is_pct else f'{val:.4f}'
        html += f'<tr><td>{label}</td><td>{val_str}</td></tr>'
    html += '</table>'
    return html


# ============================================================
# 数据库股票数据加载
# ============================================================

def load_stock_data_from_db(stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从数据库加载单只股票的日线数据

    查询 trade_stock_daily 表，返回包含 trade_date 和 close_price 列的 DataFrame。

    参数:
        stock_code: 股票代码，如 "600519.SH"
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    返回:
        pd.DataFrame, 包含 trade_date, close_price 列，按日期升序排列
    """
    from core.db import connect, load_mysql_config, query_dict

    try:
        cfg = load_mysql_config()
        conn = connect(cfg)
    except Exception as e:
        return pd.DataFrame()

    try:
        rows = query_dict(
            conn,
            """
            SELECT trade_date, close_price
            FROM trade_stock_daily
            WHERE stock_code = %s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
            """,
            (stock_code, start_date, end_date),
        )
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df["close_price"] = pd.to_numeric(df["close_price"], errors="coerce")
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df = df.dropna(subset=["close_price"])
        return df
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()


# ============================================================
# SVD 市场状态诊断
# ============================================================

def diagnose_market_regime(
    stock_codes: list[str],
    start_date: str,
    end_date: str,
    window: int = 60,
    step: int = 10,
) -> dict:
    """
    SVD 市场状态诊断

    通过对多只股票的日收益率矩阵进行滚动 SVD 分解，
    判断当前市场状态：齐涨齐跌 / 板块分化 / 个股行情。

    原理:
      - 构建多只股票的日收益率矩阵（股票 x 日期）
      - 对滚动窗口内的收益率矩阵做 SVD 分解
      - 计算第一主成分方差占比（top1_var_ratio）：
        > 50% 表示齐涨齐跌，35%-50% 表示板块分化，< 35% 表示个股行情
      - 同时计算前三个主成分累计方差占比（top3_var_ratio）

    参数:
        stock_codes: 股票代码列表，如 ["600519.SH", "000858.SZ"]
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        window: 滚动窗口天数，默认 60
        step: 滚动步长天数，默认 10

    返回:
        dict, 诊断结果，包含:
          - current_state: 当前市场状态 ("齐涨齐跌"/"板块分化"/"个股行情")
          - current_f1_ratio: 当前第一主成分方差占比
          - advice: 投资建议
          - rolling_data: 滚动诊断数据列表
          - stock_count: 参与诊断的股票数量
          - data_days: 数据覆盖的交易日数
    """
    if not stock_codes or len(stock_codes) < 3:
        return {
            "current_state": "数据不足",
            "current_f1_ratio": 0.0,
            "advice": "SVD 诊断至少需要 3 只股票的数据，当前数量不足",
            "rolling_data": [],
            "stock_count": len(stock_codes),
            "data_days": 0,
        }

    # 加载所有股票的日收益率数据
    returns_dict: dict[str, pd.Series] = {}
    for code in stock_codes:
        df = load_stock_data_from_db(code, start_date, end_date)
        if df.empty or len(df) < 2:
            continue
        df = df.sort_values("trade_date").reset_index(drop=True)
        # 计算日收益率
        returns = df["close_price"].pct_change().dropna()
        returns.index = df["trade_date"].iloc[1:]
        returns_dict[code] = returns

    if len(returns_dict) < 3:
        return {
            "current_state": "数据不足",
            "current_f1_ratio": 0.0,
            "advice": f"有效数据股票数量不足（需要至少3只，实际{len(returns_dict)}只）",
            "rolling_data": [],
            "stock_count": len(returns_dict),
            "data_days": 0,
        }

    # 构建收益率矩阵：行=股票，列=日期
    returns_df = pd.DataFrame(returns_dict)
    # 对齐日期：取所有股票共有的交易日
    returns_df = returns_df.dropna()
    if returns_df.empty or len(returns_df) < window:
        return {
            "current_state": "数据不足",
            "current_f1_ratio": 0.0,
            "advice": f"有效交易日数据不足（需要至少{window}天，实际{len(returns_df)}天）",
            "rolling_data": [],
            "stock_count": len(returns_dict),
            "data_days": len(returns_df),
        }

    # 转置：行=日期，列=股票，便于滚动窗口处理
    returns_matrix = returns_df.T  # 行=股票，列=日期

    dates = returns_df.index
    total_days = len(dates)
    data_days = total_days

    # 滚动 SVD 分解
    rolling_data: list[dict] = []
    n_stocks = returns_matrix.shape[0]

    for i in range(window - 1, total_days, step):
        window_dates = dates[i - window + 1: i + 1]
        # 取窗口内的收益率子矩阵（股票 x 日期）
        window_data = returns_matrix[window_dates].values

        # 标准化：每只股票减去均值，除以标准差
        means = window_data.mean(axis=1, keepdims=True)
        stds = window_data.std(axis=1, keepdims=True)
        stds[stds == 0] = 1.0  # 避免除零
        normalized = (window_data - means) / stds

        # SVD 分解
        try:
            U, S, Vt = np.linalg.svd(normalized, full_matrices=False)
        except Exception:
            continue

        # 计算方差占比
        total_var = np.sum(S ** 2)
        if total_var == 0:
            continue

        top1_var = (S[0] ** 2) / total_var
        top3_var = np.sum(S[:min(3, len(S))] ** 2) / total_var

        # 判断市场状态
        if top1_var > 0.50:
            state = "齐涨齐跌"
        elif top1_var >= 0.35:
            state = "板块分化"
        else:
            state = "个股行情"

        # 使用窗口最后一个日期作为该窗口的日期标签
        date_label = window_dates[-1]
        if hasattr(date_label, "strftime"):
            date_str = date_label.strftime("%Y-%m")
        else:
            date_str = str(date_label)[:7]

        rolling_data.append({
            "date": date_str,
            "top1_var": round(float(top1_var), 4),
            "top3_var": round(float(top3_var), 4),
            "state": state,
        })

    if not rolling_data:
        return {
            "current_state": "计算失败",
            "current_f1_ratio": 0.0,
            "advice": "滚动 SVD 计算未能产生有效结果",
            "rolling_data": [],
            "stock_count": len(returns_dict),
            "data_days": data_days,
        }

    # 取最后一个窗口的结果作为当前状态
    current = rolling_data[-1]
    current_state = current["state"]
    current_f1_ratio = current["top1_var"]

    # 根据市场状态生成投资建议
    advice_map = {
        "齐涨齐跌": (
            "当前市场呈现齐涨齐跌特征，第一主成分解释力度强，"
            "个股走势高度趋同。建议：1) 跟随大盘趋势操作，指数基金或宽基ETF是较好选择；"
            "2) 个股选择的重要性降低，仓位管理更关键；"
            "3) 注意系统性风险，市场转向时个股难以独善其身。"
        ),
        "板块分化": (
            "当前市场呈现板块分化特征，存在明显的行业轮动。"
            "建议：1) 重视行业/板块配置，选择强势板块龙头股；"
            "2) 关注资金流向和板块轮动节奏；"
            "3) 避免在弱势板块中逆势操作，顺势而为更有效。"
        ),
        "个股行情": (
            "当前市场呈现个股行情特征，个股走势分化明显，"
            "板块效应弱化。建议：1) 精选个股比行业配置更重要；"
            "2) 重视公司基本面和个股催化剂；"
            "3) 分散投资降低个股风险，避免过度集中持仓；"
            "4) 适合量化选股和事件驱动策略。"
        ),
    }
    advice = advice_map.get(current_state, "暂无投资建议")

    return {
        "current_state": current_state,
        "current_f1_ratio": current_f1_ratio,
        "advice": advice,
        "rolling_data": rolling_data,
        "stock_count": len(returns_dict),
        "data_days": data_days,
    }


# ============================================================
# 交易成本分析
# ============================================================

def analyze_trading_costs(
    trades: list[dict],
    commission_rate: float = 0.0003,
    stamp_duty_rate: float = 0.001,
    transfer_fee_rate: float = 0.00001,
) -> dict:
    """
    交易成本分析

    根据交易记录列表和费率参数，计算每笔交易的佣金、印花税、过户费，
    并汇总返回各项成本总额和成本占比。

    参数:
        trades: 交易记录列表，每条记录应包含:
            - action: "buy" 或 "sell"
            - price: 成交价格
            - size: 成交数量
        commission_rate: 佣金费率，默认万三 (0.0003)
        stamp_duty_rate: 印花税费率，仅卖出时收取，默认千一 (0.001)
        transfer_fee_rate: 过户费率，买卖均收取，默认十万分之一 (0.00001)

    返回:
        dict, 包含:
          - total_turnover: 总成交额
          - buy_turnover: 买入成交额
          - sell_turnover: 卖出成交额
          - commission: 佣金总额
          - stamp_tax: 印花税总额
          - transfer_fee: 过户费总额
          - total_cost: 总交易成本
          - cost_ratio: 成本占总成交额比例
          - details: 每笔交易的成本明细
    """
    if not trades:
        return {
            "total_turnover": 0.0,
            "buy_turnover": 0.0,
            "sell_turnover": 0.0,
            "commission": 0.0,
            "stamp_tax": 0.0,
            "transfer_fee": 0.0,
            "total_cost": 0.0,
            "cost_ratio": 0.0,
            "details": [],
        }

    min_commission = 5.0  # 最低佣金5元
    total_turnover = 0.0
    buy_turnover = 0.0
    sell_turnover = 0.0
    total_commission = 0.0
    total_stamp_tax = 0.0
    total_transfer_fee = 0.0
    details: list[dict] = []

    for trade in trades:
        action = str(trade.get("action", "")).lower()
        price = float(trade.get("price", 0))
        size = int(trade.get("size", 0))

        if size <= 0 or price <= 0:
            continue

        amount = price * size
        total_turnover += amount

        # 计算佣金（最低5元）
        commission = max(amount * commission_rate, min_commission)

        # 计算印花税（仅卖出）
        stamp_tax = amount * stamp_duty_rate if action == "sell" else 0.0

        # 计算过户费（买卖均收）
        transfer_fee = amount * transfer_fee_rate

        cost = commission + stamp_tax + transfer_fee

        if action == "buy":
            buy_turnover += amount
        elif action in ("sell", "pending_sell"):
            sell_turnover += amount

        total_commission += commission
        total_stamp_tax += stamp_tax
        total_transfer_fee += transfer_fee

        details.append({
            "trade_date": trade.get("trade_date", ""),
            "action": action,
            "price": price,
            "size": size,
            "amount": round(amount, 2),
            "commission": round(commission, 2),
            "stamp_tax": round(stamp_tax, 2),
            "transfer_fee": round(transfer_fee, 2),
            "total_cost": round(cost, 2),
        })

    total_cost = total_commission + total_stamp_tax + total_transfer_fee
    cost_ratio = total_cost / total_turnover if total_turnover > 0 else 0.0

    return {
        "total_turnover": round(total_turnover, 2),
        "buy_turnover": round(buy_turnover, 2),
        "sell_turnover": round(sell_turnover, 2),
        "commission": round(total_commission, 2),
        "stamp_tax": round(total_stamp_tax, 2),
        "transfer_fee": round(total_transfer_fee, 2),
        "total_cost": round(total_cost, 2),
        "cost_ratio": round(float(cost_ratio), 6),
        "details": details,
    }


# ============================================================
# 个股盈亏分析
# ============================================================

def analyze_stock_pnl(trades: list[dict]) -> list[dict]:
    """
    个股盈亏分析

    按股票分组统计买入/卖出金额、数量、已实现盈亏。
    使用 FIFO 匹配买卖配对，计算每只股票的已实现盈亏。

    参数:
        trades: 交易记录列表，每条记录应包含:
            - action: "buy" 或 "sell"
            - price: 成交价格
            - size: 成交数量
            - stock_code: 股票代码（可选，如无则标记为 "unknown"）
            - stock_name: 股票名称（可选）
            - pnl: 盈亏金额（可选，sell 时直接使用）
            - trade_date: 交易日期

    返回:
        list[dict], 个股盈亏列表，每项包含:
          - stock_code: 股票代码
          - stock_name: 股票名称
          - buy_count: 买入次数
          - sell_count: 卖出次数
          - buy_amount: 买入总金额
          - sell_amount: 卖出总金额
          - buy_volume: 买入总数量
          - sell_volume: 卖出总数量
          - realized_pnl: 已实现盈亏
          - avg_buy_price: 平均买入价格
          - avg_sell_price: 平均卖出价格
    """
    if not trades:
        return []

    # 按股票代码分组
    stock_groups: dict[str, list[dict]] = {}
    for trade in trades:
        code = str(trade.get("stock_code", "") or "unknown").strip()
        if not code:
            code = "unknown"
        if code not in stock_groups:
            stock_groups[code] = []
        stock_groups[code].append(trade)

    result: list[dict] = []

    for code, stock_trades in stock_groups.items():
        buy_count = 0
        sell_count = 0
        buy_amount = 0.0
        sell_amount = 0.0
        buy_volume = 0
        sell_volume = 0.0
        realized_pnl = 0.0
        stock_name = ""

        # FIFO 队列用于匹配买卖
        buy_queue: list[dict] = []

        for trade in stock_trades:
            action = str(trade.get("action", "")).lower()
            price = float(trade.get("price", 0))
            size = int(trade.get("size", 0))

            # 获取股票名称
            if not stock_name:
                stock_name = str(trade.get("stock_name", "") or "")

            if action == "buy":
                buy_count += 1
                buy_amount += price * size
                buy_volume += size
                buy_queue.append({"price": price, "size": size})
            elif action in ("sell", "pending_sell"):
                sell_count += 1
                sell_amount += price * size
                sell_volume += size

                # 使用 FIFO 匹配计算已实现盈亏
                remaining_size = size
                while remaining_size > 0 and buy_queue:
                    buy_lot = buy_queue[0]
                    matched_size = min(remaining_size, buy_lot["size"])
                    # 已实现盈亏 = (卖出价 - 买入价) * 匹配数量
                    lot_pnl = (price - buy_lot["price"]) * matched_size
                    realized_pnl += lot_pnl

                    buy_lot["size"] -= matched_size
                    remaining_size -= matched_size

                    if buy_lot["size"] <= 0:
                        buy_queue.pop(0)

                # 如果还有未匹配的卖出数量，使用交易记录中的 pnl
                if remaining_size > 0:
                    trade_pnl = float(trade.get("pnl", 0))
                    # 按比例计算未匹配部分的盈亏
                    if size > 0:
                        realized_pnl += trade_pnl * (remaining_size / size)

        avg_buy_price = buy_amount / buy_volume if buy_volume > 0 else 0.0
        avg_sell_price = sell_amount / sell_volume if sell_volume > 0 else 0.0

        result.append({
            "stock_code": code,
            "stock_name": stock_name,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "buy_amount": round(buy_amount, 2),
            "sell_amount": round(sell_amount, 2),
            "buy_volume": buy_volume,
            "sell_volume": int(sell_volume),
            "realized_pnl": round(realized_pnl, 2),
            "avg_buy_price": round(avg_buy_price, 4),
            "avg_sell_price": round(avg_sell_price, 4),
        })

    # 按已实现盈亏降序排列
    result.sort(key=lambda x: x["realized_pnl"], reverse=True)
    return result
