import pandas as pd
import pytest

from finm37000_grp2.data import ingest

START, END = "2026-10-08T13:30", "2026-10-08T14:30"


class FakeStore:
    def to_df(self):
        return pd.DataFrame({"bid_px_00": [5000.0], "ask_px_00": [5000.25]})


class FakeTimeseries:
    def __init__(self):
        self.calls = 0

    def get_range(self, **kwargs):
        self.calls += 1
        kwargs["path"].write_bytes(b"fake")  # simulate the saved file
        return FakeStore()


class FakeMetadata:
    def __init__(self, cost, size):
        self.cost = cost
        self.size = size

    def get_cost(self, **kwargs):
        return self.cost

    def get_billable_size(self, **kwargs):
        return self.size


class FakeClient:
    # Defaults mirror a covered request under the CME Plus plan: free, ~1h mbp-1.
    def __init__(self, cost=0.0, size=80_000_000):
        self.timeseries = FakeTimeseries()
        self.metadata = FakeMetadata(cost, size)


@pytest.fixture
def client(tmp_path, monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path)
    monkeypatch.setattr(ingest, "get_client", lambda: client)
    return client


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    monkeypatch.setattr(ingest, "load_dotenv", lambda *a, **k: False)
    with pytest.raises(RuntimeError, match=r"DATABENTO_API_KEY.*\.env\.example"):
        ingest.get_client()


def test_path_scheme(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path)
    path = ingest.raw_path("ES.c.0", START, END)
    assert path == (
        tmp_path
        / "GLBX.MDP3"
        / "mbp-1"
        / "ES.c.0_2026-10-08T13-30_2026-10-08T14-30.dbn.zst"
    )


def test_path_scheme_includes_non_default_stype_in(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "RAW_DIR", tmp_path)
    path = ingest.raw_path("ESZ6", START, END, stype_in="raw_symbol")
    assert path.name == "ESZ6_2026-10-08T13-30_2026-10-08T14-30_raw_symbol.dbn.zst"
    assert path != ingest.raw_path("ESZ6", START, END)


def test_different_stype_in_is_not_a_cache_hit(client):
    ingest.load_raw("ES.c.0", START, END)
    ingest.load_raw("ES.c.0", START, END, stype_in="raw_symbol")
    assert client.timeseries.calls == 2


def test_raw_dir_is_repo_rooted():
    assert ingest.RAW_DIR == ingest.REPO_ROOT / "data" / "raw"
    assert (ingest.REPO_ROOT / "pyproject.toml").exists()


def test_cache_miss_downloads_and_writes(client):
    path = ingest.load_raw("ES.c.0", START, END)
    assert client.timeseries.calls == 1
    assert path == ingest.raw_path("ES.c.0", START, END)
    assert path.read_bytes() == b"fake"


def test_cache_hit_skips_client(client, monkeypatch):
    first = ingest.load_raw("ES.c.0", START, END)

    def fail():
        raise AssertionError("client should not be created on a cache hit")

    monkeypatch.setattr(ingest, "get_client", fail)
    assert ingest.load_raw("ES.c.0", START, END) == first
    assert client.timeseries.calls == 1


def test_force_redownloads(client):
    ingest.load_raw("ES.c.0", START, END)
    ingest.load_raw("ES.c.0", START, END, force=True)
    assert client.timeseries.calls == 2


def test_max_cost_aborts(client):
    client.metadata.cost = 10.0
    with pytest.raises(RuntimeError, match="max_cost"):
        ingest.load_raw("ES.c.0", START, END, max_cost=1.0)
    assert client.timeseries.calls == 0
    assert not ingest.raw_path("ES.c.0", START, END).exists()


def test_billed_request_aborts_by_default(client):
    client.metadata.cost = 0.31  # e.g. mbp-10 older than the plan's 1 month
    with pytest.raises(RuntimeError, match="max_cost"):
        ingest.load_raw("ES.c.0", START, END, schema="mbp-10")
    assert client.timeseries.calls == 0


def test_max_cost_none_allows_billed_request(client):
    client.metadata.cost = 0.31
    ingest.load_raw("ES.c.0", START, END, max_cost=None)
    assert client.timeseries.calls == 1


def test_max_size_aborts(client):
    client.metadata.size = 5_000_000_000
    with pytest.raises(RuntimeError, match="max_size_gb"):
        ingest.load_raw("ES.c.0", START, END, max_size_gb=1.0)
    assert client.timeseries.calls == 0
    assert not ingest.raw_path("ES.c.0", START, END).exists()


def test_read_raw(monkeypatch, tmp_path):
    monkeypatch.setattr(ingest.db.DBNStore, "from_file", lambda p: FakeStore())
    df = ingest.read_raw(tmp_path / "x.dbn.zst")
    assert list(df.columns) == ["bid_px_00", "ask_px_00"]
