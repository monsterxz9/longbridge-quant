"""本地数据缓存层 —— 日K线、市值与基本面。

设计要点:
- 每只股票的日 K 线存为一个 parquet 文件: .cache/daily/{symbol}.parquet
- 过期就整段重拉（不做增量合并，保持代码简单正确）
- 通过 LB_CACHE_MAX_AGE_HOURS 环境变量可全局调整过期时间
- 市值快照存为单个 parquet: .cache/large_caps.parquet，每日刷新一次
- 数据入口使用 Longbridge CLI 的 JSON 输出，不依赖 Python SDK
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from lb_config import CACHE_DIR, CACHE_MAX_AGE_HOURS, LARGE_CAP_THRESHOLD
from longbridge_cli import LongbridgeCLI

DAILY_DIR = CACHE_DIR / "daily"
LARGE_CAPS_FILE = CACHE_DIR / "large_caps.parquet"
LARGE_CAPS_META = CACHE_DIR / "large_caps.meta.json"
FUNDAMENTALS_FILE = CACHE_DIR / "fundamentals.parquet"
FUNDAMENTALS_META = CACHE_DIR / "fundamentals.meta.json"


def _meta_path(symbol: str) -> Path:
    return DAILY_DIR / f"{symbol}.meta.json"


def _data_path(symbol: str) -> Path:
    return DAILY_DIR / f"{symbol}.parquet"


def _is_fresh(meta_file: Path, max_age_hours: float) -> bool:
    """判断 meta 文件对应的缓存是否仍在有效期内。"""
    if not meta_file.exists():
        return False
    try:
        meta = json.loads(meta_file.read_text())
        updated_at = datetime.fromisoformat(meta["updated_at"])
    except (json.JSONDecodeError, KeyError, ValueError):
        return False
    return datetime.now() - updated_at < timedelta(hours=max_age_hours)


def _write_meta(meta_file: Path, extra: dict | None = None) -> None:
    payload = {"updated_at": datetime.now().isoformat()}
    if extra:
        payload.update(extra)
    meta_file.write_text(json.dumps(payload, ensure_ascii=False))


def _safe_float(val) -> float:
    """将 CLI 返回的字符串/数字安全转为 float，None/NaN → NaN。"""
    if val is None or val == "":
        return float("nan")
    try:
        f = float(val)
    except (TypeError, ValueError):
        return float("nan")
    return f if math.isfinite(f) else float("nan")


def fetch_daily_cached(
    client: LongbridgeCLI,
    symbol: str,
    count: int = 300,
    max_age_hours: float | None = None,
) -> pd.DataFrame:
    """读缓存；若缓存过期或不存在则拉 API 并写回 parquet。

    返回的 DataFrame 列: date, open, high, low, close, volume（date 为 datetime）。
    """
    if max_age_hours is None:
        max_age_hours = CACHE_MAX_AGE_HOURS

    data_file = _data_path(symbol)
    meta_file = _meta_path(symbol)

    if data_file.exists() and _is_fresh(meta_file, max_age_hours):
        df = pd.read_parquet(data_file)
        # 若缓存里的数据量不够，仍要重拉
        if len(df) >= count:
            return df.tail(count).reset_index(drop=True)

    # 过期或不存在或不够 → 重新通过 CLI 拉取
    df = client.daily_candles(symbol, count=count)
    if df.empty:
        return df

    df.to_parquet(data_file, index=False)
    _write_meta(meta_file, {"count": len(df)})
    return df


def fetch_daily_batch(
    client: LongbridgeCLI,
    symbols: list[str],
    count: int = 300,
    max_age_hours: float | None = None,
    sleep: float = 0.15,
    progress: bool = True,
) -> dict[str, pd.DataFrame]:
    """批量获取日 K 线，命中缓存时不计入 sleep，未命中的才限频。

    返回 {symbol: DataFrame}。出错或空数据的 symbol 不会出现在结果中。
    """
    if max_age_hours is None:
        max_age_hours = CACHE_MAX_AGE_HOURS

    results: dict[str, pd.DataFrame] = {}
    total = len(symbols)
    hits = 0
    misses = 0
    errors = 0

    for i, sym in enumerate(symbols, 1):
        data_file = _data_path(sym)
        meta_file = _meta_path(sym)
        cache_hit = (
            data_file.exists() and _is_fresh(meta_file, max_age_hours)
        )
        try:
            df = fetch_daily_cached(client, sym, count, max_age_hours)
            if df.empty:
                errors += 1
                continue
            results[sym] = df
            if cache_hit:
                hits += 1
            else:
                misses += 1
                time.sleep(sleep)  # 仅对真正的 API 调用限频
        except Exception as e:
            errors += 1
            if progress:
                print(f"  [{sym}] 拉取失败: {type(e).__name__}: {e}")

        if progress and i % 50 == 0:
            print(
                f"  缓存进度: {i}/{total}  命中: {hits}  回源: {misses}  出错: {errors}"
            )

    if progress:
        print(
            f"  缓存完成: 共 {total} 只  命中: {hits}  回源: {misses}  出错: {errors}"
        )
    return results


def get_large_caps_cached(
    client: LongbridgeCLI,
    threshold: float = LARGE_CAP_THRESHOLD,
    max_age_hours: float = 24.0,
    force: bool = False,
) -> pd.DataFrame:
    """获取全美股市值 >= threshold 的股票快照。

    返回 DataFrame 列: symbol, market_value, last_done, exchange，按市值降序。
    缓存文件: .cache/large_caps.parquet（每日刷新一次足矣）。
    """
    if not force and LARGE_CAPS_FILE.exists() and _is_fresh(
        LARGE_CAPS_META, max_age_hours
    ):
        df = pd.read_parquet(LARGE_CAPS_FILE)
        return df[df["market_value"] >= threshold].reset_index(drop=True)

    print(f"  [large_caps] 刷新全美股市值快照（阈值 ${threshold/1e9:.0f}B）...")
    # 拉全部美股列表
    all_us = client.security_list("US")
    symbols = [str(s["symbol"]) for s in all_us if s.get("symbol")]
    print(f"  [large_caps] 全美股数量: {len(symbols)}")

    # 批量拉市值
    rows: list[dict] = []
    batch_size = 500
    indexes = ("mktcap", "last_done")
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            results = client.calc_indexes(batch, indexes)
            for r in results:
                mv = _safe_float(r.get("mktcap"))
                if mv >= threshold:
                    rows.append(
                        {
                            "symbol": r.get("symbol"),
                            "market_value": mv,
                            "last_done": _safe_float(r.get("last_done")),
                        }
                    )
        except Exception as e:
            print(f"  [large_caps] 批次 {i} 出错: {e}")
        time.sleep(0.3)

    print(f"  [large_caps] 满足市值阈值: {len(rows)} 只，补充交易所信息...")
    # 补交易所
    exch_map: dict[str, str] = {}
    syms = [r["symbol"] for r in rows]
    for i in range(0, len(syms), batch_size):
        batch = syms[i : i + batch_size]
        try:
            infos = client.static_info(batch)
            for info in infos:
                exch_map[str(info.get("symbol"))] = str(info.get("exchange") or "")
        except Exception as e:
            print(f"  [large_caps] static_info 批次 {i} 出错: {e}")
        time.sleep(0.2)

    for r in rows:
        r["exchange"] = exch_map.get(r["symbol"], "")

    df = pd.DataFrame(rows).sort_values("market_value", ascending=False).reset_index(
        drop=True
    )
    df.to_parquet(LARGE_CAPS_FILE, index=False)
    _write_meta(LARGE_CAPS_META, {"total": len(df), "threshold": threshold})
    print(f"  [large_caps] 缓存写入: {LARGE_CAPS_FILE} ({len(df)} 只)")
    return df


def fetch_fundamentals_cached(
    client: LongbridgeCLI,
    symbols: list[str],
    max_age_hours: float = 24.0,
    force: bool = False,
) -> pd.DataFrame:
    """批量获取基本面指标，24 小时缓存。

    返回 DataFrame 列: symbol, pe_ttm, pb, dividend_yield, turnover_rate,
    volume_ratio, amplitude, capital_flow, ytd_return, half_year_return,
    five_day_return, ten_day_return, market_cap, last_done
    """
    if not force and FUNDAMENTALS_FILE.exists() and _is_fresh(
        FUNDAMENTALS_META, max_age_hours
    ):
        df = pd.read_parquet(FUNDAMENTALS_FILE)
        # 只返回请求的 symbols 中有缓存的部分
        cached_syms = set(df["symbol"].tolist())
        requested = set(symbols)
        if requested.issubset(cached_syms):
            return df[df["symbol"].isin(requested)].reset_index(drop=True)

    print(f"  [fundamentals] 批量获取 {len(symbols)} 只股票的基本面数据...")
    batch_size = 500
    rows: list[dict] = []

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            df_batch = client.fundamental_indexes(batch)
            rows.extend(df_batch.to_dict("records"))
        except Exception as e:
            print(f"  [fundamentals] 批次 {i} 出错: {e}")
        time.sleep(0.3)

    if not rows:
        print("  [fundamentals] 未获取到任何数据")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df.to_parquet(FUNDAMENTALS_FILE, index=False)
    _write_meta(FUNDAMENTALS_META, {"total": len(df)})
    print(f"  [fundamentals] 缓存写入: {FUNDAMENTALS_FILE} ({len(df)} 只)")
    return df
