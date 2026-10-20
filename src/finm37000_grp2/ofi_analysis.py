"""ES complete-book-state OFI research, aligned with ofi_research_updated.ipynb.

Pass ONLY clean.book_states(raw) (not trade records). One-second bars are
labeled by the START of the second; the feature becomes known at its END.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

ES_TICK_SIZE = 0.25
DEFAULT_HORIZONS = (1, 5, 10, 30, 60)


@dataclass(frozen=True)
class QuoteColumns:
    timestamp: str = "ts_event"
    bid_px: str = "bid_px"
    bid_sz: str = "bid_sz"
    ask_px: str = "ask_px"
    ask_sz: str = "ask_sz"
    symbol: str = "instrument_id"

DEFAULT_QUOTE_COLUMNS = QuoteColumns()


def prepare_quotes(
    quotes: pd.DataFrame, columns: QuoteColumns = DEFAULT_QUOTE_COLUMNS, *, file_id=0
) -> pd.DataFrame:
    """Preserve duplicate timestamps and order ties by exchange sequence."""
    df = (
        quotes.reset_index()
        if quotes.index.name == columns.timestamp
        else quotes.copy()
    )
    required = [
        columns.timestamp,
        columns.bid_px,
        columns.bid_sz,
        columns.ask_px,
        columns.ask_sz,
        columns.symbol,
        "sequence",
        "roll",
        "session_start",
    ]
    missing = [c for c in required if c not in df]
    if missing:
        raise ValueError(f"Missing cleaned book-state columns: {missing}")
    df = df.copy()
    ts = pd.to_datetime(df[columns.timestamp], utc=True)
    df["ts_event"] = ts
    for dest, src in (
        ("bid_px", columns.bid_px),
        ("ask_px", columns.ask_px),
        ("bid_sz", columns.bid_sz),
        ("ask_sz", columns.ask_sz),
    ):
        df[dest] = pd.to_numeric(df[src], errors="coerce")
    df["instrument_id"] = df[columns.symbol]
    valid = (
        df["ts_event"].notna()
        & (df["bid_px"] < df["ask_px"])
        & (df["bid_sz"] > 0)
        & (df["ask_sz"] > 0)
    )
    df = df.loc[valid].copy()
    df["_file_id"] = df.get("_file_id", file_id)
    df = df.sort_values(
        ["_file_id", "ts_event", "sequence"], kind="stable"
    ).reset_index(drop=True)
    local_day = df["ts_event"].dt.tz_convert("America/Chicago").dt.date
    boundary = (
        df["_file_id"].ne(df["_file_id"].shift())
        | df["instrument_id"].ne(df["instrument_id"].shift())
        | pd.Series(local_day).ne(pd.Series(local_day).shift())
        | df["session_start"].fillna(False).astype(bool)
        | df["roll"].fillna(False).astype(bool)
    )
    df["segment_id"] = boundary.cumsum().astype("int32")
    df["session_id"] = local_day.astype(str)
    df["symbol_id"] = df["instrument_id"].astype(str)
    df["timestamp"] = df["ts_event"]
    df["mid"] = (df["bid_px"] + df["ask_px"]) / 2
    return df


def event_ofi(quotes: pd.DataFrame) -> pd.DataFrame:
    """Cont best-level event OFI, neutral at every segment's first event."""
    df = quotes.copy()
    if "segment_id" not in df:
        raise ValueError("Call prepare_quotes before event_ofi")
    prev = df.groupby("segment_id", sort=False)[
        ["bid_px", "ask_px", "bid_sz", "ask_sz"]
    ].shift()
    ofi = (
        np.where(df["bid_px"].ge(prev["bid_px"]), df["bid_sz"], 0)
        - np.where(df["bid_px"].le(prev["bid_px"]), prev["bid_sz"].fillna(0), 0)
        - np.where(df["ask_px"].le(prev["ask_px"]), df["ask_sz"], 0)
        + np.where(df["ask_px"].ge(prev["ask_px"]), prev["ask_sz"].fillna(0), 0)
    )
    df["ofi_event"] = np.asarray(ofi, dtype=float)
    df.loc[prev["bid_px"].isna(), "ofi_event"] = 0.0
    return df


def make_second_panel(
    quotes: pd.DataFrame,
    *,
    windows_seconds: Sequence[int] = (1, 5),
    horizons_seconds: Sequence[int] = DEFAULT_HORIZONS,
    tick_size: float = ES_TICK_SIZE,
) -> pd.DataFrame:
    """Aggregate independently per session/roll/contract segment; no cross-boundary targets."""
    if tick_size <= 0 or any(v <= 0 for v in (*windows_seconds, *horizons_seconds)):
        raise ValueError("Windows, horizons, and tick size must be positive")
    if "ofi_event" not in quotes:
        quotes = event_ofi(quotes)
    panels = []
    for seg_id, group in quotes.groupby("segment_id", sort=False):
        g = group.set_index("ts_event")
        second = pd.DataFrame(
            {
                "ofi_1s": g["ofi_event"].resample("1s").sum(),
                "mid": g["mid"].resample("1s").last().ffill(),
            }
        ).dropna(subset=["mid"])
        if second.empty:
            continue
        for w in windows_seconds:
            if w != 1:
                second[f"ofi_{w}s"] = second["ofi_1s"].rolling(w, min_periods=w).sum()
        for h in horizons_seconds:
            second[f"fwd_{h}s_ticks"] = (
                second["mid"].shift(-h) - second["mid"]
            ) / tick_size
        second["segment_id"] = seg_id
        second["instrument_id"] = group["instrument_id"].iloc[0]
        second["session_date_ct"] = (
            group["ts_event"].iloc[0].tz_convert("America/Chicago").date()
        )
        second["session_id"] = str(second["session_date_ct"].iloc[0])
        panels.append(second)
    if not panels:
        raise ValueError("No usable book states")
    return (
        pd.concat(panels)
        .rename_axis("second_start_utc")
        .reset_index()
        .sort_values(["second_start_utc", "segment_id"], kind="stable")
        .reset_index(drop=True)
    )


