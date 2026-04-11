"""盘前/盘后/夜盘行情查看"""

import os

# 启用夜盘数据（必须在 import longbridge 之前设置）
os.environ.setdefault("LONGBRIDGE_ENABLE_OVERNIGHT", "true")

from longbridge.openapi import QuoteContext  # noqa: E402

from lb_config import get_config  # noqa: E402

ctx = QuoteContext(get_config())

symbols = ["AAPL.US", "TSLA.US", "NVDA.US"]
quotes = ctx.quote(symbols)

for q in quotes:
    print(f"\n{'=' * 60}")
    print(f"  {q.symbol}  常规: {q.last_done}  成交量: {q.volume}")
    print(f"{'=' * 60}")

    # 盘前
    if q.pre_market_quote and q.pre_market_quote.volume:
        pm = q.pre_market_quote
        chg = (pm.last_done - pm.prev_close) / pm.prev_close * 100 if pm.prev_close else 0
        print(f"  盘前  最新: {pm.last_done}  涨跌: {chg:.2f}%  量: {pm.volume}  时间: {pm.timestamp}")

    # 盘后
    if q.post_market_quote and q.post_market_quote.volume:
        am = q.post_market_quote
        chg = (am.last_done - am.prev_close) / am.prev_close * 100 if am.prev_close else 0
        print(f"  盘后  最新: {am.last_done}  涨跌: {chg:.2f}%  量: {am.volume}  时间: {am.timestamp}")

    # 夜盘
    if q.overnight_quote and q.overnight_quote.volume:
        ov = q.overnight_quote
        chg = (ov.last_done - ov.prev_close) / ov.prev_close * 100 if ov.prev_close else 0
        print(f"  夜盘  最新: {ov.last_done}  涨跌: {chg:.2f}%  量: {ov.volume}  时间: {ov.timestamp}")

    if not any([
        q.pre_market_quote and q.pre_market_quote.volume,
        q.post_market_quote and q.post_market_quote.volume,
        q.overnight_quote and q.overnight_quote.volume,
    ]):
        print("  (无盘前/盘后/夜盘数据)")
