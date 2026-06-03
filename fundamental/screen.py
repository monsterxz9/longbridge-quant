"""基本面筛选引擎。"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ScreenCriteria:
    """基本面筛选条件。所有字段为 None 表示不过滤该维度。"""

    pe_max: float | None = None
    pe_min: float | None = None
    pb_max: float | None = None
    pb_min: float | None = None
    dividend_min: float | None = None
    capital_flow_positive: bool = False
    ytd_return_min: float | None = None
    ytd_return_max: float | None = None
    market_cap_min: float | None = None
    sort_by: str = "pe_ttm"
    ascending: bool = True


def screen(df: pd.DataFrame, criteria: ScreenCriteria) -> pd.DataFrame:
    """对 fetch_fundamentals_cached 返回的 DataFrame 做筛选 + 排序。

    跳过 NaN 值（不因缺数据而排除股票，只有明确不满足条件才排除）。
    """
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)

    if criteria.pe_min is not None:
        mask &= df["pe_ttm"].isna() | (df["pe_ttm"] >= criteria.pe_min)
    if criteria.pe_max is not None:
        # PE 为负（亏损）的也排除
        mask &= df["pe_ttm"].isna() | ((df["pe_ttm"] > 0) & (df["pe_ttm"] <= criteria.pe_max))
    if criteria.pb_min is not None:
        mask &= df["pb"].isna() | (df["pb"] >= criteria.pb_min)
    if criteria.pb_max is not None:
        mask &= df["pb"].isna() | (df["pb"] <= criteria.pb_max)
    if criteria.dividend_min is not None:
        mask &= df["dividend_yield"].isna() | (df["dividend_yield"] >= criteria.dividend_min)
    if criteria.capital_flow_positive:
        mask &= df["capital_flow"].isna() | (df["capital_flow"] > 0)
    if criteria.ytd_return_min is not None:
        mask &= df["ytd_return"].isna() | (df["ytd_return"] >= criteria.ytd_return_min)
    if criteria.ytd_return_max is not None:
        mask &= df["ytd_return"].isna() | (df["ytd_return"] <= criteria.ytd_return_max)
    if criteria.market_cap_min is not None:
        mask &= df["market_cap"].isna() | (df["market_cap"] >= criteria.market_cap_min)

    result = df[mask].copy()

    if criteria.sort_by in result.columns:
        result = result.sort_values(
            criteria.sort_by, ascending=criteria.ascending, na_position="last"
        ).reset_index(drop=True)

    return result
