"""Data pipeline: Databento -> raw cache -> clean Parquet, one session at a time.

The research sample is too large for one DataFrame (README Data appendix), so
each session is downloaded, cleaned and written before the next one starts.
Member D's feature, analysis and backtest stages read the Parquet files with
`clean.read_clean` and plug in after `run_data`.
"""

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from . import config
from .data import clean, ingest, synthetic

logger = logging.getLogger(__name__)


def output_dir(*, offline: bool = False) -> Path:
    """Root for processed Parquet files; offline runs never touch real data."""
    return config.OFFLINE_DIR if offline else config.PROCESSED_DIR


def load_day(day: date, *, force: bool = False, offline: bool = False) -> pd.DataFrame:
    """Raw records for one session's RTH, from Databento or the fixture."""
    if offline:
        return synthetic.raw_day(day)
    start, end = (f"{t:%Y-%m-%dT%H:%M}" for t in clean.rth_bounds(day))
    path = ingest.load_raw(config.SYMBOL, start, end, force=force)
    return ingest.read_raw(path)


def run_data(
    sample: str = "dev", *, force: bool = False, offline: bool = False
) -> list[Path]:
    """Write clean Parquet for every session in `sample`; return the paths.

    Sessions whose Parquet file already exists are skipped unless `force`,
    which also downloads the raw data again. With `offline`, synthetic records
    replace Databento (no API key needed) and output goes to
    `config.OFFLINE_DIR`.
    """
    s = config.SAMPLES[sample]
    root = output_dir(offline=offline)
    days = clean.session_dates(s.start, s.end)
    logger.info("Sample %r: %d sessions, %s to %s", sample, len(days), s.start, s.end)

    paths = []
    for i, day in enumerate(days, 1):
        path = clean.processed_path(day, root=root)
        if path.exists() and not force:
            logger.info("[%d/%d] %s: using %s", i, len(days), day, path)
            paths.append(path)
            continue
        df = clean.clean(load_day(day, force=force, offline=offline))
        if df.empty:
            logger.warning("[%d/%d] %s: no RTH data, skipping", i, len(days), day)
            continue
        paths += clean.write_clean(df, root=root)
        logger.info("[%d/%d] %s: wrote %d rows to %s", i, len(days), day, len(df), path)
    return paths
