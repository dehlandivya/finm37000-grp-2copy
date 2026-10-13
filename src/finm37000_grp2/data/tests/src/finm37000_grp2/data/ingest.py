"""Databento ingestion for CME ES futures (issue: data ingestion/loading)."""
import os
from pathlib import Path

import databento as db
import pandas as pd

DATASET = "GLBX.MDP3"
DEFAULT_SYMBOL = "ES.c.0"   # continuous, calendar-front contract
DEFAULT_SCHEMA = "mbp-1"    # top of book + trades
RAW_DIR = Path("data/raw")  # git-ignored


def get_client() -> db.Historical:
    """Build a Databento client from the DATABENTO_API_KEY env variable."""
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError("DATABENTO_API_KEY is not set. See README 'How to Run'.")
    return db.Historical(key)


def estimate_cost(start: str, end: str, symbol: str = DEFAULT_SYMBOL,
                  schema: str = DEFAULT_SCHEMA) -> float:
    """Return the estimated download cost in USD. Always check before pulling."""
    return get_client().metadata.get_cost(
        dataset=DATASET,
        symbols=[symbol],
        stype_in="continuous",
        schema=schema,
        start=start,
        end=end,
    )


def _cache_path(symbol: str, schema: str, start: str, end: str) -> Path:
    tag = f"{symbol}_{schema}_{start}_{end}"
    for ch in ":/ ":
        tag = tag.replace(ch, "-")
    return RAW_DIR / f"{tag}.dbn.zst"


def load_raw(start: str, end: str, symbol: str = DEFAULT_SYMBOL,
             schema: str = DEFAULT_SCHEMA, force: bool = False) -> pd.DataFrame:
    """Download once to data/raw/, then reuse the cached file.

    start/end are UTC ISO strings, e.g. "2026-10-08T13:30".
    Returns a DataFrame indexed by ts_recv (UTC), prices as floats.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, schema, start, end)

    if path.exists() and not force:
        store = db.DBNStore.from_file(path)
    else:
        store = get_client().timeseries.get_range(
            dataset=DATASET,
            symbols=[symbol],
            stype_in="continuous",
            schema=schema,
            start=start,
            end=end,
            path=path,
        )
    return store.to_df()
