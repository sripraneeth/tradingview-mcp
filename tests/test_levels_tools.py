import unittest
from unittest.mock import patch

from tradingview_mcp.tools import futures, indices, stocks


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def _sample_pivot_levels():
    return {
        "classic": {
            "middle": 100.0,
            "support": {"S1": 99.0, "S2": 98.0, "S3": 97.0},
            "resistance": {"R1": 101.0, "R2": 102.0, "R3": 103.0},
        },
        "fibonacci": {
            "middle": 200.0,
            "support": {"S1": 199.0, "S2": 198.0, "S3": 197.0},
            "resistance": {"R1": 201.0, "R2": 202.0, "R3": 203.0},
        },
        "camarilla": {
            "middle": 300.0,
            "support": {"S1": 299.0, "S2": 298.0, "S3": 297.0},
            "resistance": {"R1": 301.0, "R2": 302.0, "R3": 303.0},
        },
    }


class TestLevelsTools(unittest.TestCase):
    def _assert_normalized_levels(self, response):
        self.assertIn("levels", response)
        levels = response["levels"]
        self.assertEqual(set(levels.keys()), {"Classic", "Fibonacci", "Camarilla"})

        for name in ("Classic", "Fibonacci", "Camarilla"):
            self.assertIn("support", levels[name])
            self.assertIn("resistance", levels[name])
            self.assertEqual(set(levels[name]["support"].keys()), {"S1", "S2", "S3"})
            self.assertEqual(set(levels[name]["resistance"].keys()), {"R1", "R2", "R3"})

    def test_stocks_levels_normalizes_schema_and_identity_fields(self):
        mcp = DummyMCP()
        stocks.register_stocks_tools(mcp)
        stocks_levels = mcp.tools["stocks_levels"]

        pivot_levels = _sample_pivot_levels()
        analysis_payload = {
            "symbol": "AAPL",
            "exchange": "NASDAQ",
            "timeframe": "1D",
            "metrics": {"pivot_levels": pivot_levels},
        }

        with patch("tradingview_mcp.tools.stocks.analyze_single", return_value=analysis_payload):
            result = stocks_levels(symbol="AAPL", exchange="NASDAQ", timeframe="1D")

        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["exchange"], "NASDAQ")
        self.assertEqual(result["timeframe"], "1D")
        self.assertEqual(result["pivot_levels"], pivot_levels)
        self._assert_normalized_levels(result)
        self.assertEqual(result["levels"]["Classic"], pivot_levels["classic"])
        self.assertEqual(result["levels"]["Fibonacci"], pivot_levels["fibonacci"])
        self.assertEqual(result["levels"]["Camarilla"], pivot_levels["camarilla"])

    def test_futures_levels_normalizes_schema_and_identity_fields(self):
        mcp = DummyMCP()
        futures.register_futures_tools(mcp)
        futures_levels = mcp.tools["futures_levels"]

        pivot_levels = _sample_pivot_levels()
        analysis_payload = {
            "symbol": "ES1!",
            "exchange": "CME_MINI",
            "timeframe": "15m",
            "metrics": {"pivot_levels": pivot_levels},
        }

        with patch("tradingview_mcp.tools.futures.analyze_single", return_value=analysis_payload):
            result = futures_levels(symbol="ES1!", exchange="CME_MINI", timeframe="15m")

        self.assertEqual(result["symbol"], "ES1!")
        self.assertEqual(result["exchange"], "cme_mini")
        self.assertEqual(result["timeframe"], "15m")
        self.assertEqual(result["pivot_levels"], pivot_levels)
        self._assert_normalized_levels(result)
        self.assertEqual(result["levels"]["Classic"], pivot_levels["classic"])
        self.assertEqual(result["levels"]["Fibonacci"], pivot_levels["fibonacci"])
        self.assertEqual(result["levels"]["Camarilla"], pivot_levels["camarilla"])

    def test_indices_levels_normalizes_schema_and_identity_fields(self):
        mcp = DummyMCP()
        indices.register_indices_tools(mcp)
        indices_levels = mcp.tools["indices_levels"]

        pivot_levels = _sample_pivot_levels()
        analysis_payload = {
            "symbol": "SPX",
            "exchange": "CBOE",
            "timeframe": "1D",
            "metrics": {"pivot_levels": pivot_levels},
        }

        with patch("tradingview_mcp.tools.indices.analyze_single", return_value=analysis_payload):
            result = indices_levels(symbol="SPX", exchange="CBOE", timeframe="1D")

        self.assertEqual(result["symbol"], "SPX")
        self.assertEqual(result["exchange"], "CBOE")
        self.assertEqual(result["timeframe"], "1D")
        self.assertEqual(result["pivot_levels"], pivot_levels)
        self._assert_normalized_levels(result)
        self.assertEqual(result["levels"]["Classic"], pivot_levels["classic"])
        self.assertEqual(result["levels"]["Fibonacci"], pivot_levels["fibonacci"])
        self.assertEqual(result["levels"]["Camarilla"], pivot_levels["camarilla"])

    def test_levels_tools_propagate_error_payload(self):
        error_payload = {
            "error": "No data found",
            "symbol": "UNKNOWN",
            "exchange": "TEST",
            "timeframe": "1D",
        }

        test_cases = [
            {
                "register": stocks.register_stocks_tools,
                "tool": "stocks_levels",
                "patch_target": "tradingview_mcp.tools.stocks.analyze_single",
                "kwargs": {"symbol": "UNKNOWN", "exchange": "NASDAQ", "timeframe": "1D"},
            },
            {
                "register": futures.register_futures_tools,
                "tool": "futures_levels",
                "patch_target": "tradingview_mcp.tools.futures.analyze_single",
                "kwargs": {"symbol": "UNKNOWN", "exchange": "CME_MINI", "timeframe": "15m"},
            },
            {
                "register": indices.register_indices_tools,
                "tool": "indices_levels",
                "patch_target": "tradingview_mcp.tools.indices.analyze_single",
                "kwargs": {"symbol": "UNKNOWN", "exchange": "CBOE", "timeframe": "1D"},
            },
        ]

        for case in test_cases:
            with self.subTest(tool=case["tool"]):
                mcp = DummyMCP()
                case["register"](mcp)
                tool_fn = mcp.tools[case["tool"]]

                with patch(case["patch_target"], return_value=error_payload):
                    result = tool_fn(**case["kwargs"])

                self.assertEqual(result, error_payload)


if __name__ == "__main__":
    unittest.main()
