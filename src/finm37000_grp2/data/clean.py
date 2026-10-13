"""Clean and validate ES top-of-book data (issue #7).

`clean()` turns raw Databento `mbp-1` records (from `ingest.read_raw`) into an
event-level dataset. That schema is the interface between the data half and
the analysis half of the pipeline; it is documented in `docs/data-schema.md`.

Two `mbp-1` details shape the design (checked on real 2026 samples):

- Trade rows (`action == "T"`) carry the book *before* the trade and do not
  have the F_LAST flag. The trade's effect on the book appears in the next
  F_LAST row of the same packet. OFI and other book features must therefore
  use `book_states()`, which keeps F_LAST rows only.
- Several 1-lot fills from one match event are reported as identical rows
  (same ts_event, sequence, price, size). They are separate trades, so exact
  duplicates are kept.
"""

import logging
from datetime import date, time
from pathlib import Path

import numpy as np
import pandas as pd

from .ingest import REPO_ROOT

logger = logging.getLogger(__name__)

# TODO(#8): move to config.py.
PROCESSED_DIR = REPO_ROOT / "data" / "processed"  # git-ignored

TZ = "America/Chicago"
RTH_START = time(8, 30)  # CT, inclusive
RTH_END = time(15, 15)  # CT, exclusive
# Holiday-shortened sessions in the research sample (README Data appendix).
HOLIDAYS = frozenset({date(2026, 7, 3), date(2026, 9, 7)})

F_LAST = 0x80  # Databento flag: last record of an exchange packet

ACTIONS = ["A", "C", "M", "R", "T", "F"]  # Add, Cancel, Modify, cleaR, Trade, Fill
SIDES = ["A", "B", "N"]  # Ask, Bid, None

# Raw mbp-1 column -> clean column.
RENAME = {
    "bid_px_00": "bid_px",
    "ask_px_00": "ask_px",
    "bid_sz_00": "bid_sz",
    "ask_sz_00": "ask_sz",
}

# Clean schema, in column order. The index is `ts_event`.
SCHEMA = {
    "ts_recv": "datetime64[ns, UTC]",
    "instrument_id": "uint32",
    "sequence": "int64",
    "flags": "uint8",
    "action": pd.CategoricalDtype(ACTIONS),
    "side": pd.CategoricalDtype(SIDES),
    "price": "float64",
    "size": "int64",
    "bid_px": "float64",
    "ask_px": "float64",
    "bid_sz": "int64",
    "ask_sz": "int64",
    "locked": "bool",
    "roll": "bool",
    "session_start": "bool",
}

# Columns that may never be NaN (`price` is undefined for some actions).
REQUIRED = [c for c in SCHEMA if c != "price"]


