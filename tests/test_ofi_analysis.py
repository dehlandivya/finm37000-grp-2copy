"""Unit tests for ES cleaned-book-state OFI module."""

import numpy as np
import pandas as pd
import pytest

from finm37000_grp2.ofi_analysis import (
    chronological_split,
    event_ofi,
    make_research_frame,
    make_second_panel,
    prepare_quotes,
)


def sample():
    times = pd.date_range("2026-10-08 13:30:00", periods=7, freq="s", tz="UTC")
    return pd.DataFrame(
        {
            "ts_event": [times[0], times[1], times[1], *times[2:]],
            "sequence": range(8),
            "instrument_id": [42] * 8,
            "bid_px": [6000, 6000, 6000, 6000.25, 6000.25, 6000.25, 6000.25, 6000.25],
            "ask_px": [
                6000.25,
                6000.25,
                6000.25,
                6000.5,
                6000.5,
                6000.5,
                6000.5,
                6000.5,
            ],
            "bid_sz": [10, 12, 14, 14, 14, 14, 14, 14],
            "ask_sz": [10] * 8,
            "session_start": [True] + [False] * 7,
            "roll": [False] * 8,
        }
    )


def test_duplicate_timestamp_preserved_and_ofi():
    q = event_ofi(prepare_quotes(sample()))
    assert len(q) == 8
    assert q["ts_event"].duplicated().sum() == 1
    assert q["ofi_event"].iloc[0] == 0
    assert q["ofi_event"].iloc[1] == 2
    assert q["ofi_event"].iloc[2] == 2
    assert q["ofi_event"].iloc[3] == 14 + 10  # bid and ask prices rise


def test_session_reset():
    s = sample()
    s.loc[4, "session_start"] = True
    q = event_ofi(prepare_quotes(s))
    assert q.loc[4, "ofi_event"] == 0
    assert q.loc[4, "segment_id"] != q.loc[3, "segment_id"]


def test_forward_returns_do_not_cross_boundary():
    q = event_ofi(prepare_quotes(sample()))
    panel = make_second_panel(q, horizons_seconds=(1, 5))
    assert len(panel) == 7
    assert np.isnan(panel["fwd_1s_ticks"].iloc[-1])
    assert panel["fwd_1s_ticks"].iloc[1] == 1
    assert panel["fwd_1s_ticks"].iloc[2] == 0
    assert panel["ofi_1s"].iloc[1] == 4
    assert np.isnan(panel["ofi_5s"].iloc[0])
    assert np.isnan(panel["fwd_5s_ticks"].iloc[-5:]).all()


def test_pipeline_and_one_session_oos_guard():
    panel = make_research_frame(sample())
    assert len(panel) == 7
    with pytest.raises(ValueError, match="at least two sessions"):
        chronological_split(panel)
