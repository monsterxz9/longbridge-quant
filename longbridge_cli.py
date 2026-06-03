"""Longbridge CLI adapter.

The project treats the `longbridge` executable as the data provider and keeps
strategy code independent from SDK objects.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

import pandas as pd

Runner = Callable[[list[str]], str]

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

FUNDAMENTAL_FIELDS: tuple[str, ...] = (
    "pe",
    "pb",
    "dps_rate",
    "turnover_rate",
    "volume_ratio",
    "amplitude",
    "capital_flow",
    "ytd_change_rate",
    "half_year_change_rate",
    "five_day_change_rate",
    "ten_day_change_rate",
    "mktcap",
    "last_done",
)

FUNDAMENTAL_FIELD_MAP: dict[str, str] = {
    "pe": "pe_ttm",
    "pb": "pb",
    "dps_rate": "dividend_yield",
    "turnover_rate": "turnover_rate",
    "volume_ratio": "volume_ratio",
    "amplitude": "amplitude",
    "capital_flow": "capital_flow",
    "ytd_change_rate": "ytd_return",
    "half_year_change_rate": "half_year_return",
    "five_day_change_rate": "five_day_return",
    "ten_day_change_rate": "ten_day_return",
    "mktcap": "market_cap",
    "last_done": "last_done",
}

FUNDAMENTAL_COLUMNS: list[str] = ["symbol", *FUNDAMENTAL_FIELD_MAP.values()]


class LongbridgeCLIError(RuntimeError):
    """Raised when the Longbridge CLI command or JSON output is unusable."""


def parse_json_output(text: str) -> Any:
    """Parse JSON from CLI stdout, ignoring colored update banners if present."""
    clean = ANSI_RE.sub("", text).strip()
    for i, char in enumerate(clean):
        if char not in "[{":
            continue
        try:
            return json.loads(clean[i:])
        except json.JSONDecodeError:
            continue
    raise LongbridgeCLIError("longbridge CLI did not return JSON output")


def _safe_float(value: Any) -> float:
    if value is None or value == "":
        return float("nan")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return number if math.isfinite(number) else float("nan")


def _safe_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def _default_runner(command: list[str]) -> str:
    if shutil.which(command[0]) is None:
        raise LongbridgeCLIError(
            f"未找到 `{command[0]}`，请先安装 Longbridge CLI 并确认 PATH 可用"
        )
    proc = subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise LongbridgeCLIError(
            f"longbridge CLI 执行失败 ({proc.returncode}): {' '.join(command)}\n{detail}"
        )
    return proc.stdout


class LongbridgeCLI:
    """Small typed wrapper over `longbridge ... --format json`."""

    def __init__(self, binary: str = "longbridge", runner: Runner | None = None) -> None:
        self.binary = binary
        self.runner = runner or _default_runner

    def run_json(self, *args: str) -> Any:
        command = [self.binary, *args, "--format", "json"]
        return parse_json_output(self.runner(command))

    def check(self) -> dict[str, Any]:
        data = self.run_json("check")
        if not isinstance(data, dict):
            raise LongbridgeCLIError("longbridge check returned non-object JSON")
        return data

    def quote(self, symbols: list[str]) -> list[dict[str, Any]]:
        if not symbols:
            return []
        data = self.run_json("quote", *symbols)
        if not isinstance(data, list):
            raise LongbridgeCLIError("longbridge quote returned non-list JSON")
        return data

    def static_info(self, symbols: list[str]) -> list[dict[str, Any]]:
        if not symbols:
            return []
        data = self.run_json("static", *symbols)
        if not isinstance(data, list):
            raise LongbridgeCLIError("longbridge static returned non-list JSON")
        return data

    def security_list(
        self,
        market: str = "US",
        page_size: int = 500,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            data = self.run_json(
                "security-list",
                market,
                "--page",
                str(page),
                "--count",
                str(page_size),
            )
            if not isinstance(data, list):
                raise LongbridgeCLIError("longbridge security-list returned non-list JSON")
            rows.extend(data)
            if len(data) < page_size:
                break
        return rows

    def daily_candles(
        self,
        symbol: str,
        count: int = 300,
        period: str = "day",
        adjust: str = "forward",
        session: str | None = None,
    ) -> pd.DataFrame:
        args = [
            "kline",
            symbol,
            "--period",
            period,
            "--count",
            str(count),
            "--adjust",
            adjust,
        ]
        if session:
            args.extend(["--session", session])
        data = self.run_json(*args)
        if not isinstance(data, list):
            raise LongbridgeCLIError("longbridge kline returned non-list JSON")

        rows = [
            {
                "date": item.get("time"),
                "open": _safe_float(item.get("open")),
                "high": _safe_float(item.get("high")),
                "low": _safe_float(item.get("low")),
                "close": _safe_float(item.get("close")),
                "volume": _safe_int(item.get("volume")),
            }
            for item in data
        ]
        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        if df.empty:
            return df
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    def calc_indexes(
        self,
        symbols: list[str],
        fields: tuple[str, ...] = FUNDAMENTAL_FIELDS,
    ) -> list[dict[str, Any]]:
        if not symbols:
            return []
        data = self.run_json("calc-index", *symbols, "--fields", ",".join(fields))
        if not isinstance(data, list):
            raise LongbridgeCLIError("longbridge calc-index returned non-list JSON")
        return data

    def fundamental_indexes(self, symbols: list[str]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for item in self.calc_indexes(symbols, FUNDAMENTAL_FIELDS):
            row = {"symbol": item.get("symbol")}
            for cli_field, col_name in FUNDAMENTAL_FIELD_MAP.items():
                row[col_name] = _safe_float(item.get(cli_field))
            rows.append(row)
        return pd.DataFrame(rows, columns=FUNDAMENTAL_COLUMNS)

    def capital_flow(self, symbol: str) -> list[dict[str, Any]]:
        data = self.run_json("capital", symbol, "--flow")
        if not isinstance(data, list):
            raise LongbridgeCLIError("longbridge capital --flow returned non-list JSON")
        return data

    def capital_distribution(self, symbol: str) -> dict[str, Any]:
        data = self.run_json("capital", symbol)
        if not isinstance(data, dict):
            raise LongbridgeCLIError("longbridge capital returned non-object JSON")
        return data

