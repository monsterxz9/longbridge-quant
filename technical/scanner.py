"""EMA 回踩扫描器 + 持仓回测器。

核心概念:
    PullbackEvent —— 一次"多头趋势下日内低点回踩 EMA"的事件
    find_ema_pullbacks —— 在日期窗口内从单只股票的 DataFrame 中提取事件
    backtest_pullback —— 从事件买入点持有 N 天计算回报与最大回撤
    scan_universe —— 对一批股票跑以上两步并返回汇总 DataFrame

"回踩"默认要求 4 个条件: 日线多头排列 + 周线多头排列 + 日内低点触及 EMA
(±tolerance) + 当日收盘回到 EMA 附近 (容差内)。详见 find_ema_pullbacks
的 docstring。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd

from cache import fetch_daily_batch
from longbridge_cli import LongbridgeCLI
from technical.indicators import calc_ema, calc_macd, resample_weekly


def _mark_trend_bullish(df: pd.DataFrame, col: str = "trend_bull") -> pd.DataFrame:
    """给含 ema21/55/100/200 的 DataFrame 写入一列多头排列布尔值 (21>55>100>200)。"""
    df[col] = (
        (df["ema21"] > df["ema55"])
        & (df["ema55"] > df["ema100"])
        & (df["ema100"] > df["ema200"])
    )
    return df


@dataclass
class PullbackEvent:
    """一次多头趋势下回踩 EMA 的事件记录。"""

    symbol: str
    ema_level: str
    touch_date: str
    touch_price: float
    touch_low: float
    ema_value: float
    dist_pct: float


def find_ema_pullbacks(
    df: pd.DataFrame,
    window_start: str,
    window_end: str,
    ema_levels: Iterable[int] = (21, 55, 100),
    tolerance: float = 0.03,
    require_macd_bullish: bool = False,
    require_trend_bull: bool = True,
    symbol: str = "",
) -> list[PullbackEvent]:
    """在日期窗口内寻找"多头趋势下的 EMA 回踩"事件。

    回踩的完整定义 (默认 4 个条件都要满足):
        1. 日线 EMA 多头排列 (ema21 > ema55 > ema100 > ema200)
        2. 周线 EMA 多头排列 (基于日线 resample 后"已收盘"的最近一周)
        3. 日内低点落在 EMA ±tolerance 范围内
        4. 当日收盘回到 EMA 附近: close >= ema * (1 - tolerance)
    """
    if df.empty:
        return []

    mask = (df["date"] >= window_start) & (df["date"] <= window_end)
    window = df.loc[mask]
    if window.empty:
        return []

    events: list[PullbackEvent] = []
    for _, row in window.iterrows():
        if require_trend_bull:
            if not bool(row.get("daily_bull", False)):
                continue
            if not bool(row.get("weekly_bull", False)):
                continue

        if require_macd_bullish:
            dif = row.get("macd_dif")
            dea = row.get("macd_dea")
            if dif is None or dea is None or pd.isna(dif) or pd.isna(dea):
                continue
            if dif <= dea:
                continue

        low = float(row["low"])
        close = float(row["close"])

        for lvl in ema_levels:
            col = f"ema{lvl}"
            if col not in row or pd.isna(row[col]) or row[col] == 0:
                continue
            ema_val = float(row[col])
            dist = low / ema_val - 1
            if abs(dist) <= tolerance and close >= ema_val * (1 - tolerance):
                events.append(
                    PullbackEvent(
                        symbol=symbol,
                        ema_level=f"EMA{lvl}",
                        touch_date=row["date"].strftime("%Y-%m-%d"),
                        touch_price=close,
                        touch_low=low,
                        ema_value=ema_val,
                        dist_pct=dist * 100,
                    )
                )
    return events


def backtest_pullback(
    event: PullbackEvent,
    df: pd.DataFrame,
    hold_days: int | None = None,
) -> dict:
    """从 event.touch_date 的收盘价买入，持有 hold_days 个交易日。"""
    touch_date = pd.Timestamp(event.touch_date).normalize()
    date_only = df["date"].dt.normalize()
    idx = df.index[date_only == touch_date]
    if len(idx) == 0:
        return {
            "entry_date": event.touch_date,
            "entry_price": event.touch_price,
            "exit_date": event.touch_date,
            "exit_price": event.touch_price,
            "return_pct": 0.0,
            "max_drawdown": 0.0,
        }
    entry_i = int(idx[0])
    if hold_days is None:
        exit_i = len(df) - 1
    else:
        exit_i = min(entry_i + hold_days, len(df) - 1)

    entry_price = float(df.iloc[entry_i]["close"])
    exit_price = float(df.iloc[exit_i]["close"])
    return_pct = (exit_price / entry_price - 1) * 100

    segment = df.iloc[entry_i : exit_i + 1]
    min_close = float(segment["close"].min())
    max_drawdown = (min_close / entry_price - 1) * 100

    return {
        "entry_date": event.touch_date,
        "entry_price": entry_price,
        "exit_date": df.iloc[exit_i]["date"].strftime("%Y-%m-%d"),
        "exit_price": exit_price,
        "return_pct": return_pct,
        "max_drawdown": max_drawdown,
    }


def scan_universe(
    client: LongbridgeCLI,
    symbols: list[str],
    window_start: str,
    window_end: str,
    ema_levels: Iterable[int] = (21, 55, 100),
    hold_days: int | None = None,
    tolerance: float = 0.03,
    require_macd_bullish: bool = False,
    require_trend_bull: bool = True,
    candles: int = 300,
    progress: bool = True,
) -> pd.DataFrame:
    """对一批股票跑 find_ema_pullbacks + backtest_pullback，返回汇总 DataFrame。"""
    if progress:
        print(f"  扫描 {len(symbols)} 只股票 (窗口 {window_start} ~ {window_end})...")

    daily_map = fetch_daily_batch(client, symbols, count=candles, progress=progress)

    ema_levels_tuple = tuple(ema_levels)
    ema_full_periods = list(set(list(ema_levels_tuple) + [21, 55, 100, 200]))

    rows: list[dict] = []
    for sym, df in daily_map.items():
        if len(df) < max(ema_levels_tuple) + 5:
            continue
        df = calc_ema(df.copy(), ema_full_periods)
        if require_macd_bullish:
            df = calc_macd(df)

        if require_trend_bull:
            df = _mark_trend_bullish(df, col="daily_bull")
            base_cols = ["date", "open", "high", "low", "close", "volume"]
            weekly = resample_weekly(df[base_cols].copy())
            if len(weekly) >= 21:
                weekly = calc_ema(weekly, [21, 55, 100, 200])
                weekly = _mark_trend_bullish(weekly, col="weekly_bull")
                df = pd.merge_asof(
                    df.sort_values("date"),
                    weekly[["date", "weekly_bull"]].sort_values("date"),
                    on="date",
                    direction="backward",
                )
            else:
                df["weekly_bull"] = False

        events = find_ema_pullbacks(
            df,
            window_start=window_start,
            window_end=window_end,
            ema_levels=ema_levels_tuple,
            tolerance=tolerance,
            require_macd_bullish=require_macd_bullish,
            require_trend_bull=require_trend_bull,
            symbol=sym,
        )
        if not events:
            continue

        best = min(events, key=lambda e: abs(e.dist_pct))
        bt = backtest_pullback(best, df, hold_days=hold_days)
        rows.append({**asdict(best), **bt})

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result = result.sort_values("return_pct", ascending=False).reset_index(drop=True)
    return result
