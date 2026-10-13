
"""Calculate order book features from ES futures market data.

These features describe the current state of the order book,
including prices, liquidity, and potential buying/selling pressure.

We will later analyze whether these features can predict
short-term price movements in ES futures.
"""


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


def calculate_obi(bid_size: float, ask_size: float) -> float:
    """Calculate Order Book Imbalance (OBI) using top-of-book quantities."""

    # Bid size = number of contracts available at the best bid.
    # Ask size = number of contracts available at the best ask.
    # Together, these represent displayed liquidity at the top of the book.
    total_size = bid_size + ask_size

    # Negative quantities are invalid because order sizes cannot
    # represent a negative number of contracts.
    if bid_size < 0 or ask_size < 0:
        raise ValueError("Bid and ask sizes cannot be negative.")

    # Avoid dividing by zero when both sides have no displayed quantity.
    if total_size == 0:
        raise ValueError("Total order book size cannot be zero.")

    # OBI = (bid_size - ask_size) / (bid_size + ask_size)
    #
    # Positive OBI: more contracts at the bid than the ask.
    # Negative OBI: more contracts at the ask than the bid.
    # OBI = 0: equal quantities on both sides.
    #
    # OBI ranges from -1 to +1 for valid nonnegative quantities.
    # We will test whether OBI predicts future price movements.
    return (bid_size - ask_size) / total_size


def calculate_microprice(
    bid_price: float,
    ask_price: float,
    bid_size: float,
    ask_size: float,
) -> float:
    """Calculate the microprice using bid/ask prices and quantities."""

    # Check that displayed order quantities are valid.
    if bid_size < 0 or ask_size < 0:
        raise ValueError("Bid and ask sizes cannot be negative.")

    total_size = bid_size + ask_size

    # Both quantities cannot be zero because we need
    # a positive total size to calculate a weighted price.
    if total_size == 0:
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
    return (
        ask_price * bid_size + bid_price * ask_size
    ) / total_size

