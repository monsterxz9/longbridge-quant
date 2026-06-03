"""基本面报告输出。"""

from __future__ import annotations

import math

import pandas as pd


def _fmt(val, fmt: str = ".2f", suffix: str = "", na: str = "-") -> str:
    """安全格式化数字，NaN 显示为 '-'。"""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return na
    return f"{val:{fmt}}{suffix}"


def _fmt_cap(val) -> str:
    """市值格式化为 B/M。"""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "-"
    if val >= 1e12:
        return f"${val/1e12:.1f}T"
    if val >= 1e9:
        return f"${val/1e9:.1f}B"
    if val >= 1e6:
        return f"${val/1e6:.0f}M"
    return f"${val:.0f}"


def _fmt_flow(val) -> str:
    """资金流格式化。"""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return "-"
    if abs(val) >= 1e9:
        return f"{'+' if val > 0 else ''}{val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"{'+' if val > 0 else ''}{val/1e6:.1f}M"
    if abs(val) >= 1e3:
        return f"{'+' if val > 0 else ''}{val/1e3:.0f}K"
    return f"{'+' if val > 0 else ''}{val:.0f}"


def print_fundamental_table(df: pd.DataFrame, top_n: int = 30) -> None:
    """批量基本面表格输出。"""
    if df.empty:
        print("\n  [报告] 没有满足条件的股票")
        return

    display = df.head(top_n)
    total = len(df)

    print(f"\n{'=' * 120}")
    print(f"  基本面筛选结果 ({total} 只命中，显示前 {min(top_n, total)} 只)")
    print(f"{'=' * 120}")
    print(
        f"  {'标的':<12} {'价格':>8} {'市值':>10} {'PE(TTM)':>10} {'PB':>8} "
        f"{'股息率':>8} {'换手率':>8} {'量比':>6} {'振幅':>6} "
        f"{'资金流':>10} {'5日':>7} {'10日':>7} {'半年':>7} {'YTD':>7}"
    )
    print(f"  {'-' * 114}")

    for _, r in display.iterrows():
        print(
            f"  {r['symbol']:<12} "
            f"{_fmt(r.get('last_done'), '.2f'):>8} "
            f"{_fmt_cap(r.get('market_cap')):>10} "
            f"{_fmt(r.get('pe_ttm'), '.1f'):>10} "
            f"{_fmt(r.get('pb'), '.2f'):>8} "
            f"{_fmt(r.get('dividend_yield'), '.2f', '%'):>8} "
            f"{_fmt(r.get('turnover_rate'), '.2f', '%'):>8} "
            f"{_fmt(r.get('volume_ratio'), '.2f'):>6} "
            f"{_fmt(r.get('amplitude'), '.2f', '%'):>6} "
            f"{_fmt_flow(r.get('capital_flow')):>10} "
            f"{_fmt(r.get('five_day_return'), '.1f', '%'):>7} "
            f"{_fmt(r.get('ten_day_return'), '.1f', '%'):>7} "
            f"{_fmt(r.get('half_year_return'), '.1f', '%'):>7} "
            f"{_fmt(r.get('ytd_return'), '.1f', '%'):>7}"
        )

    if total > top_n:
        print(f"\n  ... 还有 {total - top_n} 只未显示")


def print_fundamental_report(detail: dict) -> None:
    """单股基本面详情报告。"""
    sym = detail.get("symbol", "?")
    if "error" in detail:
        print(f"\n  {sym}: {detail['error']}")
        return

    print(f"\n{'=' * 70}")
    print(f"  {sym} 基本面详情")
    print(f"{'=' * 70}")

    # 估值
    print(f"\n  --- 估值 ---")
    print(f"  价格:     {_fmt(detail.get('last_done'), '.2f')}")
    print(f"  市值:     {_fmt_cap(detail.get('market_cap'))}")
    print(f"  PE(TTM):  {_fmt(detail.get('pe_ttm'), '.2f')}")
    print(f"  PB:       {_fmt(detail.get('pb'), '.2f')}")
    print(f"  股息率:   {_fmt(detail.get('dividend_yield'), '.2f', '%')}")

    # 交易活跃度
    print(f"\n  --- 交易活跃度 ---")
    print(f"  换手率:   {_fmt(detail.get('turnover_rate'), '.2f', '%')}")
    print(f"  量比:     {_fmt(detail.get('volume_ratio'), '.2f')}")
    print(f"  振幅:     {_fmt(detail.get('amplitude'), '.2f', '%')}")

    # 多周期动量
    print(f"\n  --- 动量 ---")
    print(f"  5日涨幅:  {_fmt(detail.get('five_day_return'), '.2f', '%')}")
    print(f"  10日涨幅: {_fmt(detail.get('ten_day_return'), '.2f', '%')}")
    print(f"  半年涨幅: {_fmt(detail.get('half_year_return'), '.2f', '%')}")
    print(f"  YTD涨幅:  {_fmt(detail.get('ytd_return'), '.2f', '%')}")

    # 资金流净额
    print(f"\n  --- 资金流 ---")
    print(f"  净资金流:  {_fmt_flow(detail.get('capital_flow'))}")

    # 时序资金流
    flow_lines = detail.get("capital_flow_lines", [])
    if flow_lines:
        print(f"\n  --- 日内资金流 (最近 {min(10, len(flow_lines))} 条) ---")
        for fl in flow_lines[-10:]:
            print(
                f"    {fl['timestamp']}  "
                f"流入: {_fmt_flow(fl['inflow'])}  "
                f"流出: {_fmt_flow(fl['outflow'])}  "
                f"净额: {_fmt_flow(fl['net'])}"
            )
    elif detail.get("capital_flow_error"):
        print(f"  (资金流时序获取失败: {detail['capital_flow_error']})")

    # 大小单分布
    dist = detail.get("capital_distribution", {})
    if dist:
        print(f"\n  --- 大小单分布 ---")
        for label, in_key, out_key in [
            ("大单", "large_inflow", "large_outflow"),
            ("中单", "medium_inflow", "medium_outflow"),
            ("小单", "small_inflow", "small_outflow"),
        ]:
            inflow = dist.get(in_key, 0)
            outflow = dist.get(out_key, 0)
            net = inflow - outflow
            print(
                f"    {label}  流入: {_fmt_flow(inflow)}  "
                f"流出: {_fmt_flow(-outflow)}  "
                f"净额: {_fmt_flow(net)}"
            )
    elif detail.get("capital_distribution_error"):
        print(f"  (大小单分布获取失败: {detail['capital_distribution_error']})")
