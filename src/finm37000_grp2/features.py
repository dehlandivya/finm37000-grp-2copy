"""Calculate order book features from ES futures market data.

These features describe the current state of the order book,
including prices, liquidity, and potential buying/selling pressure.

We will later analyze whether these features can predict
short-term price movements in ES futures.
"""

import numpy as np


def calculate_midprice(bid_price: float, ask_price: float) -> float:
    """Calculate the midpoint between the best bid and ask prices."""

    # The bid is the highest price buyers are willing to pay.
    # The ask is the lowest price sellers are willing to accept.
    # Their average provides a simple estimate of the market's midprice.
    return (bid_price + ask_price) / 2


def calculate_spread(bid_price: float, ask_price: float) -> float:
    """Calculate the difference between the best ask and bid prices."""

    # The spread measures the gap between buying and selling prices.
    # A smaller spread generally indicates a more liquid market
    # and a lower cost of trading immediately.
    return ask_price - bid_price


def calculate_obi(bid_size, ask_size):
    """Calculate order book imbalance from displayed bid and ask sizes."""

    # Convert to float before subtracting to avoid unsigned integer overflow.
    # NumPy arrays also allow us to process entire DataFrame columns.
    bid_size = np.asarray(bid_size, dtype="float64")
    ask_size = np.asarray(ask_size, dtype="float64")

    # Reject missing or non-finite order quantities.
    if not np.isfinite(bid_size).all() or not np.isfinite(ask_size).all():
        raise ValueError("Bid and ask sizes must be finite numbers.")

    # Reject negative sizes anywhere in the input.
    if (bid_size < 0).any() or (ask_size < 0).any():
        raise ValueError("Bid and ask sizes cannot be negative.")

    total_size = bid_size + ask_size

    # Avoid dividing by zero.
    if (total_size == 0).any():
        raise ValueError("Total order book size cannot be zero.")

    return (bid_size - ask_size) / total_size


def calculate_microprice(bid_price, ask_price, bid_size, ask_size):
    """Calculate the quantity-weighted microprice from bid/ask data."""

    # Convert inputs to NumPy arrays so the function can process
    # individual values or entire DataFrame columns.
    bid_price = np.asarray(bid_price, dtype="float64")
    ask_price = np.asarray(ask_price, dtype="float64")
    bid_size = np.asarray(bid_size, dtype="float64")
    ask_size = np.asarray(ask_size, dtype="float64")

    # Reject missing or non-finite prices and order quantities.
    if not all(
        np.isfinite(values).all()
        for values in (bid_price, ask_price, bid_size, ask_size)
    ):
        raise ValueError("Bid/ask prices and sizes must be finite numbers.")

    # Reject negative order sizes.
    if (bid_size < 0).any() or (ask_size < 0).any():
        raise ValueError("Bid and ask sizes cannot be negative.")

    total_size = bid_size + ask_size

    # Avoid division by zero when there are no displayed orders.
    if (total_size == 0).any():
        raise ValueError("Total order book size cannot be zero.")

    # Microprice = (ask_price * bid_size + bid_price * ask_size)
    #              / (bid_size + ask_size)
    #
    # Unlike the regular midprice, microprice considers order sizes.
    #
    # If bid_size > ask_size, the microprice shifts toward the ask.
    # If ask_size > bid_size, the microprice shifts toward the bid.
    #
    # This makes microprice a possible indicator of short-term
    # price pressure, which we will evaluate in our analysis.
    return (ask_price * bid_size + bid_price * ask_size) / total_size
