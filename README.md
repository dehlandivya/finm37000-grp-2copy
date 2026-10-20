# FINM 37000 — Group 2 Project

## From Order Book Imbalance to Executable Alpha

### Project Goal

This project investigates whether information contained in the limit order book can predict short-horizon price movements in CME equity index futures and whether this predictive information can be converted into an executable trading strategy.

Using high-frequency CME E-mini S&P 500 (`ES`) futures data from Databento, we will study signals including order book imbalance, order flow imbalance, and microprice. We will evaluate both their statistical predictive power and whether any identified alpha survives realistic bid-ask spreads, transaction costs, and execution delays.

## Desired Outcome

The desired outcome is a reproducible quantitative research pipeline that takes raw CME futures market data through the full process:

**Market Data → Order Book Features → Alpha Research → Execution Analysis → Strategy Backtest**

The completed project will:

- Construct high-frequency order book and market microstructure features from CME futures data.
- Test whether order book imbalance, order flow, and microprice predict subsequent midprice movements over short horizons.
- Measure how quickly identified predictive signals decay.
- Develop a rules-based trading strategy based on the strongest identified signals.
- Evaluate whether statistical alpha remains economically meaningful after bid-ask spreads, transaction costs, and execution delays.
- Produce figures and performance statistics including signal decay, P&L, Sharpe ratio, maximum drawdown, win rate, turnover, and P&L per trade.
- Provide a reproducible entry point allowing another user with Databento access to run the analysis.

The project does **not** assume that order book signals will ultimately generate profitable trading performance. A finding that statistical predictability disappears after realistic execution assumptions would also be a meaningful outcome.

## Data

We use CME Globex market data for E-mini S&P 500 futures (`ES`) from Databento. It is pulled through the Databento Historical API with each member's own API key, stored in a git-ignored `.env` file (see [How to Run](#how-to-run)). Raw data is cached in the git-ignored `data/raw/` directory and is never committed.

| Item | Specification |
|---|---|
| Dataset | `GLBX.MDP3` (CME Globex MDP 3.0) |
| Schemas | `mbp-1` (top-of-book updates and trades), `definition` (contract metadata) |
| Symbol | `ES.v.0`, `stype_in="continuous"` (front contract by volume) |
| Session | Regular trading hours, 08:30–15:15 CT |
| Dev sample | 2026-10-08 |
| Research sample | 2026-07-01 to 2026-09-30 |
| Fields | `ts_event`, `ts_recv`, `action`, `side`, `price`, `size`, `bid_px_00`, `ask_px_00`, `bid_sz_00`, `ask_sz_00`, `bid_ct_00`, `ask_ct_00`, `instrument_id`, `sequence`, `flags` |
| Robustness (optional) | `NQ.v.0` with the same settings |

