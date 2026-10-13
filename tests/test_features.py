"""Tests for order book feature calculations.

These tests use synthetic (made-up) market data so that
we can verify the calculations without downloading
real Databento data.
"""

import numpy as np
import pandas as pd
import pytest

from finm37000_grp2.features import (
    calculate_microprice,
    calculate_midprice,
    calculate_obi,
    calculate_spread,
)


def test_midprice():
    """Check that midprice is the average of bid and ask."""
    result = calculate_midprice(5800.00, 5800.25)
    assert result == pytest.approx(5800.125)


def test_spread():
    """Check that spread equals ask price minus bid price."""
    result = calculate_spread(5800.00, 5800.25)
    assert result == pytest.approx(0.25)


def test_obi():
    """Check OBI when there is more quantity on the bid side."""
    result = calculate_obi(120, 40)
    assert result == pytest.approx(0.5)


def test_obi_balanced():
    """Check that equal bid and ask sizes produce zero imbalance."""
    result = calculate_obi(100, 100)
    assert result == pytest.approx(0.0)


def test_obi_negative():
    """Check OBI when there is more quantity on the ask side."""
    result = calculate_obi(40, 120)
    assert result == pytest.approx(-0.5)


def test_microprice():
    """Check the quantity-weighted microprice calculation."""
    result = calculate_microprice(5800.00, 5800.25, 120, 40)
    assert result == pytest.approx(5800.1875)


def test_obi_zero_size():
    """OBI should reject an order book with zero total quantity."""
    with pytest.raises(ValueError):
        calculate_obi(0, 0)


def test_microprice_negative_size():
    """Microprice should reject negative order quantities."""
    with pytest.raises(ValueError):
        calculate_microprice(5800.00, 5800.25, -10, 40)


def test_obi_uint32():
    bid = np.uint32(40)
    ask = np.uint32(120)

    result = calculate_obi(bid, ask)

    assert result == pytest.approx(-0.5)


def test_obi_pandas_series():
    """Check that OBI works on multiple observations at once."""

    # Simulate two rows of market data.
    bid_sizes = pd.Series([20, 40])
    ask_sizes = pd.Series([26, 20])

    result = calculate_obi(bid_sizes, ask_sizes)

    # Compare against the expected OBI for each row.
    np.testing.assert_allclose(result, [-6 / 46, 20 / 60])


def test_microprice_pandas_series():
    """Check that microprice works on multiple observations at once."""

    # Simulate two rows of market data.
    bid_prices = pd.Series([100.0, 101.0])
    ask_prices = pd.Series([101.0, 102.0])
    bid_sizes = pd.Series([20, 40])
    ask_sizes = pd.Series([30, 20])

    result = calculate_microprice(bid_prices, ask_prices, bid_sizes, ask_sizes)

    # Compare against the expected microprice for each row.
    np.testing.assert_allclose(
        result,
        [
            (101 * 20 + 100 * 30) / 50,
            (102 * 40 + 101 * 20) / 60,
        ],
    )


def test_obi_missing_size():
    """OBI should reject missing order quantities."""
    with pytest.raises(ValueError):
        calculate_obi(20, np.nan)


def test_microprice_missing_price():
    """Microprice should reject missing prices."""
    with pytest.raises(ValueError):
        calculate_microprice(np.nan, 5800.25, 120, 40)


def test_obi_infinite_size():
    """OBI should reject infinite order quantities."""
    with pytest.raises(ValueError):
        calculate_obi(20, np.inf)
