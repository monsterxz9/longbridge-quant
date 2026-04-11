"""动态美股股票池构建。

基于 cache.get_large_caps_cached() 的全市场市值快照，按交易所过滤生成：
- all_largecap_universe     所有市值 >= 阈值的美股（~1180 只）
- nasdaq_largecap_universe  NASD 交易所大盘股（~350 只）
- tech_largecap_universe    NASD 大盘股 + NYSE 科技白名单（~370 只）

硬编码 `SECTORS`（`sectors_data.py`）仍然可用作精选关注池。
"""

from __future__ import annotations

from longbridge.openapi import QuoteContext

from cache import get_large_caps_cached
from lb_config import LARGE_CAP_THRESHOLD

# NYSE 上市的科技相关股票白名单（不在 NASDAQ 但属于科技板块）
# 增删这里以补充被 NASD 过滤规则漏掉的科技股
NYSE_TECH_WHITELIST: list[str] = [
    # 半导体
    "TSM.US", "ASML.US", "ARM.US", "GFS.US", "UMC.US",
    # 硬件/存储
    "IBM.US", "ORCL.US", "DELL.US", "HPQ.US", "HPE.US",
    "SNDK.US", "WDC.US", "STX.US", "NTAP.US",
    # 平台/消费互联网
    "UBER.US", "HOOD.US", "SQ.US", "AFRM.US",
    "SE.US", "SHOP.US", "MELI.US", "PDD.US",
    "SPOT.US", "RBLX.US", "SNAP.US", "PINS.US", "RDDT.US",
    # 网络安全 / SaaS
    "NET.US", "CRWD.US", "ZS.US", "FTNT.US", "S.US", "PANW.US",
    "TWLO.US", "HUBS.US", "VEEV.US", "BILL.US",
    # IT 服务
    "ACN.US", "INFY.US", "IT.US",
]


def all_largecap_universe(
    ctx: QuoteContext, min_market_cap: float = LARGE_CAP_THRESHOLD
) -> list[str]:
    """所有市值 >= min_market_cap 的美股列表，按市值降序。"""
    df = get_large_caps_cached(ctx, threshold=min_market_cap)
    return df["symbol"].tolist()


def nasdaq_largecap_universe(
    ctx: QuoteContext, min_market_cap: float = LARGE_CAP_THRESHOLD
) -> list[str]:
    """NASD 交易所的大盘股列表。"""
    df = get_large_caps_cached(ctx, threshold=min_market_cap)
    return df[df["exchange"] == "NASD"]["symbol"].tolist()


def tech_largecap_universe(
    ctx: QuoteContext, min_market_cap: float = LARGE_CAP_THRESHOLD
) -> list[str]:
    """科技大盘股池 = NASD 大盘股 + NYSE 科技白名单（去重）。"""
    df = get_large_caps_cached(ctx, threshold=min_market_cap)
    nasd = df[df["exchange"] == "NASD"]["symbol"].tolist()

    # 只保留在大盘股池中仍满足阈值的白名单股票
    large_cap_set = set(df["symbol"].tolist())
    whitelist = [s for s in NYSE_TECH_WHITELIST if s in large_cap_set]

    # 去重并保持大体按市值顺序（NASD 在前）
    seen: set[str] = set()
    result: list[str] = []
    for s in nasd + whitelist:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def sectors_universe() -> list[str]:
    """从硬编码 SECTORS 扁平化得到的精选关注池。"""
    from sectors_data import SECTORS

    seen: set[str] = set()
    result: list[str] = []
    for syms in SECTORS.values():
        for s in syms:
            if s not in seen:
                seen.add(s)
                result.append(s)
    return result
