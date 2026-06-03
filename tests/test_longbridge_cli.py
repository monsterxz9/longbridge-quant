from __future__ import annotations

import math
import unittest

import pandas as pd

from longbridge_cli import LongbridgeCLI, parse_json_output


class LongbridgeCLITest(unittest.TestCase):
    def test_parse_json_output_ignores_cli_banner(self) -> None:
        payload = "\x1b[32mUpdated to v0.22.2\x1b[0m\n[{\"symbol\": \"AAPL.US\"}]"

        self.assertEqual(parse_json_output(payload), [{"symbol": "AAPL.US"}])

    def test_daily_candles_uses_cli_and_normalizes_dataframe(self) -> None:
        calls: list[list[str]] = []

        def runner(cmd: list[str]) -> str:
            calls.append(cmd)
            return """
            [
              {
                "time": "2026-06-01T04:00:00Z",
                "open": "309.625",
                "high": "310.940",
                "low": "305.020",
                "close": "306.310",
                "volume": "48849933"
              }
            ]
            """

        client = LongbridgeCLI(runner=runner)

        df = client.daily_candles("AAPL.US", count=1)

        self.assertEqual(
            calls[0],
            [
                "longbridge",
                "kline",
                "AAPL.US",
                "--period",
                "day",
                "--count",
                "1",
                "--adjust",
                "forward",
                "--format",
                "json",
            ],
        )
        self.assertEqual(list(df.columns), ["date", "open", "high", "low", "close", "volume"])
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["date"]))
        self.assertEqual(df.iloc[0]["close"], 306.31)
        self.assertEqual(df.iloc[0]["volume"], 48849933)

    def test_calc_indexes_maps_cli_fields_to_project_columns(self) -> None:
        def runner(cmd: list[str]) -> str:
            return """
            [
              {
                "symbol": "AAPL.US",
                "pe": "37.770",
                "pb": "43.470",
                "dps_rate": "0.33",
                "turnover_rate": "0.300",
                "volume_ratio": null,
                "amplitude": "2.861",
                "capital_flow": "-855.81",
                "ytd_change_rate": "25.4",
                "half_year_change_rate": "19.5",
                "five_day_change_rate": "6.1",
                "ten_day_change_rate": "7.2",
                "mktcap": "4629454611200.000",
                "last_done": "315.200"
              }
            ]
            """

        df = LongbridgeCLI(runner=runner).fundamental_indexes(["AAPL.US"])

        self.assertEqual(df.iloc[0]["symbol"], "AAPL.US")
        self.assertEqual(df.iloc[0]["pe_ttm"], 37.77)
        self.assertEqual(df.iloc[0]["dividend_yield"], 0.33)
        self.assertEqual(df.iloc[0]["market_cap"], 4629454611200.0)
        self.assertTrue(math.isnan(df.iloc[0]["volume_ratio"]))

    def test_security_list_pages_until_short_page(self) -> None:
        calls: list[list[str]] = []

        def runner(cmd: list[str]) -> str:
            calls.append(cmd)
            if "--page" in cmd and cmd[cmd.index("--page") + 1] == "1":
                return '[{"symbol": "AAPL.US"}, {"symbol": "MSFT.US"}]'
            return '[{"symbol": "NVDA.US"}]'

        rows = LongbridgeCLI(runner=runner).security_list(market="US", page_size=2)

        self.assertEqual([row["symbol"] for row in rows], ["AAPL.US", "MSFT.US", "NVDA.US"])
        self.assertEqual(calls[0][-6:], ["--page", "1", "--count", "2", "--format", "json"])
        self.assertEqual(calls[1][-6:], ["--page", "2", "--count", "2", "--format", "json"])


if __name__ == "__main__":
    unittest.main()
