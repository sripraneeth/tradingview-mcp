import pytest

from tradingview_mcp.core.services.orb_predictor import calculate_orb_levels


def test_calculate_orb_levels_uses_atr_when_session_open_missing() -> None:
    result = calculate_orb_levels(
        open_price=100.0,
        high=110.0,
        low=90.0,
        atr=2.0,
        session_open=None,
    )

    assert result["small_range_high"] == 101.0
    assert result["small_range_low"] == 99.0
    assert result["range_high"] == 102.0
    assert result["range_low"] == 98.0
    assert result["large_range_high"] == 103.0
    assert result["large_range_low"] == 97.0

    metadata = result["metadata"]
    assert metadata["range_estimate"] == 2.0
    assert metadata["range_source"] == "atr"
    assert metadata["session_open"] is None


def test_calculate_orb_levels_uses_session_range_when_session_open_provided() -> None:
    result = calculate_orb_levels(
        open_price=50.0,
        high=56.0,
        low=52.0,
        atr=9.0,
        session_open=50.12345,
    )

    assert result["small_range_high"] == 52.0
    assert result["small_range_low"] == 48.0
    assert result["range_high"] == 54.0
    assert result["range_low"] == 46.0
    assert result["large_range_high"] == 56.0
    assert result["large_range_low"] == 44.0

    metadata = result["metadata"]
    assert metadata["range_estimate"] == 4.0
    assert metadata["range_source"] == "session_range"
    assert metadata["session_open"] == 50.1235
    assert metadata["atr"] == 9.0


def test_calculate_orb_levels_returns_expected_keys() -> None:
    result = calculate_orb_levels(
        open_price=10.0,
        high=12.0,
        low=8.0,
        atr=1.5,
        session_open=None,
    )

    assert set(result.keys()) == {
        "small_range_high",
        "small_range_low",
        "range_high",
        "range_low",
        "large_range_high",
        "large_range_low",
        "metadata",
    }

    assert set(result["metadata"].keys()) == {
        "open_price",
        "range_estimate",
        "range_source",
        "atr",
        "session_open",
        "session_high",
        "session_low",
        "precision",
    }


@pytest.mark.parametrize(
    ("kwargs", "error_message"),
    [
        (
            {
                "open_price": 100.0,
                "high": 90.0,
                "low": 95.0,
                "atr": 1.0,
                "session_open": None,
            },
            "high must be greater than or equal to low",
        ),
        (
            {
                "open_price": 100.0,
                "high": 105.0,
                "low": 95.0,
                "atr": -0.01,
                "session_open": None,
            },
            "atr must be non-negative",
        ),
        (
            {
                "open_price": float("inf"),
                "high": 105.0,
                "low": 95.0,
                "atr": 1.0,
                "session_open": None,
            },
            "open_price must be finite",
        ),
    ],
)
def test_calculate_orb_levels_validation_errors(kwargs: dict, error_message: str) -> None:
    with pytest.raises(ValueError, match=error_message):
        calculate_orb_levels(**kwargs)
