import unittest

from tradingview_mcp.core.services.orb_predictor import calculate_orb_levels


class TestCalculateOrbLevels(unittest.TestCase):
    def test_uses_atr_when_session_open_missing(self) -> None:
        result = calculate_orb_levels(
            open_price=100.0,
            high=110.0,
            low=90.0,
            atr=2.0,
            session_open=None,
        )

        self.assertEqual(result["small_range_high"], 101.0)
        self.assertEqual(result["small_range_low"], 99.0)
        self.assertEqual(result["range_high"], 102.0)
        self.assertEqual(result["range_low"], 98.0)
        self.assertEqual(result["large_range_high"], 103.0)
        self.assertEqual(result["large_range_low"], 97.0)

        metadata = result["metadata"]
        self.assertEqual(metadata["range_estimate"], 2.0)
        self.assertEqual(metadata["range_source"], "atr")
        self.assertEqual(metadata["session_open"], None)

    def test_uses_session_range_when_session_open_provided(self) -> None:
        result = calculate_orb_levels(
            open_price=50.0,
            high=56.0,
            low=52.0,
            atr=9.0,
            session_open=50.12345,
        )

        self.assertEqual(result["small_range_high"], 52.0)
        self.assertEqual(result["small_range_low"], 48.0)
        self.assertEqual(result["range_high"], 54.0)
        self.assertEqual(result["range_low"], 46.0)
        self.assertEqual(result["large_range_high"], 56.0)
        self.assertEqual(result["large_range_low"], 44.0)

        metadata = result["metadata"]
        self.assertEqual(metadata["range_estimate"], 4.0)
        self.assertEqual(metadata["range_source"], "session_range")
        self.assertEqual(metadata["session_open"], 50.1235)
        self.assertEqual(metadata["atr"], 9.0)

    def test_returns_six_levels_and_metadata_keys(self) -> None:
        result = calculate_orb_levels(
            open_price=10.0,
            high=12.0,
            low=8.0,
            atr=1.5,
            session_open=None,
        )

        expected_top_keys = {
            "small_range_high",
            "small_range_low",
            "range_high",
            "range_low",
            "large_range_high",
            "large_range_low",
            "metadata",
        }
        self.assertEqual(set(result.keys()), expected_top_keys)

        expected_metadata_keys = {
            "open_price",
            "range_estimate",
            "range_source",
            "atr",
            "session_open",
            "session_high",
            "session_low",
            "precision",
        }
        self.assertEqual(set(result["metadata"].keys()), expected_metadata_keys)

    def test_validation_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "high must be greater than or equal to low"):
            calculate_orb_levels(
                open_price=100.0,
                high=90.0,
                low=95.0,
                atr=1.0,
                session_open=None,
            )

        with self.assertRaisesRegex(ValueError, "atr must be non-negative"):
            calculate_orb_levels(
                open_price=100.0,
                high=105.0,
                low=95.0,
                atr=-0.01,
                session_open=None,
            )

        with self.assertRaisesRegex(ValueError, "open_price must be finite"):
            calculate_orb_levels(
                open_price=float("inf"),
                high=105.0,
                low=95.0,
                atr=1.0,
                session_open=None,
            )


if __name__ == "__main__":
    unittest.main()
