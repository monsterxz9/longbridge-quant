"""EMA 回踩扫描器 CLI —— 对指定股票池跑回踩扫描 + 持有回测。

用法示例:

    # 默认: 科技大盘股池 + 最近 10 个自然日窗口 + 持有到最新收盘
    uv run scripts/pullback_scan.py

    # 指定股票池
    uv run scripts/pullback_scan.py --universe nasdaq_largecap
    uv run scripts/pullback_scan.py --universe all_largecap
    uv run scripts/pullback_scan.py --universe sectors

    # 指定日期窗口
    uv run scripts/pullback_scan.py --window 2026-03-27:2026-04-02

    # 指定持有天数和 EMA 级别
    uv run scripts/pullback_scan.py --window 2026-03-27:2026-04-02 --hold 10 --ema 55,100

    # 开启 MACD 多方过滤
    uv run scripts/pullback_scan.py --window 2026-03-27:2026-04-02 --macd-filter

    # 关闭趋势过滤
    uv run scripts/pullback_scan.py --window 2026-03-27:2026-04-02 --no-trend-filter
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import pandas as pd

from lb_config import get_client
from longbridge_cli import LongbridgeCLI
from technical.scanner import scan_universe
from universe import (
    all_largecap_universe,
    nasdaq_largecap_universe,
    sectors_universe,
    tech_largecap_universe,
)

UNIVERSES = {
    "tech_largecap": tech_largecap_universe,
    "nasdaq_largecap": nasdaq_largecap_universe,
    "all_largecap": all_largecap_universe,
    "sectors": None,
}


def parse_window(text: str) -> tuple[str, str]:
    parts = text.split(":")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(
            f"--window 格式应为 YYYY-MM-DD:YYYY-MM-DD，收到 {text!r}"
        )
    start, end = parts[0].strip(), parts[1].strip()
    datetime.strptime(start, "%Y-%m-%d")
    datetime.strptime(end, "%Y-%m-%d")
    return start, end


def parse_ema_levels(text: str) -> tuple[int, ...]:
    return tuple(int(x.strip()) for x in text.split(",") if x.strip())


def default_window() -> tuple[str, str]:
    today = datetime.now()
    start = today - timedelta(days=10)
    return start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")


def load_universe(name: str, client: LongbridgeCLI) -> list[str]:
    if name == "sectors":
        return sectors_universe()
    fn = UNIVERSES[name]
    return fn(client)


def print_report(df: pd.DataFrame, universe_name: str, window: tuple[str, str], hold_days: int | None) -> None:
    if df.empty:
        print("\n  [报告] 窗口内没有任何股票触发 EMA 回踩信号")
        return

    total = len(df)
    pos = int((df["return_pct"] > 0).sum())
    avg = df["return_pct"].mean()
    median = df["return_pct"].median()
    hold_str = f"持有 {hold_days} 个交易日" if hold_days else "持有至最新收盘"

    print(f"\n{'='*105}")
    print(
        f"  EMA 回踩扫描结果 | 股票池: {universe_name} | 窗口: {window[0]} ~ {window[1]} | {hold_str}"
    )
    print(f"{'='*105}")
    print(
        f"  {'标的':<14} {'EMA':>8} {'日期':>12} {'入场':>10} {'出场':>10} "
        f"{'回报%':>8} {'最大回撤%':>10} {'低点':>10} {'偏离%':>7}"
    )
    print(f"  {'-'*97}")

    for _, r in df.iterrows():
        flag = " \u2605" if r["return_pct"] is not None and r["return_pct"] > 15 else ""
        print(
            f"  {r['symbol']:<14} {r['ema_level']:>8} {r['touch_date']:>12} "
            f"{r['entry_price']:>10.2f} {r['exit_price']:>10.2f} "
            f"{r['return_pct']:>7.1f}% {r['max_drawdown']:>9.1f}% "
            f"{r['touch_low']:>10.2f} {r['dist_pct']:>6.1f}%{flag}"
        )

    print(f"\n  --- 统计 ---")
    print(
        f"  命中: {total} 只 | 正收益: {pos}/{total} ({pos/total*100:.0f}%) | "
        f"平均: {avg:.1f}% | 中位数: {median:.1f}%"
    )

    for ema in ["EMA21", "EMA55", "EMA100", "EMA200"]:
        group = df[df["ema_level"] == ema]
        if not group.empty:
            g_avg = group["return_pct"].mean()
            g_pos = int((group["return_pct"] > 0).sum())
            print(
                f"  {ema}: {len(group)}只  平均: {g_avg:.1f}%  "
                f"胜率: {g_pos}/{len(group)} ({g_pos/len(group)*100:.0f}%)"
            )

    top_n = min(20, total)
    print(f"\n  === TOP {top_n} ===")
    for _, r in df.head(top_n).iterrows():
        print(
            f"  {r['symbol']:<14} {r['ema_level']:>8}  "
            f"买入:{r['entry_price']:>10.2f}  现价:{r['exit_price']:>10.2f}  回报: {r['return_pct']:>7.1f}%"
        )

    bottom_n = min(10, max(0, total - top_n))
    if bottom_n > 0:
        print(f"\n  === BOTTOM {bottom_n} ===")
        for _, r in df.tail(bottom_n).iterrows():
            print(
                f"  {r['symbol']:<14} {r['ema_level']:>8}  "
                f"买入:{r['entry_price']:>10.2f}  现价:{r['exit_price']:>10.2f}  回报: {r['return_pct']:>7.1f}%"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="EMA 回踩扫描器")
    parser.add_argument(
        "--universe",
        default="tech_largecap",
        choices=list(UNIVERSES.keys()),
        help="股票池 (默认: tech_largecap)",
    )
    parser.add_argument(
        "--window",
        type=parse_window,
        default=None,
        help="日期窗口 YYYY-MM-DD:YYYY-MM-DD (默认: 最近 10 个自然日)",
    )
    parser.add_argument(
        "--hold",
        type=int,
        default=None,
        help="持有交易日数 (默认: 持有到最新收盘)",
    )
    parser.add_argument(
        "--ema",
        type=parse_ema_levels,
        default=(21, 55, 100),
        help="要检测的 EMA 级别 (默认: 21,55,100)",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.03,
        help="低点距离 EMA 的容差百分比 (默认: 0.03 即 3%%)",
    )
    parser.add_argument(
        "--macd-filter",
        action="store_true",
        help="额外要求 MACD 多方（DIF > DEA）才算有效回踩",
    )
    parser.add_argument(
        "--no-trend-filter",
        dest="trend_filter",
        action="store_false",
        default=True,
        help="关闭日线+周线多头排列的趋势过滤（默认开启）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="股票池大小上限（用于快速测试）",
    )
    args = parser.parse_args()

    window = args.window if args.window else default_window()

    client = get_client()

    print(f"  股票池: {args.universe}")
    symbols = load_universe(args.universe, client)
    if args.limit:
        symbols = symbols[: args.limit]
    print(f"  股票数量: {len(symbols)}")

    df = scan_universe(
        client,
        symbols,
        window_start=window[0],
        window_end=window[1],
        ema_levels=args.ema,
        hold_days=args.hold,
        tolerance=args.tolerance,
        require_macd_bullish=args.macd_filter,
        require_trend_bull=args.trend_filter,
    )

    print_report(df, args.universe, window, args.hold)


if __name__ == "__main__":
    main()