def session_date(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Chicago calendar date of each timestamp, as naive midnight timestamps."""
    return index.tz_convert(TZ).normalize().tz_localize(None)


def in_rth(index: pd.DatetimeIndex) -> np.ndarray:
    """True for timestamps inside 08:30-15:15 CT on a non-holiday."""
    local = index.tz_convert(TZ)
    minute = local.hour * 60 + local.minute
    start = RTH_START.hour * 60 + RTH_START.minute
    end = RTH_END.hour * 60 + RTH_END.minute
    holiday = session_date(index).isin(pd.to_datetime(sorted(HOLIDAYS)))
    return np.asarray((minute >= start) & (minute < end) & ~holiday)


def _mark_segments(df: pd.DataFrame) -> pd.DataFrame:
    """Set `roll` and `session_start` from the rows present in `df`.

    `session_start` marks the first row of each session, and `roll` a row
    whose `instrument_id` differs from the previous row in `df`. Features
    that difference consecutive rows (returns, OFI) must reset wherever
    either is True. With `ES.v.0` the roll happens overnight, so when
    sessions are processed one at a time it only shows up as a new
    `instrument_id` at a `session_start`.
    """
    df = df.copy()
    day = pd.Series(session_date(df.index))
    inst = df["instrument_id"].reset_index(drop=True)
    df["session_start"] = day.ne(day.shift()).to_numpy()
    df["roll"] = (inst.ne(inst.shift()) & inst.index.to_series().gt(0)).to_numpy()
    return df


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean raw `mbp-1` records into the event-level schema.

    Steps:

    - Index by `ts_event` (UTC, ns) and keep `ts_recv`. Rows are stably
      sorted by (`ts_event`, `sequence`), so records within one packet keep
      their original order (a trade row stays before its F_LAST book row).
    - Keep regular trading hours, 08:30-15:15 CT, minus `HOLIDAYS`.
    - Drop rows with an undefined or crossed best bid/ask, or a non-positive
      top-of-book size. Locked books (`bid_px == ask_px`) are kept and
      flagged in `locked`.
    - Cast sizes to int64 so differences can go negative (raw sizes are
      uint32 and wrap around).
    - Add `roll` and `session_start` (see `_mark_segments`).

    Exact duplicate rows are kept: they are separate fills from one match
    event. See `docs/data-schema.md` for the full schema and invariants.
    """
    df = raw.reset_index().rename(columns=RENAME)
    df = df.sort_values(["ts_event", "sequence"], kind="stable")
    df = df.set_index("ts_event")
    df.index = df.index.as_unit("ns")

    df = df[in_rth(df.index)]

    book = df[["bid_px", "ask_px", "bid_sz", "ask_sz"]]
    bad = (
        book.isna().any(axis=1)
        | (df["bid_px"] > df["ask_px"])
        | (df["bid_sz"] <= 0)
        | (df["ask_sz"] <= 0)
    )
    if bad.any():
        logger.info("Dropping %d rows with undefined or crossed books", bad.sum())
    df = df[~bad]

    df["locked"] = df["bid_px"] == df["ask_px"]
    df = _mark_segments(df)
    return df[list(SCHEMA)].astype(SCHEMA)


def validate(df: pd.DataFrame) -> None:
    """Raise ValueError if `df` does not satisfy the clean schema."""
    problems = []

    idx = df.index
    if idx.name != "ts_event" or str(idx.dtype) != "datetime64[ns, UTC]":
        problems.append("index must be `ts_event` with dtype datetime64[ns, UTC]")
    elif not idx.is_monotonic_increasing:
        problems.append("index is not sorted by ts_event")

    missing = [c for c in SCHEMA if c not in df.columns]
    if missing:
        problems.append(f"missing columns: {missing}")
    for col, dtype in SCHEMA.items():
        if col in df.columns and df[col].dtype != dtype:
            problems.append(f"{col} has dtype {df[col].dtype}, expected {dtype}")
    if problems:
        raise ValueError("; ".join(problems))

    nan_cols = [c for c in REQUIRED if df[c].isna().any()]
    if nan_cols:
        problems.append(f"NaNs in required columns: {nan_cols}")
    if (df["bid_px"] > df["ask_px"]).any():
        problems.append("crossed books (bid_px > ask_px)")
    if not df["locked"].equals(df["bid_px"] == df["ask_px"]):
        problems.append("`locked` does not match bid_px == ask_px")
    if (df["bid_sz"] <= 0).any() or (df["ask_sz"] <= 0).any():
        problems.append("non-positive top-of-book sizes")
    if not in_rth(idx).all():
        problems.append("rows outside regular trading hours")
    if problems:
        raise ValueError("; ".join(problems))


def book_states(df: pd.DataFrame) -> pd.DataFrame:
    """Complete book states only: the input for OFI, OBI, midprice, etc.

    Keeps rows with the F_LAST flag, which drops trade rows (pre-trade book)
    and intermediate records within a packet. `roll` and `session_start` are
    recomputed so they mark the first *kept* row of each segment.
    """
    return _mark_segments(df[(df["flags"] & F_LAST) != 0])


def trades(df: pd.DataFrame) -> pd.DataFrame:
    """Trade rows. `side` is the aggressor; `price`/`size` are the fill."""
    return df[df["action"] == "T"]


def processed_path(day: date | str, *, root: str | Path | None = None) -> Path:
    """Parquet path for one session: data/processed/ES/{YYYY-MM-DD}.parquet."""
    root = PROCESSED_DIR if root is None else Path(root)
    return root / "ES" / f"{pd.Timestamp(day):%Y-%m-%d}.parquet"


def write_clean(df: pd.DataFrame, *, root: str | Path | None = None) -> list[Path]:
    """Validate and write `df` as one Parquet file per session; return paths."""
    validate(df)
    paths = []
    for day, part in df.groupby(session_date(df.index), sort=True):
        path = processed_path(day, root=root)
        path.parent.mkdir(parents=True, exist_ok=True)
        part.to_parquet(path)
        paths.append(path)
    return paths


def read_clean(day: date | str, *, root: str | Path | None = None) -> pd.DataFrame:
    """Read one cleaned session written by `write_clean`."""
    return pd.read_parquet(processed_path(day, root=root))
