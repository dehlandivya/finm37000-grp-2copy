"""Tests for cleaning and validating mbp-1 data, using synthetic records."""

import pandas as pd
import pytest

from finm37000_grp2.data import clean

# 2026-10-08 is on CDT, so RTH is 13:30-20:15 UTC.
T0 = pd.Timestamp("2026-10-08 14:00:00", tz="UTC")
ESZ6, ESH7 = 10252, 99999


def row(ms, action="A", side="B", *, seq=None, flags=clean.F_LAST, **kw):
    """One raw mbp-1 record at T0 + `ms` milliseconds, or at a Timestamp `ms`.

    Sequence defaults to `ms`, and the book to a 1-tick 50x12 market.
    """
    offset = isinstance(ms, int)
    ts = T0 + pd.Timedelta(milliseconds=ms) if offset else ms
    if seq is None:
        seq = ms if offset else 0
    rec = dict(
        ts_event=ts,
        ts_recv=ts + pd.Timedelta(microseconds=300),
        instrument_id=ESZ6,
        action=action,
        side=side,
        price=7831.0,
        size=1,
        flags=flags,
        sequence=seq,
        bid_px_00=7831.00,
        ask_px_00=7831.25,
        bid_sz_00=50,
        ask_sz_00=12,
        symbol="ES.v.0",
    )
    rec.update(kw)
    return rec


def make_raw(rows):
    """Shape records like `ingest.read_raw`: ts_recv index, raw dtypes."""
    df = pd.DataFrame(rows).set_index("ts_recv")
    dtypes = {
        "instrument_id": "uint32",
        "flags": "uint8",
        "sequence": "uint32",
        "size": "uint32",
        "bid_sz_00": "uint32",
        "ask_sz_00": "uint32",
    }
    return df.astype(dtypes)


def test_schema_and_validate_on_clean_input():
    df = clean.clean(make_raw([row(0), row(1), row(2)]))
    clean.validate(df)
    assert df.index.name == "ts_event"
    assert list(df.columns) == list(clean.SCHEMA)
    assert len(df) == 3


def test_sizes_are_int64_so_differences_go_negative():
    df = clean.clean(make_raw([row(0, bid_sz_00=3, ask_sz_00=10)]))
    assert (df["bid_sz"] - df["ask_sz"]).iloc[0] == -7


def test_out_of_order_rows_are_sorted():
    df = clean.clean(make_raw([row(2), row(0), row(1)]))
    assert df.index.is_monotonic_increasing
    assert list(df["sequence"]) == [0, 1, 2]


def test_same_packet_order_is_preserved():
    # A trade row and the F_LAST book update it causes share ts_event and
    # sequence. The trade must stay first.
    ts = T0 + pd.Timedelta(milliseconds=5)
    raw = make_raw(
        [
            row(ts, "T", "B", seq=7, flags=0, price=7831.25, size=12),
            row(ts, "C", "A", seq=7, ask_px_00=7831.50, ask_sz_00=51),
        ]
    )
    df = clean.clean(raw)
    assert list(df["action"]) == ["T", "C"]


def test_exact_duplicate_trades_are_kept():
    # Separate 1-lot fills from one match event are reported as identical rows.
    fill = row(5, "T", "B", seq=7, flags=0, price=7831.25)
    df = clean.clean(make_raw([row(0), fill, fill, fill]))
    assert len(clean.trades(df)) == 3


def test_crossed_book_is_dropped_and_locked_is_flagged():
    raw = make_raw(
        [
            row(0),
            row(1, bid_px_00=7831.50, ask_px_00=7831.25),  # crossed
            row(2, bid_px_00=7831.25, ask_px_00=7831.25),  # locked
        ]
    )
    df = clean.clean(raw)
    clean.validate(df)
    assert list(df["sequence"]) == [0, 2]
    assert list(df["locked"]) == [False, True]


@pytest.mark.parametrize(
    "bad",
    [
        {"bid_px_00": float("nan")},
        {"ask_px_00": float("nan")},
        {"bid_sz_00": 0},
        {"ask_sz_00": 0},
    ],
)
def test_undefined_quotes_are_dropped(bad):
    df = clean.clean(make_raw([row(0), row(1, **bad)]))
    assert list(df["sequence"]) == [0]


