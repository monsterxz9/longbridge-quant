"""板块分类 EMA + MACD 多周期扫描"""

import pandas as pd

from cache import fetch_daily_cached
from lb_config import get_client
from longbridge_cli import LongbridgeCLI
from sectors_data import SECTORS
from technical.indicators import calc_ema, calc_macd, detect_signals

EMA_PERIODS = [21, 55, 100, 200]


def quick_scan(client: LongbridgeCLI, symbol: str) -> dict | None:
    """对单个标的做快速日线扫描，返回摘要 dict"""
    try:
        daily = fetch_daily_cached(client, symbol, 250)
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}

    if len(daily) < 200:
        return {"symbol": symbol, "error": f"数据不足 ({len(daily)} bars)"}

    daily = calc_ema(daily, EMA_PERIODS)
    daily = calc_macd(daily)
    daily = detect_signals(daily)

    last = daily.iloc[-1]
    prev = daily.iloc[-2]

    if last["ema_bullish"]:
        ema_status = "多头"
    elif last["ema_bearish"]:
        ema_status = "空头"
    else:
        ema_status = "交织"

    above_count = sum(1 for p in EMA_PERIODS if last["close"] > last[f"ema{p}"])
    macd_side = "多" if last["macd_dif"] > last["macd_dea"] else "空"
    hist_trend = "放大" if abs(last["macd_hist"]) > abs(prev["macd_hist"]) else "缩小"

    signals = daily[daily["signal"] != ""].tail(1)
    last_signal = ""
    last_signal_date = ""
    if not signals.empty:
        row = signals.iloc[-1]
        last_signal = row["signal"]
        last_signal_date = row["date"].strftime("%m-%d")

    return {
        "symbol": symbol,
        "close": last["close"],
        "ema_status": ema_status,
        "above_ema": f"{above_count}/4",
        "macd_side": macd_side,
        "macd_hist": last["macd_hist"],
        "hist_trend": hist_trend,
        "last_signal": last_signal,
        "signal_date": last_signal_date,
    }


def format_signal(sig: str) -> str:
    return {
        "BUY": "BUY",
        "SELL": "SELL",
        "macd_golden": "MACD金叉",
        "macd_death": "MACD死叉",
    }.get(sig, sig or "-")


def print_sector(sector_name: str, results: list[dict]):
    print(f"\n{'=' * 90}")
    print(f"  {sector_name}")
    print(f"{'=' * 90}")
    print(
        f"  {'标的':<12} {'价格':>10} {'EMA排列':>8} {'站上EMA':>8} "
        f"{'MACD':>6} {'柱趋势':>6} {'最近信号':>10} {'日期':>8}"
    )
    print(f"  {'-' * 82}")

    for r in results:
        if "error" in r:
            print(f"  {r['symbol']:<12} {r['error']}")
            continue

        sig_str = format_signal(r["last_signal"])
        print(
            f"  {r['symbol']:<12} {r['close']:>10.2f} {r['ema_status']:>8} {r['above_ema']:>8} "
            f"{r['macd_side']:>6} {r['hist_trend']:>6} {sig_str:>10} {r['signal_date']:>8}"
        )


def sector_summary(results: list[dict]) -> dict:
    """板块内多空统计"""
    valid = [r for r in results if "error" not in r]
    bullish = sum(1 for r in valid if r["ema_status"] == "多头")
    bearish = sum(1 for r in valid if r["ema_status"] == "空头")
    macd_bull = sum(1 for r in valid if r["macd_side"] == "多")
    return {
        "total": len(valid),
        "ema_bullish": bullish,
        "ema_bearish": bearish,
        "macd_bullish": macd_bull,
    }


def main():
    client = get_client()

    cache = {}
    all_summaries = {}
    all_results = {}

    for sector_name, symbols in SECTORS.items():
        results = []
        for symbol in symbols:
            if symbol not in cache:
                cache[symbol] = quick_scan(client, symbol)
            results.append(cache[symbol])

        print_sector(sector_name, results)
        all_results[sector_name] = results
        all_summaries[sector_name] = sector_summary(results)

    for name, s in all_summaries.items():
        t = s["total"] or 1
        ema_score = s["ema_bullish"] / t
        macd_score = s["macd_bullish"] / t
        above_scores = [r for r in all_results[name] if "error" not in r]
        avg_above = sum(int(r["above_ema"].split("/")[0]) for r in above_scores) / (len(above_scores) * 4) if above_scores else 0
        s["score"] = ema_score * 50 + macd_score * 30 + avg_above * 20

    ranked = sorted(all_summaries.items(), key=lambda x: x[1]["score"], reverse=True)

    print(f"\n{'=' * 90}")
    print("  板块强弱排名 (综合评分: EMA排列50% + MACD方向30% + 价格位置20%)")
    print(f"{'=' * 90}")
    print(f"  {'排名':>4} {'板块':<14} {'标的':>4} {'EMA多头':>8} {'EMA空头':>8} {'MACD多':>7} {'评分':>6}  强弱")
    print(f"  {'-' * 75}")

    for i, (name, s) in enumerate(ranked, 1):
        bar_len = int(s["score"] / 10)
        bar = "\u2588" * bar_len + "\u2591" * (10 - bar_len)
        print(
            f"  {i:>4} {name:<14} {s['total']:>4} {s['ema_bullish']:>8} {s['ema_bearish']:>8} "
            f"{s['macd_bullish']:>7} {s['score']:>5.0f}  {bar}"
        )


if __name__ == "__main__":
    main()