def make_research_frame(
    raw_quotes: pd.DataFrame,
    columns: QuoteColumns = DEFAULT_QUOTE_COLUMNS,
    *,
    windows_seconds: Sequence[int] = (1, 5),
    horizons_seconds: Sequence[int] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """Accept cleaned complete book states only; returns the second-level panel."""
    return make_second_panel(
        event_ofi(prepare_quotes(raw_quotes, columns)),
        windows_seconds=windows_seconds,
        horizons_seconds=horizons_seconds,
    )


def chronological_split(df: pd.DataFrame, test_fraction: float = 0.25):
    """Split by entire local session dates, never individual event rows."""
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    days = sorted(df["session_id"].unique())
    if len(days) < 2:
        raise ValueError("Need at least two sessions for an out-of-sample split")
    cut = max(1, min(len(days) - 1, int(np.floor(len(days) * (1 - test_fraction)))))
    return (
        df.loc[df["session_id"].isin(days[:cut])].copy(),
        df.loc[df["session_id"].isin(days[cut:])].copy(),
    )


def fit_ols(train: pd.DataFrame, test: pd.DataFrame, signal: str, target: str):
    """Fit train-only univariate OLS; report OOS R² vs training mean and zero."""
    a = train[[signal, target]].replace([np.inf, -np.inf], np.nan).dropna()
    b = test[[signal, target]].replace([np.inf, -np.inf], np.nan).dropna()
    if len(a) < 3 or len(b) == 0 or a[signal].nunique() < 2:
        raise ValueError("Insufficient usable data or constant training signal")
    x = np.column_stack((np.ones(len(a)), a[signal].to_numpy(dtype=float)))
    beta = np.linalg.lstsq(x, a[target].to_numpy(dtype=float), rcond=None)[0]
    prediction = beta[0] + beta[1] * b[signal].to_numpy(dtype=float)
    actual = b[target].to_numpy(dtype=float)
    sse = float(np.sum((actual - prediction) ** 2))
    base_train = float(a[target].mean())
    denom_train = float(np.sum((actual - base_train) ** 2))
    denom_zero = float(np.sum(actual**2))
    metrics = {
        "intercept": float(beta[0]),
        "slope": float(beta[1]),
        "oos_r2_train_mean": 1 - sse / denom_train if denom_train > 0 else np.nan,
        "oos_r2_zero": 1 - sse / denom_zero if denom_zero > 0 else np.nan,
        "n_train": len(a),
        "n_test": len(b),
    }
    preds = b.copy()
    preds["prediction"] = prediction
    return metrics, preds


def conditional_quantiles(
    train: pd.DataFrame, test: pd.DataFrame, signal: str, target: str, bins: int = 10
) -> pd.DataFrame:
    """Train-derived quantile thresholds; evaluate realized returns on test."""
    a = train[signal].replace([np.inf, -np.inf], np.nan).dropna()
    if len(a) < bins:
        raise ValueError("Not enough training observations")
    edges = np.unique(np.quantile(a, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        raise ValueError("Signal has too few distinct quantile thresholds")
    edges[0], edges[-1] = -np.inf, np.inf
    b = test[[signal, target]].replace([np.inf, -np.inf], np.nan).dropna().copy()
    b["quantile"] = pd.cut(b[signal], bins=edges, labels=False, include_lowest=True)
    return (
        b.groupby("quantile", observed=True)
        .agg(
            mean_return_ticks=(target, "mean"),
            median_return_ticks=(target, "median"),
            count=(target, "size"),
            mean_ofi=(signal, "mean"),
        )
        .reset_index()
    )


def daily_slopes(df: pd.DataFrame, signal: str, target: str) -> pd.DataFrame:
    """Per-day OLS slopes; days are units for cross-day stability analysis."""
    rows = []
    for day, g in df.groupby("session_id"):
        g = g[[signal, target]].replace([np.inf, -np.inf], np.nan).dropna()
        if len(g) < 3 or g[signal].nunique() < 2:
            continue
        x = g[signal].to_numpy(dtype=float)
        y = g[target].to_numpy(dtype=float)
        slope = float(
            np.dot(x - x.mean(), y - y.mean()) / np.dot(x - x.mean(), x - x.mean())
        )
        rows.append({"session_id": day, "slope": slope, "n": len(g)})
    return pd.DataFrame(rows, columns=["session_id", "slope", "n"])


def run_horizon_summary(
    df: pd.DataFrame,
    signal: str = "ofi_1s",
    horizons_seconds: Sequence[int] = DEFAULT_HORIZONS,
    test_fraction: float = 0.25,
) -> pd.DataFrame:
    train, test = chronological_split(df, test_fraction)
    rows = []
    for h in horizons_seconds:
        target = f"fwd_{h}s_ticks"
        metrics, _ = fit_ols(train, test, signal, target)
        slopes = daily_slopes(test, signal, target)
        metrics.update(
            {
                "horizon_s": h,
                "mean_daily_slope": slopes["slope"].mean() if len(slopes) else np.nan,
                "sd_daily_slope": slopes["slope"].std(ddof=1)
                if len(slopes) > 1
                else np.nan,
                "n_test_days": len(slopes),
            }
        )
        rows.append(metrics)
    return pd.DataFrame(rows)
