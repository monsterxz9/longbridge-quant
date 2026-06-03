"""基本面数据获取：封装 cache 层，提供 universe 级和单股级接口。"""

from __future__ import annotations

import time

import pandas as pd

from cache import fetch_fundamentals_cached
from longbridge_cli import LongbridgeCLI
from universe import (
    all_largecap_universe,
    nasdaq_largecap_universe,
    sectors_universe,
    tech_largecap_universe,
)

_UNIVERSE_LOADERS = {
    "tech_largecap": tech_largecap_universe,
    "nasdaq_largecap": nasdaq_largecap_universe,
    "all_largecap": all_largecap_universe,
    "sectors": None,
}


def _safe_float(val) -> float:
    if val is None or val == "":
        return 0.0
    return float(val)


def load_universe(name: str, client: LongbridgeCLI) -> list[str]:
    if name == "sectors":
        return sectors_universe()
    fn = _UNIVERSE_LOADERS[name]
    return fn(client)


def get_universe_fundamentals(
    client: LongbridgeCLI,
    universe_name: str = "tech_largecap",
    limit: int | None = None,
) -> pd.DataFrame:
    """获取指定股票池的全部基本面数据。"""
    symbols = load_universe(universe_name, client)
    if limit:
        symbols = symbols[:limit]
    return fetch_fundamentals_cached(client, symbols)


def get_single_fundamental(client: LongbridgeCLI, symbol: str) -> dict:
    """获取单股基本面 + 资金流详情。

    返回 dict 包含:
    - 基本面指标 (pe_ttm, pb, dividend_yield, ...)
    - capital_flow_lines: 时序资金流 list[dict]
    - capital_distribution: 大小单分布 dict
    """
    # 基本面指标
    df = fetch_fundamentals_cached(client, [symbol])
    if df.empty:
        return {"symbol": symbol, "error": "无基本面数据"}

    result = df.iloc[0].to_dict()

    # 时序资金流
    try:
        flow_lines = client.capital_flow(symbol)
        result["capital_flow_lines"] = [
            {
                "timestamp": str(fl.get("time")),
                "inflow": max(_safe_float(fl.get("inflow")), 0.0),
                "outflow": min(_safe_float(fl.get("inflow")), 0.0),
                "net": _safe_float(fl.get("inflow")),
            }
            for fl in flow_lines
        ]
    except Exception as e:
        result["capital_flow_lines"] = []
        result["capital_flow_error"] = str(e)

    time.sleep(0.2)

    # 大小单分布
    try:
        dist = client.capital_distribution(symbol)
        cap_in = dist.get("capital_in", {})
        cap_out = dist.get("capital_out", {})
        result["capital_distribution"] = {
            "large_inflow": _safe_float(cap_in.get("large")),
            "large_outflow": _safe_float(cap_out.get("large")),
            "medium_inflow": _safe_float(cap_in.get("medium")),
            "medium_outflow": _safe_float(cap_out.get("medium")),
            "small_inflow": _safe_float(cap_in.get("small")),
            "small_outflow": _safe_float(cap_out.get("small")),
        }
    except Exception as e:
        result["capital_distribution"] = {}
        result["capital_distribution_error"] = str(e)

    return result
