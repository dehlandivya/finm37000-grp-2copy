
"""Tests for order book feature calculations.

These tests use synthetic (made-up) market data so that
we can verify the calculations without downloading
real Databento data.
"""

import pytest

from finm37000_grp2.features import (
    calculate_midprice,
    calculate_spread,
    calculate_obi,
    calculate_microprice,
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
