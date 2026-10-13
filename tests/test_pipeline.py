"""Tests for config, the synthetic fixture and the end-to-end data pipeline.

Nothing here needs an API key or the network: Databento is either replaced by
the synthetic fixture (`--offline`) or by fakes of `ingest.load_raw`.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from finm37000_grp2 import config, pipeline
from finm37000_grp2.__main__ import main
from finm37000_grp2.data import clean, ingest, synthetic

# `read_raw()` columns and dtypes, checked on a real ES mbp-1 file.
RAW_DTYPES = {
    "ts_event": "datetime64[ns, UTC]",
    "rtype": "uint8",
    "publisher_id": "uint16",
    "instrument_id": "uint32",
    "action": "object",
    "side": "object",
    "depth": "uint8",
    "price": "float64",
    "size": "uint32",
    "flags": "uint8",
    "ts_in_delta": "int32",
    "sequence": "uint32",
    "bid_px_00": "float64",
    "ask_px_00": "float64",
    "bid_sz_00": "uint32",
    "ask_sz_00": "uint32",
    "bid_ct_00": "uint32",
    "ask_ct_00": "uint32",
    "symbol": "object",
}


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """Send all pipeline output to tmp_path, and fail on any API access."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(config, "OFFLINE_DIR", tmp_path / "offline")
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)

    def no_client():
        raise AssertionError("the Databento API must not be used")

    monkeypatch.setattr(ingest, "get_client", no_client)
    return tmp_path


def test_paths_are_repo_rooted():
    assert (config.REPO_ROOT / "pyproject.toml").exists()
    assert config.RAW_DIR == config.REPO_ROOT / "data" / "raw"
    assert config.PROCESSED_DIR == config.REPO_ROOT / "data" / "processed"


def test_research_sessions_skip_weekends_and_holidays():
    s = config.SAMPLES["research"]
    days = clean.session_dates(s.start, s.end)
    assert len(days) == 64  # 66 weekdays minus 07-03 and 09-07
    assert days[0] == date(2026, 7, 1) and days[-1] == date(2026, 9, 30)
    assert not config.HOLIDAYS & set(days)
    assert all(d.weekday() < 5 for d in days)


def test_rth_bounds_follow_daylight_saving():
    start, end = clean.rth_bounds("2026-10-08")  # CDT
    assert start == pd.Timestamp("2026-10-08 13:30", tz="UTC")
    assert end == pd.Timestamp("2026-10-08 20:15", tz="UTC")
    start, _ = clean.rth_bounds("2026-11-02")  # CST
    assert start == pd.Timestamp("2026-11-02 14:30", tz="UTC")


def test_synthetic_day_looks_like_read_raw():
    raw = synthetic.raw_day("2026-10-08")
    assert raw.index.name == "ts_recv"
    assert str(raw.index.dtype) == "datetime64[ns, UTC]"
    dtypes = {c: str(t) for c, t in raw.dtypes.items()}
    # Newer pandas reports text columns as "str" instead of "object".
    dtypes = {c: "object" if t == "str" else t for c, t in dtypes.items()}
    assert dtypes == RAW_DTYPES
    assert raw.equals(synthetic.raw_day("2026-10-08"))  # deterministic


def test_synthetic_day_exercises_cleaning():
    raw = synthetic.raw_day("2026-10-08")
    df = clean.clean(raw)
    clean.validate(df)
    assert 0 < len(df) < len(raw)  # out-of-RTH and crossed rows are dropped
    assert not clean.in_rth(pd.DatetimeIndex(raw["ts_event"])).all()
    trades = clean.trades(df)
    assert len(trades) > 0
    assert (trades["flags"] & clean.F_LAST == 0).all()


def test_offline_end_to_end_without_api_key(dirs, capsys):
    main(["--offline", "--sample", "dev"])

    path = dirs / "offline" / "ES" / "2026-10-08.parquet"
    assert path.exists()
    assert not (dirs / "processed").exists()  # real outputs are untouched
    df = clean.read_clean("2026-10-08", root=dirs / "offline")
    clean.validate(df)
    assert df["session_start"].sum() == 1
    assert "1 clean session file(s)" in capsys.readouterr().out


def test_existing_sessions_are_skipped_unless_forced(dirs, monkeypatch):
    calls = []
    real = synthetic.raw_day
    monkeypatch.setattr(
        synthetic, "raw_day", lambda day: calls.append(day) or real(day)
    )

    first = pipeline.run_data("dev", offline=True)
    assert pipeline.run_data("dev", offline=True) == first
    assert len(calls) == 1
    pipeline.run_data("dev", offline=True, force=True)
    assert len(calls) == 2


def test_online_downloads_each_rth_session(dirs, monkeypatch):
    calls = []

    def fake_load_raw(symbols, start, end, *, force=False):
        calls.append((symbols, start, end, force))
        return Path(start)  # stands in for the cached file

    monkeypatch.setattr(ingest, "load_raw", fake_load_raw)
    monkeypatch.setattr(ingest, "read_raw", lambda p: synthetic.raw_day(p.name[:10]))

    paths = pipeline.run_data("dev")
    assert calls == [("ES.v.0", "2026-10-08T13:30", "2026-10-08T20:15", False)]
    assert paths == [dirs / "processed" / "ES" / "2026-10-08.parquet"]
    clean.validate(clean.read_clean("2026-10-08", root=dirs / "processed"))


def test_session_without_rth_data_is_skipped(dirs, monkeypatch):
    raw = synthetic.raw_day("2026-10-08")
    after_close = raw[raw["ts_event"] >= clean.rth_bounds("2026-10-08")[1]]
    monkeypatch.setattr(pipeline, "load_day", lambda day, **kw: after_close)
    assert pipeline.run_data("dev") == []
