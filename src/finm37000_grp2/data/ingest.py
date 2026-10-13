"""Databento ingestion for CME ES futures (issue #6)."""

import logging
import os
from pathlib import Path

import databento as db
import pandas as pd
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

DATASET = "GLBX.MDP3"
DEFAULT_SYMBOL = "ES.c.0"  # continuous, calendar-front contract
DEFAULT_SCHEMA = "mbp-1"  # top of book + trades
DEFAULT_STYPE_IN = "continuous"
# The team's CME Plus plan includes L0/L1 history (mbp-1, tbbo, ...) and the
# last month of L2/L3 (mbp-10, mbo), so anything billed is unexpected.
DEFAULT_MAX_COST = 0.0

# Resolved from the repo root so it doesn't depend on the working directory.
# TODO(#8): move to config.py.
REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "data" / "raw"  # git-ignored


def get_client() -> db.Historical:
    """Build a Databento client from DATABENTO_API_KEY (environment or `.env`)."""
    load_dotenv(REPO_ROOT / ".env")
    key = os.environ.get("DATABENTO_API_KEY")
    if not key:
        raise RuntimeError(
            "DATABENTO_API_KEY is not set. Copy .env.example to .env and set "
            "your key (see README 'How to Run')."
        )
    return db.Historical(key)


def _as_list(symbols: str | list[str]) -> list[str]:
    return [symbols] if isinstance(symbols, str) else list(symbols)


def estimate_cost(
    symbols: str | list[str],
    start: str,
    end: str,
    *,
    dataset: str = DATASET,
    schema: str = DEFAULT_SCHEMA,
    stype_in: str = DEFAULT_STYPE_IN,
) -> float:
    """Return the estimated download cost in USD."""
    return get_client().metadata.get_cost(
        dataset=dataset,
        symbols=_as_list(symbols),
        stype_in=stype_in,
        schema=schema,
        start=start,
        end=end,
    )


def raw_path(
    symbols: str | list[str],
    start: str,
    end: str,
    *,
    dataset: str = DATASET,
    schema: str = DEFAULT_SCHEMA,
    stype_in: str = DEFAULT_STYPE_IN,
) -> Path:
    """Cache path: data/raw/{dataset}/{schema}/{symbols}_{start}_{end}.dbn.zst.

    `stype_in` changes how Databento interprets `symbols`, so non-default modes
    get a `_{stype_in}` suffix to keep their cache files distinct.
    """
    name = f"{'-'.join(_as_list(symbols))}_{start}_{end}"
    if stype_in != DEFAULT_STYPE_IN:
        name += f"_{stype_in}"
    for ch in ":/\\ ":
        name = name.replace(ch, "-")
    return RAW_DIR / dataset / schema / f"{name}.dbn.zst"


def load_raw(
    symbols: str | list[str],
    start: str,
    end: str,
    *,
    dataset: str = DATASET,
    schema: str = DEFAULT_SCHEMA,
    stype_in: str = DEFAULT_STYPE_IN,
    force: bool = False,
    max_cost: float | None = DEFAULT_MAX_COST,
    max_size_gb: float | None = None,
) -> Path:
    """Download raw data once to data/raw/ and return the cached file's path.

    start/end are UTC ISO strings, e.g. "2026-10-08T13:30". If the file
    already exists, no API request is made unless `force=True`. The estimated
    cost and billable (uncompressed) size are logged before downloading; if
    either exceeds `max_cost` or `max_size_gb`, the download is aborted. Pass
    `max_cost=None` to allow billed requests.
    """
    path = raw_path(
        symbols, start, end, dataset=dataset, schema=schema, stype_in=stype_in
    )
    if path.exists() and not force:
        logger.info("Using cached %s", path)
        return path

    client = get_client()
    params = dict(
        dataset=dataset,
        symbols=_as_list(symbols),
        stype_in=stype_in,
        schema=schema,
        start=start,
        end=end,
    )
    cost = client.metadata.get_cost(**params)
    size_gb = client.metadata.get_billable_size(**params) / 1e9
    logger.info("Estimated Databento cost: $%.4f, size: %.2f GB", cost, size_gb)
    if max_cost is not None and cost > max_cost:
        raise RuntimeError(
            f"Estimated cost ${cost:.4f} exceeds max_cost ${max_cost:.4f}; "
            "aborting download. The request is likely outside the CME Plus "
            "plan (e.g. mbp-10/mbo older than 1 month); pass max_cost=None "
            "to allow billed requests."
        )
    if max_size_gb is not None and size_gb > max_size_gb:
        raise RuntimeError(
            f"Estimated size {size_gb:.2f} GB exceeds max_size_gb "
            f"{max_size_gb:.2f} GB; aborting download."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    client.timeseries.get_range(**params, path=path)
    logger.info("Downloaded %s", path)
    return path


def read_raw(path: str | Path) -> pd.DataFrame:
    """Read a cached DBN file into a DataFrame (indexed by ts_recv, UTC)."""
    return db.DBNStore.from_file(path).to_df()
