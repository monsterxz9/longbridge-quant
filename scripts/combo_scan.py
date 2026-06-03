"""技术+基本面组合扫描 CLI。

管道: universe → 基本面筛选 → 技术面回踩扫描 → 合并排序输出

用法示例:

    # 低估值 + EMA 回踩
    uv run scripts/combo_scan.py --universe tech_largecap \\
        --pe-max 30 --capital-flow-positive \\
        --window 2026-04-01:2026-04-10 --ema 55,100

    # 价值 + 回踩
    uv run scripts/combo_scan.py --universe all_largecap \\
        --pe-max 15 --dividend-min 2.0 \\
        --window 2026-04-01:2026-04-10
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta

import pandas as pd

from fundamental.data import get_universe_fundamentals
from fundamental.screen import ScreenCriteria, screen
from lb_config import get_client
from technical.scanner import scan_universe


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


def _fmt_flow(val) -> str:
    if val is None or pd.isna(val):
        return "-"
    if abs(val) >= 1e9:
        return f"{'+' if val > 0 else ''}{val/1e9:.1f}B"
    if abs(val) >= 1e6:
        return f"{'+' if val > 0 else ''}{val/1e6:.0f}M"
    return f"{'+' if val > 0 else ''}{val/1e3:.0f}K"


def print_combo_report(
    df: pd.DataFrame,
    universe_name: str,
    window: tuple[str, str],
    hold_days: int | None,
    screen_desc: str,
) -> None:
    if df.empty:
        print("\n  [报告] 没有同时满足基本面 + 技术面条件的股票")
        return

    total = len(df)
    pos = int((df["return_pct"] > 0).sum())
    avg = df["return_pct"].mean()
    hold_str = f"持有 {hold_days} 交易日" if hold_days else "持有至最新收盘"

    print(f"\n{'=' * 135}")
    print(
        f"  组合扫描 | 股票池: {universe_name} | 筛选: {screen_desc} | 窗口: {window[0]}~{window[1]} | {hold_str}"
    )
    print(f"{'=' * 135}")
    print(
        f"  {'标的':<12} {'EMA':>7} {'日期':>11} {'入场':>9} {'出场':>9} "
        f"{'回报%':>7} {'回撤%':>7}  "
        f"{'PE':>7} {'PB':>6} {'股息':>6} {'资金流':>9} {'YTD%':>7}"
    )
    print(f"  {'-' * 127}")

    for _, r in df.iterrows():
        print(
            f"  {r['symbol']:<12} {r['ema_level']:>7} {r['touch_date']:>11} "
            f"{r['entry_price']:>9.2f} {r['exit_price']:>9.2f} "
            f"{r['return_pct']:>6.1f}% {r['max_drawdown']:>6.1f}%  "
            f"{r.get('pe_ttm', float('nan')):>7.1f} "
            f"{r.get('pb', float('nan')):>6.2f} "
            f"{r.get('dividend_yield', float('nan')):>5.1f}% "
            f"{_fmt_flow(r.get('capital_flow')):>9} "
            f"{r.get('ytd_return', float('nan')):>6.1f}%"
        )

    print(f"\n  --- 统计 ---")
    print(f"  命中: {total} 只 | 正收益: {pos}/{total} ({pos/total*100:.0f}%) | 平均: {avg:.1f}%")


def build_screen_desc(criteria: ScreenCriteria) -> str:
    parts = []
    if criteria.pe_max is not None:
        parts.append(f"PE<={criteria.pe_max}")
    if criteria.pe_min is not None:
        parts.append(f"PE>={criteria.pe_min}")
    if criteria.pb_max is not None:
        parts.append(f"PB<={criteria.pb_max}")
    if criteria.dividend_min is not None:
        parts.append(f"股息>={criteria.dividend_min}%")
    if criteria.capital_flow_positive:
        parts.append("资金流入")
    if criteria.ytd_return_min is not None:
        parts.append(f"YTD>={criteria.ytd_return_min}%")
    if criteria.market_cap_min is not None:
        parts.append(f"市值>=${criteria.market_cap_min/1e9:.0f}B")
    return " & ".join(parts) if parts else "无基本面过滤"


def main() -> None:
    parser = argparse.ArgumentParser(description="技术+基本面组合扫描")
    parser.add_argument(
        "--universe",
        default="tech_largecap",
        choices=["tech_largecap", "nasdaq_largecap", "all_largecap", "sectors"],
        help="股票池 (默认: tech_largecap)",
    )

    # 基本面筛选
    parser.add_argument("--pe-max", type=float, default=None)
    parser.add_argument("--pe-min", type=float, default=None)
    parser.add_argument("--pb-max", type=float, default=None)
    parser.add_argument("--dividend-min", type=float, default=None, help="股息率下限 (%%)")
    parser.add_argument("--capital-flow-positive", action="store_true")
    parser.add_argument("--ytd-min", type=float, default=None)
    parser.add_argument("--market-cap-min", type=float, default=None)

    # 技术面参数
    parser.add_argument("--window", type=parse_window, default=None)
    parser.add_argument("--hold", type=int, default=None)
    parser.add_argument("--ema", type=parse_ema_levels, default=(21, 55, 100))
    parser.add_argument("--tolerance", type=float, default=0.03)
    parser.add_argument("--macd-filter", action="store_true")
    parser.add_argument("--no-trend-filter", dest="trend_filter",
                        action="store_false", default=True)

    parser.add_argument("--limit", type=int, default=None, help="股票池上限（快速测试）")
    parser.add_argument("--top", type=int, default=30, help="显示前 N 条")

    args = parser.parse_args()

    window = args.window if args.window else default_window()

    client = get_client()

    # Step 1: 获取股票池的基本面数据
    print(f"  股票池: {args.universe}")
    fund_df = get_universe_fundamentals(client, args.universe, limit=args.limit)
    print(f"  基本面数据: {len(fund_df)} 只")

    # Step 2: 基本面筛选
    criteria = ScreenCriteria(
        pe_max=args.pe_max,
        pe_min=args.pe_min,
        pb_max=args.pb_max,
        dividend_min=args.dividend_min,
        capital_flow_positive=args.capital_flow_positive,
        ytd_return_min=args.ytd_min,
        market_cap_min=args.market_cap_min,
    )
    screen_desc = build_screen_desc(criteria)
    filtered = screen(fund_df, criteria)
    print(f"  基本面筛选命中: {len(filtered)} 只 ({screen_desc})")

    if filtered.empty:
        print("\n  基本面筛选后无剩余股票")
        return

    filtered_symbols = filtered["symbol"].tolist()

    # Step 3: 技术面扫描
    tech_df = scan_universe(
        client,
        filtered_symbols,
        window_start=window[0],
        window_end=window[1],
        ema_levels=args.ema,
        hold_days=args.hold,
        tolerance=args.tolerance,
        require_macd_bullish=args.macd_filter,
        require_trend_bull=args.trend_filter,
    )

    if tech_df.empty:
        print("\n  [报告] 基本面筛选通过，但技术面无回踩信号")
        return

    # Step 4: 合并基本面 + 技术面
    fund_cols = ["symbol", "pe_ttm", "pb", "dividend_yield", "capital_flow",
                 "ytd_return", "market_cap"]
    merged = tech_df.merge(filtered[fund_cols], on="symbol", how="left")
    merged = merged.sort_values("return_pct", ascending=False).reset_index(drop=True).head(args.top)

    print_combo_report(merged, args.universe, window, args.hold, screen_desc)


if __name__ == "__main__":
    main()
