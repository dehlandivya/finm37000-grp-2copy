"""The in-sample / out-of-sample split (issue #17) is well formed."""

from datetime import date, timedelta

from finm37000_grp2 import config


def _sessions(sample):
    """Weekdays in the sample that are not holiday-shortened sessions."""
    out, d = [], sample.start
    while d <= sample.end:
        if d.weekday() < 5 and d not in config.HOLIDAYS:
            out.append(d)
        d += timedelta(days=1)
    return out


def test_split_samples_exist():
    assert {"in_sample", "out_of_sample"} <= set(config.SAMPLES)


def test_split_is_contiguous_and_covers_research_sample():
    ins = config.SAMPLES["in_sample"]
    oos = config.SAMPLES["out_of_sample"]
    research = config.SAMPLES["research"]
    assert ins.start == research.start
    assert oos.end == research.end
    assert oos.start == ins.end + timedelta(days=1)


def test_no_overlap_between_in_and_out_of_sample():
    ins = _sessions(config.SAMPLES["in_sample"])
    oos = _sessions(config.SAMPLES["out_of_sample"])
    assert not set(ins) & set(oos)
    assert max(ins) < min(oos)


def test_session_counts_add_up_to_research_sample():
    ins = _sessions(config.SAMPLES["in_sample"])
    oos = _sessions(config.SAMPLES["out_of_sample"])
    research = _sessions(config.SAMPLES["research"])
    assert len(ins) == 43
    assert len(oos) == 21
    assert len(ins) + len(oos) == len(research) == 64


def test_dev_sample_is_outside_the_research_period():
    dev = config.SAMPLES["dev"]
    research = config.SAMPLES["research"]
    assert dev.start > research.end


def test_holidays_and_roll_fall_in_the_expected_periods():
    ins = config.SAMPLES["in_sample"]
    oos = config.SAMPLES["out_of_sample"]
    assert ins.start <= date(2026, 7, 3) <= ins.end
    assert oos.start <= date(2026, 9, 7) <= oos.end
    assert oos.start <= date(2026, 9, 16) <= oos.end  # ESU6 -> ESZ6 roll