def test_session_filter_keeps_rth_only():
    rows = [
        row(pd.Timestamp("2026-10-08 13:29:59.999", tz="UTC"), seq=1),  # 08:29 CT
        row(pd.Timestamp("2026-10-08 13:30:00", tz="UTC"), seq=2),  # 08:30 CT
        row(pd.Timestamp("2026-10-08 20:14:59.999", tz="UTC"), seq=3),
        row(pd.Timestamp("2026-10-08 20:15:00", tz="UTC"), seq=4),  # 15:15 CT
        row(pd.Timestamp("2026-10-08 22:00:00", tz="UTC"), seq=5),  # reopen
    ]
    df = clean.clean(make_raw(rows))
    assert list(df["sequence"]) == [2, 3]


def test_session_filter_follows_daylight_saving():
    # 2026-11-02 is on CST, so RTH opens at 14:30 UTC.
    rows = [
        row(pd.Timestamp("2026-11-02 13:30:00", tz="UTC"), seq=1),
        row(pd.Timestamp("2026-11-02 14:30:00", tz="UTC"), seq=2),
    ]
    assert list(clean.clean(make_raw(rows))["sequence"]) == [2]


def test_holidays_are_dropped():
    ts = pd.Timestamp("2026-07-03 14:00:00", tz="UTC")
    assert clean.clean(make_raw([row(ts, seq=1)])).empty


def test_roll_and_session_start():
    day1 = pd.Timestamp("2026-09-15 20:00:00", tz="UTC")
    day2 = pd.Timestamp("2026-09-16 14:00:00", tz="UTC")
    rows = [
        row(day1, seq=1, instrument_id=42140870),
        row(day1 + pd.Timedelta(seconds=1), seq=2, instrument_id=42140870),
        row(day2, seq=3, instrument_id=ESZ6),
        row(day2 + pd.Timedelta(seconds=1), seq=4, instrument_id=ESZ6),
        row(day2 + pd.Timedelta(seconds=2), seq=5, instrument_id=ESH7),
    ]
    df = clean.clean(make_raw(rows))
    assert list(df["session_start"]) == [True, False, True, False, False]
    assert list(df["roll"]) == [False, False, True, False, True]


def test_book_states_keeps_f_last_rows_and_remarks_segments():
    # The session's first row is a trade (no F_LAST), so the first kept book
    # state must become the session start.
    raw = make_raw(
        [
            row(0, "T", "B", seq=1, flags=0),
            row(0, "C", "A", seq=1, ask_px_00=7831.50),
            row(1, seq=2),
        ]
    )
    df = clean.clean(raw)
    book = clean.book_states(df)
    assert list(book["sequence"]) == [1, 2]
    assert list(book["action"]) == ["C", "A"]
    assert list(book["session_start"]) == [True, False]
    assert len(clean.trades(df)) == 1


def test_validate_rejects_broken_frames():
    df = clean.clean(make_raw([row(0), row(1)]))

    with pytest.raises(ValueError, match="missing columns"):
        clean.validate(df.drop(columns="flags"))
    with pytest.raises(ValueError, match="dtype"):
        clean.validate(df.astype({"bid_sz": "uint32"}))
    with pytest.raises(ValueError, match="not sorted"):
        clean.validate(df.iloc[::-1])

    crossed = df.copy()
    crossed.loc[crossed.index[0], "bid_px"] = 7832.0
    with pytest.raises(ValueError, match="crossed"):
        clean.validate(crossed)

    nan = df.copy()
    nan.loc[nan.index[0], "ask_px"] = float("nan")
    with pytest.raises(ValueError, match="NaNs"):
        clean.validate(nan)

    outside = df.copy()
    outside.index = outside.index - pd.Timedelta(hours=6)
    outside.index.name = "ts_event"
    with pytest.raises(ValueError, match="regular trading hours"):
        clean.validate(outside)


def test_write_and_read_one_file_per_session(tmp_path):
    day2 = pd.Timestamp("2026-10-09 14:00:00", tz="UTC")
    df = clean.clean(make_raw([row(0), row(1), row(day2, seq=3)]))
    paths = clean.write_clean(df, root=tmp_path)
    assert [p.name for p in paths] == ["2026-10-08.parquet", "2026-10-09.parquet"]

    back = clean.read_clean("2026-10-08", root=tmp_path)
    clean.validate(back)
    assert back.equals(df.iloc[:2])
