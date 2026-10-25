"""Central configuration (issue #8): paths, Databento settings and samples.

Everything else reads these values from here. See PLANNING.md Data for the reasons
behind each choice.
"""

from dataclasses import dataclass
from datetime import date, time
from pathlib import Path

# Paths, resolved from the repo root so they don't depend on the working
# directory. Everything under data/ is git-ignored.
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
# Output of `--offline` runs, kept apart from real data.
OFFLINE_DIR = PROCESSED_DIR / "offline"

# Databento request.
DATASET = "GLBX.MDP3"
SCHEMA = "mbp-1"  # top of book + trades
SYMBOL = "ES.v.0"  # continuous, highest-volume contract
STYPE_IN = "continuous"
PRODUCT = SYMBOL.split(".")[0]  # "ES": subdirectory for processed files
# The team's CME Plus plan includes L0/L1 history (mbp-1, tbbo, ...) and the
# last month of L2/L3 (mbp-10, mbo), so anything billed is unexpected.
MAX_COST = 0.0

# Session: regular trading hours, in exchange time.
TZ = "America/Chicago"
RTH_START = time(8, 30)  # CT, inclusive
RTH_END = time(15, 15)  # CT, exclusive
# Holiday-shortened sessions in the research sample (PLANNING.md Data appendix).
HOLIDAYS = frozenset({date(2026, 7, 3), date(2026, 9, 7)})


@dataclass(frozen=True)
class Sample:
    """A range of session dates, both ends inclusive."""

    start: date
    end: date


SAMPLES = {
    "dev": Sample(date(2026, 10, 8), date(2026, 10, 8)),
    "research": Sample(date(2026, 7, 1), date(2026, 9, 30)),
    # Split of the research sample (issue #17). All signal research uses
    # in_sample only. out_of_sample was reserved for a strategy backtest that
    # was not run because no signal cleared the spread (README).
    "in_sample": Sample(date(2026, 7, 1), date(2026, 8, 31)),
    "out_of_sample": Sample(date(2026, 9, 1), date(2026, 9, 30)),
}
