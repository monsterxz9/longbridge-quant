"""EMA 21/55/100/200 + MACD 多周期策略 (日线 + 周线)"""

import pandas as pd
from longbridge.openapi import QuoteContext, Period, AdjustType

# get_config() 集中在 lb_config，这里 re-export 保持向后兼容
from lb_config import get_config  # noqa: F401


def fetch_daily(ctx: QuoteContext, symbol: str, count: int = 300) -> pd.DataFrame:
    """拉取日 K 线数据"""
    candles = ctx.candlesticks(symbol, Period.Day, count, AdjustType.ForwardAdjust)
    rows = [
        {
            "date": c.timestamp,
            "open": float(c.open),
            "high": float(c.high),
            "low": float(c.low),
            "close": float(c.close),
            "volume": int(c.volume),
        }
        for c in candles
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


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
    df["macd_hist"] = (df["macd_dif"] - df["macd_dea"]) * 2  # 柱状图
    return df


def detect_signals(df: pd.DataFrame) -> pd.DataFrame:
    """检测信号: EMA 排列 + MACD 金叉死叉"""
    # EMA 多头排列: 21 > 55 > 100 > 200
    df["ema_bullish"] = (
        (df["ema21"] > df["ema55"])
        & (df["ema55"] > df["ema100"])
        & (df["ema100"] > df["ema200"])
    )
    # EMA 空头排列: 21 < 55 < 100 < 200
    df["ema_bearish"] = (
        (df["ema21"] < df["ema55"])
        & (df["ema55"] < df["ema100"])
        & (df["ema100"] < df["ema200"])
    )

    # MACD 金叉 / 死叉
    df["macd_golden"] = (df["macd_dif"] > df["macd_dea"]) & (
        df["macd_dif"].shift(1) <= df["macd_dea"].shift(1)
    )
    df["macd_death"] = (df["macd_dif"] < df["macd_dea"]) & (
        df["macd_dif"].shift(1) >= df["macd_dea"].shift(1)
    )

    # 综合信号
    df["signal"] = ""
    df.loc[df["ema_bullish"] & df["macd_golden"], "signal"] = "BUY"
    df.loc[df["ema_bearish"] & df["macd_death"], "signal"] = "SELL"
    # 单独 MACD 信号（EMA 未完全排列时作为参考）
    df.loc[(df["signal"] == "") & df["macd_golden"], "signal"] = "macd_golden"
    df.loc[(df["signal"] == "") & df["macd_death"], "signal"] = "macd_death"

    return df


def print_analysis(symbol: str, label: str, df: pd.DataFrame):
    """打印分析结果"""
    last = df.iloc[-1]
    print(f"\n{'=' * 70}")
    print(f"  {symbol} [{label}]  最新: {last['close']:.2f}  日期: {last['date'].strftime('%Y-%m-%d')}")
    print(f"{'=' * 70}")

    # EMA 状态
    print(f"  EMA21:  {last['ema21']:.2f}")
    print(f"  EMA55:  {last['ema55']:.2f}")
    print(f"  EMA100: {last['ema100']:.2f}")
    print(f"  EMA200: {last['ema200']:.2f}")

    if last["ema_bullish"]:
        ema_status = "多头排列 (21>55>100>200)"
    elif last["ema_bearish"]:
        ema_status = "空头排列 (21<55<100<200)"
    else:
        ema_status = "交织"
    print(f"  EMA 状态: {ema_status}")

    # MACD 状态
    print(f"\n  MACD DIF:  {last['macd_dif']:.4f}")
    print(f"  MACD DEA:  {last['macd_dea']:.4f}")
    print(f"  MACD 柱:   {last['macd_hist']:.4f}")
    macd_pos = "多方 (DIF > DEA)" if last["macd_dif"] > last["macd_dea"] else "空方 (DIF < DEA)"
    print(f"  MACD 状态: {macd_pos}")

    # 价格与 EMA 关系
    above = []
    below = []
    for p in [21, 55, 100, 200]:
        if last["close"] > last[f"ema{p}"]:
            above.append(str(p))
        else:
            below.append(str(p))
    if above:
        print(f"\n  价格在 EMA{','.join(above)} 之上")
    if below:
        print(f"  价格在 EMA{','.join(below)} 之下")

    # 最近信号
    recent = df[df["signal"] != ""].tail(5)
    if not recent.empty:
        print(f"\n  最近信号:")
        for _, row in recent.iterrows():
            tag = {
                "BUY": ">>> 买入",
                "SELL": "<<< 卖出",
                "macd_golden": "  + MACD金叉",
                "macd_death": "  - MACD死叉",
            }.get(row["signal"], row["signal"])
            print(f"    {row['date'].strftime('%Y-%m-%d')}  {tag}  收盘: {row['close']:.2f}")


def analyze(ctx: QuoteContext, symbol: str):
    """对单个标的执行日线+周线分析"""
    ema_periods = [21, 55, 100, 200]

    # 日线
    daily = fetch_daily(ctx, symbol, 300)
    daily = calc_ema(daily, ema_periods)
    daily = calc_macd(daily)
    daily = detect_signals(daily)
    print_analysis(symbol, "日线", daily)

    # 周线
    weekly = resample_weekly(daily)
    weekly = calc_ema(weekly, ema_periods)
    weekly = calc_macd(weekly)
    weekly = detect_signals(weekly)
    print_analysis(symbol, "周线", weekly)


def main():
    config = get_config()
    ctx = QuoteContext(config)

    symbols = ["AAPL.US", "TSLA.US", "NVDA.US"]
    for symbol in symbols:
        analyze(ctx, symbol)

    print("\n" + "=" * 70)
    print("  策略说明:")
    print("  BUY  = EMA 多头排列 + MACD 金叉 (强买入)")
    print("  SELL = EMA 空头排列 + MACD 死叉 (强卖出)")
    print("  macd_golden / macd_death = 仅 MACD 信号 (参考)")
    print("=" * 70)


if __name__ == "__main__":
    main()