Schema choice, roll handling, cost estimates and data-processing notes are in the [Appendix](#appendix-data-specification-notes).

### In-sample / out-of-sample split

The research sample is split once, in `src/finm37000_grp2/config.py`, so every
analysis uses the same definition.

| Sample          | Dates                    | Sessions | Use |
|-----------------|--------------------------|----------|-----|
| `in_sample`     | 2026-07-01 to 2026-08-31 | 43       | Signal research, model estimation and parameter choices (horizons, thresholds) |
| `out_of_sample` | 2026-09-01 to 2026-09-30 | 21       | Final strategy backtest only, run once after parameters are frozen |
| `dev`           | 2026-10-08               | 1        | Code development and debugging; no conclusions are drawn from it |

Session counts exclude the holiday-shortened days (2026-07-03 in-sample,
2026-09-07 out-of-sample). The out-of-sample month also contains the
ESU6 to ESZ6 roll on 2026-09-16, so the backtest is tested around a roll.

Rules:

- Research notebooks and modules use `in_sample` only, selected by sample name
  (for example `--sample in_sample`) rather than hard-coded dates.
- Do not look at out-of-sample results until strategy parameters are frozen.
  The backtest on `out_of_sample` is run once.



The cleaned dataset that feeds the analysis is documented in [`docs/data-schema.md`](docs/data-schema.md).

## Research Questions

The analysis will focus on four primary questions:

1. **Predictability:** Does order book imbalance predict subsequent short-horizon midprice movements in ES futures?

2. **Incremental information:** Do dynamic measures such as order flow imbalance and microprice provide predictive information beyond static order book imbalance?

3. **Alpha decay:** How quickly does the predictive information contained in the order book decay across different forecast horizons?

4. **Tradability:** Does any identified statistical predictability remain economically meaningful after incorporating bid-ask spreads, transaction costs, and execution delays?

Potential prediction horizons include 1, 5, 10, 30, and 60 seconds.

## Methodology

### Order Book Features

Order book imbalance will initially be defined as

$$
\mathrm{OBI}_t = \frac{Q^{\text{bid}}_t - Q^{\text{ask}}_t}{Q^{\text{bid}}_t + Q^{\text{ask}}_t}
$$

where $Q^{\text{bid}}_t$ and $Q^{\text{ask}}_t$ are the displayed quantities at the best bid and ask.

The midprice will be

$$
M_t = \frac{P^{\text{bid}}_t + P^{\text{ask}}_t}{2}
$$

We will also construct the quantity-weighted microprice

$$
P^{\text{micro}}_t = \frac{P^{\text{ask}}_t \, Q^{\text{bid}}_t + P^{\text{bid}}_t \, Q^{\text{ask}}_t}{Q^{\text{bid}}_t + Q^{\text{ask}}_t}
$$

Additional dynamic features such as order flow imbalance, trading intensity, recent returns, volume, volatility, and liquidity may be incorporated as the research develops.

### Alpha Research

We will test whether these features predict subsequent midprice movements over multiple short horizons.

Initial analysis will use conditional return analysis and interpretable statistical models such as linear and logistic regression. More complex models may be explored if they provide meaningful incremental predictive value.

The analysis will emphasize:

- Conditional future returns
- Directional predictability
- Signal strength
- Alpha decay
- Stability through time
- Performance across different volatility and liquidity regimes

### Execution Analysis

Predictive accuracy alone does not imply a profitable trading strategy. We will therefore incorporate execution assumptions into the analysis.

At minimum, the project will model aggressive execution in which trades cross the prevailing bid-ask spread.

We will investigate how strategy performance changes with:

- Bid-ask spread
- Transaction costs
- Execution delay
- Signal threshold
- Holding period

If feasible given the available data, we will additionally investigate passive execution and post-trade markouts as measures of adverse selection.

### Backtesting

Signals that demonstrate out-of-sample predictive power will be converted into rules-based trading strategies.

Backtests will preserve the chronological ordering of observations and use chronological train/test splits or walk-forward evaluation to minimize look-ahead bias.

Strategy evaluation will include metrics such as:

- Cumulative P&L
- Sharpe ratio
- Maximum drawdown
- Win rate
- P&L per trade
- Turnover
- Number of trades
- Transaction-cost sensitivity

## How to Run

The project uses `uv` for environment management.

```bash
# 1. Clone your fork
git clone https://github.com/<your-username>/finm37000-grp-2.git
cd finm37000-grp-2

# 2. Create the environment and install dependencies
uv sync

# 3. Configure your own Databento API key (https://databento.com/portal/keys)
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
# then edit .env and set DATABENTO_API_KEY=<your key>   (.env is git-ignored)

# 4. Run the tests (no API key needed)
uv run pytest

# 5. Download the dev sample (one RTH session) and write clean Parquet
uv run python -m finm37000_grp2 --sample dev
```

The pipeline runs `load_raw` → `read_raw` → `clean` → `validate` → Parquet one session at a time, for the samples defined in `src/finm37000_grp2/config.py`:

- Raw downloads are cached in `data/raw/`, and clean sessions are written to `data/processed/ES/{YYYY-MM-DD}.parquet` (read them with `clean.read_clean`). Both are git-ignored.
- `--sample research` runs the full research period (64 sessions, about 28 GB uncompressed to download).
- Sessions already in `data/processed/` are skipped, so an interrupted run resumes where it stopped. `--force` downloads and cleans everything again.
- `--offline` runs the same pipeline on synthetic data with no API key, writing to `data/processed/offline/`. It only checks the code; the data is not realistic.

Downloads abort if Databento estimates any cost, since everything we use is covered by the CME Plus plan.

During development, exploratory analysis will also be available through notebooks in the `notebooks/` directory.

The final repository will provide instructions for reproducing the primary analysis from CME data obtained through Databento.

## Repository Layout

```text
.
├── src/finm37000_grp2/   # Data, features, signals, execution, and backtesting
├── tests/                # pytest tests
├── notebooks/            # Exploratory research and analysis
├── data/                 # Local market data (git-ignored)
├── docs/                 # Assignment docs, roles, and planning notes
└── .github/              # Issue/PR templates and CI
```

## Roadmap

Implementation is organized through GitHub Issues covering:

1. CME/Databento data sourcing and contract selection
2. Market data ingestion and validation
3. Construction of a clean research dataset
4. Order book feature engineering
5. Short-horizon alpha research and signal decay
6. Execution and transaction-cost modeling
7. Strategy backtesting and robustness analysis
8. Final visualizations, documentation, and reproducibility

See the repository's open GitHub Issues for detailed goals, acceptance criteria, dependencies, and task ownership.

## Team

Team roles and responsibilities are documented in `docs/roles.md`.

The project follows a pull-request workflow in which team members contribute to and review the README and issue roadmap before implementation.

## Appendix: Data Specification Notes

**Schema.** Every feature in the Methodology uses only the best level of the book. OFI needs every change at the best quotes, so `mbp-1` is the right schema. `tbbo` (quotes only at trade times) and `bbo-1s` (1-second snapshots) miss those changes. `mbp-10` and `mbo` aren't needed, and our CME Plus plan covers only their most recent month.

**Rolls.** `ES.v.0` is used instead of `ES.c.0` because the calendar roll stays on the expiring contract after its liquidity has gone. In Sep 2026, ESU6 had no RTH trades on 09-18, but `ES.c.0` only rolled on 09-20. `ES.v.0` rolled ESU6 → ESZ6 on 2026-09-16 at 00:00 UTC, so every RTH day contains a single contract. A roll shows up as a change in `instrument_id`, and returns are never computed across one (#7).

**Cost and size** (estimated 2026-10-13, uncompressed). Everything is $0 under the CME Plus plan.

| Sample | `mbp-1` records | Size |
|---|---|---|
| Dev (1 day) | 6.2 M | 0.50 GB |
| Research (66 weekdays) | 349 M | 27.95 GB |

The research sample is too large for one DataFrame, so it is downloaded and processed one RTH session at a time.

**Processing notes** (from checking small real samples):

- **Time conversion:** RTH is 13:30–20:15 UTC while Chicago is on CDT, and 14:30–21:15 UTC on CST.
- **Holidays:** drop the holiday-shortened sessions on 2026-07-03 and 2026-09-07.
- **Contract code:** the `symbol` column holds `ES.v.0`. Get the contract code (e.g. `ESZ6`) by joining `instrument_id` to `raw_symbol` from `definition`, which also gives tick size (0.25) and multiplier (50).
- **Size dtype:** sizes are `uint32`. Cast them to `int64` before subtracting, or `bid - ask` wraps around instead of going negative.
- **Time index:** `read_raw()` indexes by `ts_recv`. Re-index by `ts_event` when cleaning.
- **Reopen artifacts:** crossed books and `side == "N"` trades appear at the 17:00 CT reopen. The RTH filter removes them.
