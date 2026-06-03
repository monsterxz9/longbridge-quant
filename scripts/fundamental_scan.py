"""基本面筛选 CLI。

用法示例:

    # 科技股低 PE 筛选
    uv run scripts/fundamental_scan.py --universe tech_largecap --pe-max 25 --sort pe_ttm

    # 高股息
    uv run scripts/fundamental_scan.py --universe all_largecap --dividend-min 3.0

    # 资金流入 + YTD 领涨
    uv run scripts/fundamental_scan.py --universe tech_largecap \
        --capital-flow-positive --sort ytd_return --desc

    # 单股详情
    uv run scripts/fundamental_scan.py --symbol AAPL.US --detail
"""

from __future__ import annotations

import argparse

from fundamental.data import get_single_fundamental, get_universe_fundamentals
from fundamental.report import print_fundamental_report, print_fundamental_table
from fundamental.screen import ScreenCriteria, screen
from lb_config import get_client

UNIVERSE_CHOICES = ["tech_largecap", "nasdaq_largecap", "all_largecap", "sectors"]

SORT_CHOICES = [
    "pe_ttm", "pb", "dividend_yield", "market_cap", "capital_flow",
    "ytd_return", "half_year_return", "ten_day_return", "five_day_return",
    "turnover_rate", "volume_ratio", "amplitude",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="基本面筛选扫描器")
    parser.add_argument(
        "--universe",
        default="tech_largecap",
        choices=UNIVERSE_CHOICES,
        help="股票池 (默认: tech_largecap)",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="单股查询模式（如 AAPL.US）",
    )
    parser.add_argument("--detail", action="store_true", help="单股模式显示详情（资金流+大小单）")

    # 筛选条件
    parser.add_argument("--pe-max", type=float, default=None, help="PE 上限（自动排除亏损）")
    parser.add_argument("--pe-min", type=float, default=None, help="PE 下限")
    parser.add_argument("--pb-max", type=float, default=None, help="PB 上限")
    parser.add_argument("--pb-min", type=float, default=None, help="PB 下限")
    parser.add_argument("--dividend-min", type=float, default=None, help="股息率下限（%%）")
    parser.add_argument("--capital-flow-positive", action="store_true", help="只保留资金净流入")
    parser.add_argument("--ytd-min", type=float, default=None, help="YTD 涨幅下限（%%）")
    parser.add_argument("--ytd-max", type=float, default=None, help="YTD 涨幅上限（%%）")
    parser.add_argument("--market-cap-min", type=float, default=None,
                        help="最小市值（美元，如 10e9 = 100 亿）")

    # 排序
    parser.add_argument("--sort", default="pe_ttm", choices=SORT_CHOICES,
                        help="排序字段 (默认: pe_ttm)")
    parser.add_argument("--desc", action="store_true", help="降序排序（默认升序）")

    # 输出
    parser.add_argument("--top", type=int, default=30, help="显示前 N 条 (默认: 30)")
    parser.add_argument("--limit", type=int, default=None,
                        help="股票池大小上限（快速测试）")

    args = parser.parse_args()

    client = get_client()

    # 单股模式
    if args.symbol:
        if args.detail:
            detail = get_single_fundamental(client, args.symbol)
            print_fundamental_report(detail)
        else:
            from cache import fetch_fundamentals_cached
            df = fetch_fundamentals_cached(client, [args.symbol])
            print_fundamental_table(df, top_n=1)
        return

    # 批量筛选模式
    print(f"  股票池: {args.universe}")
    df = get_universe_fundamentals(client, args.universe, limit=args.limit)
    print(f"  原始数据: {len(df)} 只")

    criteria = ScreenCriteria(
        pe_max=args.pe_max,
        pe_min=args.pe_min,
        pb_max=args.pb_max,
        pb_min=args.pb_min,
        dividend_min=args.dividend_min,
        capital_flow_positive=args.capital_flow_positive,
        ytd_return_min=args.ytd_min,
        ytd_return_max=args.ytd_max,
        market_cap_min=args.market_cap_min,
        sort_by=args.sort,
        ascending=not args.desc,
    )
    result = screen(df, criteria)
    print(f"  筛选命中: {len(result)} 只")

    print_fundamental_table(result, top_n=args.top)


if __name__ == "__main__":
    main()
