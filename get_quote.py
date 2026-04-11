"""长桥 OpenAPI 行情获取示例 (OAuth 认证)"""

from decimal import Decimal
from longbridge.openapi import QuoteContext, Period, AdjustType

from lb_config import get_config

# 创建行情上下文
ctx = QuoteContext(get_config())

# 1. 获取实时行情
symbols = ["AAPL.US", "TSLA.US", "NVDA.US"]
print("=" * 60)
print("实时行情")
print("=" * 60)
quotes = ctx.quote(symbols)
for q in quotes:
    change_rate = (q.last_done - q.prev_close) / q.prev_close * 100 if q.prev_close else Decimal(0)
    print(f"  {q.symbol}  最新: {q.last_done}  涨跌: {change_rate:.2f}%  成交量: {q.volume}")

# 2. 获取标的基本信息
print("\n" + "=" * 60)
print("标的基本信息")
print("=" * 60)
info = ctx.static_info(symbols)
for s in info:
    print(f"  {s.symbol}  名称: {s.name_cn}  交易所: {s.exchange}")

# 3. 获取历史 K 线 (日K, 最近 10 根)
print("\n" + "=" * 60)
print("AAPL.US 日K (最近 10 根)")
print("=" * 60)
candlesticks = ctx.candlesticks("AAPL.US", Period.Day, 10, AdjustType.ForwardAdjust)
for c in candlesticks:
    print(f"  {c.timestamp}  开: {c.open}  高: {c.high}  低: {c.low}  收: {c.close}  量: {c.volume}")
