import pandas as pd
import pytest

from finm37000_grp2.data import ingest


class FakeStore:
    def to_df(self):
        return pd.DataFrame({"bid_px_00": [5000.0], "ask_px_00": [5000.25]})


class FakeTimeseries:
    def __init__(self):
        self.calls = 0

    def get_range(self, **kwargs):
        self.calls += 1
        kwargs["path"].write_bytes(b"fake")   # simulate the saved file
        return FakeStore()


class FakeClient:
    def __init__(self):
        self.timeseries = FakeTimeseries()


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DATABENTO_API_KEY"):
        ingest.get_client()


def test_download_then_cache(tmp_path, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ingest, "get_client", lambda: client)
    monkeypatch.setattr(ingest.db.DBNStore, "from_file", lambda p: FakeStore())

    df1 = ingest.load_raw("2026-10-08T13:30", "2026-10-08T14:30")
    df2 = ingest.load_raw("2026-10-08T13:30", "2026-10-08T14:30")

    assert client.timeseries.calls == 1      # second call used the cache
    assert list(df1.columns) == ["bid_px_00", "ask_px_00"]
    assert df1.equals(df2)


def test_force_redownloads(tmp_path, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ingest, "get_client", lambda: client)
    monkeypatch.setattr(ingest.db.DBNStore, "from_file", lambda p: FakeStore())

    ingest.load_raw("2026-10-08T13:30", "2026-10-08T14:30")
    ingest.load_raw("2026-10-08T13:30", "2026-10-08T14:30", force=True)
    assert client.timeseries.calls == 2
