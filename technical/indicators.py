"""技术指标计算：EMA / MACD / 信号检测。"""

import pandas as pd


def resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """日线重采样为周线"""
    df = df.set_index("date")
    weekly = df.resample("W").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna().reset_index()
    return weekly


def calc_ema(df: pd.DataFrame, periods: list[int]) -> pd.DataFrame:
    """计算 EMA"""
    for p in periods:
        df[f"ema{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return df


def calc_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
    """计算 MACD"""
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    df["macd_dif"] = ema_fast - ema_slow
    df["macd_dea"] = df["macd_dif"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2
    return df


def detect_signals(df: pd.DataFrame) -> pd.DataFrame:
    """检测信号: EMA 排列 + MACD 金叉死叉"""
    df["ema_bullish"] = (
        (df["ema21"] > df["ema55"])
        & (df["ema55"] > df["ema100"])
        & (df["ema100"] > df["ema200"])
    )
    df["ema_bearish"] = (
        (df["ema21"] < df["ema55"])
        & (df["ema55"] < df["ema100"])
        & (df["ema100"] < df["ema200"])
    )

    df["macd_golden"] = (df["macd_dif"] > df["macd_dea"]) & (
        df["macd_dif"].shift(1) <= df["macd_dea"].shift(1)
    )
    df["macd_death"] = (df["macd_dif"] < df["macd_dea"]) & (
        df["macd_dif"].shift(1) >= df["macd_dea"].shift(1)
    )

    df["signal"] = ""
    df.loc[df["ema_bullish"] & df["macd_golden"], "signal"] = "BUY"
    df.loc[df["ema_bearish"] & df["macd_death"], "signal"] = "SELL"
    df.loc[(df["signal"] == "") & df["macd_golden"], "signal"] = "macd_golden"
    df.loc[(df["signal"] == "") & df["macd_death"], "signal"] = "macd_death"

    return df
