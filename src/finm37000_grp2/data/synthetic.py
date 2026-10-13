"""Synthetic `mbp-1` records for running the pipeline without an API key (#8).

`raw_day()` returns a small frame shaped like `ingest.read_raw()` output, so
`clean()`, `validate()` and everything downstream run unchanged. It is not
realistic market data; it only exercises the code paths: rows outside RTH,
a crossed book, and trade rows followed by their F_LAST book update.
"""

from datetime import date

import numpy as np
import pandas as pd

from .. import config
from .clean import F_LAST, rth_bounds

TICK = 0.25
START_PX = 7000.0
INSTRUMENT_ID = 1
# Real records arrive about this long after the exchange timestamp.
RECV_DELAY = pd.Timedelta(microseconds=300)
# Extra time on each side of RTH, so the session filter has rows to drop.
PADDING = pd.Timedelta(minutes=10)

DTYPES = {
    "rtype": "uint8",
    "publisher_id": "uint16",
    "instrument_id": "uint32",
    "depth": "uint8",
    "size": "uint32",
    "flags": "uint8",
    "ts_in_delta": "int32",
    "sequence": "uint32",
    "bid_sz_00": "uint32",
    "ask_sz_00": "uint32",
    "bid_ct_00": "uint32",
    "ask_ct_00": "uint32",
}


def raw_day(day: date | str, *, n: int = 2_000) -> pd.DataFrame:
    """About `n` raw records for one session, deterministic for each `day`.

    The output has `read_raw()`'s columns and dtypes, indexed by `ts_recv`.
    """
    day = pd.Timestamp(day)
    rng = np.random.default_rng(day.toordinal())
    start, end = rth_bounds(day)
    start, end = start - PADDING, end + PADDING
    span = (end - start).value
    times = start + pd.to_timedelta(np.sort(rng.integers(0, span, n)), unit="ns")

    bid, bid_sz, ask_sz = START_PX, 50, 50
    rows = []

    def add(ts, action, side, price, size, flags, crossed=False):
        bid_px = bid + TICK if crossed else bid
        rows.append(
            dict(
                ts_event=ts,
                action=action,
                side=side,
                price=price,
                size=size,
                flags=flags,
                bid_px_00=bid_px,
                ask_px_00=bid + TICK,
                bid_sz_00=bid_sz,
                ask_sz_00=ask_sz,
            )
        )

    crossed_at = n // 2
    for i, ts in enumerate(times):
        if rng.random() < 0.05:
            # A trade row carries the pre-trade book and no F_LAST; its effect
            # appears in the next F_LAST row of the same packet.
            side = rng.choice(["A", "B"])
            price = bid + TICK if side == "B" else bid
            add(ts, "T", side, price, int(rng.integers(1, 10)), 0)
            if side == "B":
                ask_sz = int(rng.integers(1, 100))
            else:
                bid_sz = int(rng.integers(1, 100))
            add(ts, "C", "A" if side == "B" else "B", price, 1, F_LAST)
            continue
        if rng.random() < 0.05:
            bid += TICK * rng.choice([-1, 1])
        bid_sz, ask_sz = (int(x) for x in rng.integers(1, 100, 2))
        side = rng.choice(["A", "B"])
        price = bid + TICK if side == "A" else bid
        add(ts, rng.choice(["A", "C", "M"]), side, price, 1, F_LAST, i == crossed_at)

    df = pd.DataFrame(rows)
    df["ts_recv"] = df["ts_event"] + RECV_DELAY
    df["rtype"] = 1
    df["publisher_id"] = 1
    df["instrument_id"] = INSTRUMENT_ID
    df["depth"] = 0
    df["ts_in_delta"] = 10_000
    df["sequence"] = np.arange(len(df))
    df["bid_ct_00"] = 1
    df["ask_ct_00"] = 1
    df["symbol"] = config.SYMBOL
    columns = [
        "ts_recv",
        "ts_event",
        "rtype",
        "publisher_id",
        "instrument_id",
        "action",
        "side",
        "depth",
        "price",
        "size",
        "flags",
        "ts_in_delta",
        "sequence",
        "bid_px_00",
        "ask_px_00",
        "bid_sz_00",
        "ask_sz_00",
        "bid_ct_00",
        "ask_ct_00",
        "symbol",
    ]
    return df[columns].astype(DTYPES).set_index("ts_recv")
