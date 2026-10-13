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

The primary data source will be CME market data obtained through Databento.

The initial instrument will be:

- **E-mini S&P 500 Futures (`ES`)**

If time and data availability permit, the analysis may be extended to E-mini Nasdaq-100 (`NQ`) futures as a robustness test.

We expect to use high-frequency market data containing:

- Best bid and ask prices
- Best bid and ask quantities
- Trades and trading volume
- Timestamps
- Contract and instrument information

From these data, we will construct variables including:

- Midprice
- Bid-ask spread
- Order book imbalance
- Order flow imbalance
- Microprice
- Recent returns
- Trading intensity
- Realized volatility
- Liquidity measures

### Data Specification

Every member pulls identical data with the settings below. The defaults live in `src/finm37000_grp2/data/ingest.py`.

| Item | Choice |
|---|---|
| Dataset | `GLBX.MDP3` (CME Globex MDP 3.0) |
| Primary schema | `mbp-1`: every top-of-book update plus every trade |
| Metadata schema | `definition`: contract code (`raw_symbol`, e.g. `ESZ6`), tick size (0.25), multiplier (50), expiration |
| Symbol | `ES.v.0` with `stype_in="continuous"` (front contract by volume) |
| Session | RTH only, 08:30–15:15 CT |
| Dev sample | 2026-10-08 RTH (`2026-10-08T13:30` to `2026-10-08T20:15` UTC) |
| Research sample | 2026-07-01 to 2026-09-30 RTH: 66 weekdays, 64 full sessions, including the Sep 2026 roll |
| Optional robustness | `NQ.v.0` with the same settings, only if time permits |

**Why `mbp-1`.** All features in the [Methodology](#methodology) use only the best level of the book. OBI, midprice and microprice need the best bid/ask prices and sizes. OFI needs every change at the best quotes, not snapshots. Forward midprice returns and execution delay need the BBO at arbitrary times. `mbp-1` has all of this in one event stream, including trades with aggressor side.

- `tbbo` only records quotes at trade times, so OFI and fixed-horizon midprice returns can't be computed from it.
- `bbo-1s` and `bbo-1m` are snapshots that lose the within-interval events OFI depends on.
- `mbp-10` and `mbo` are only needed for multi-level imbalance or queue-position modelling, which are out of scope. Our CME Plus plan also covers only the most recent month of L2/L3 history.

**Symbology and rolls.** We use `ES.v.0`, which follows the contract with the highest volume, instead of the calendar-front `ES.c.0`.

- In Sep 2026, `ES.c.0` stayed on ESU6 until 09-20. By 09-17, ESU6 had about 32k RTH trades against about 246k for ESZ6, and on 09-18 it had no RTH trades at all.
- `ES.v.0` rolled ESU6 → ESZ6 on **2026-09-16**. The switch happens at 00:00 UTC (19:00 CT the previous evening), in the middle of the overnight session. With RTH only, each day therefore has a single contract, and rolls always fall between days.
- A roll shows up in the data as a change in `instrument_id` (ESU6 = `42140870`, ESZ6 = `10252`). The `symbol` column holds the requested symbol (`ES.v.0`), not the contract. To get the contract code, join `instrument_id` to `raw_symbol` from the `definition` schema.
- Downstream code flags the first row after a roll and never computes returns across it (#7).
- `ES.v.0` uses the previous day's volume, so it lags the actual liquidity crossover by a day or two (on 09-14 ESZ6 already traded more than ESU6). Analysis may exclude the roll week as a robustness check.

**Session.** We use RTH only (08:30–15:15 CT). This avoids the thin overnight book and the daily 16:00–17:00 CT maintenance halt, and cuts the data size by about 27%. The loader takes UTC timestamps, and every sample date falls in CDT (UTC−5), so RTH is 13:30–20:15 UTC. Dates after 2026-11-01 (CST, UTC−6) would be 14:30–21:15 UTC. The research sample includes two holiday-shortened sessions, 2026-07-03 and 2026-09-07. Both stop trading at 12:00 CT and have about 4% of normal volume, so they should be dropped during cleaning.

**Cost and size.** These were estimated with `metadata.get_cost`, `get_billable_size` and `get_record_count` on 2026-10-13. Sizes are uncompressed. The `.dbn.zst` files on disk are smaller.

| Sample | Schema | Records | Size | Cost |
|---|---|---|---|---|
| Dev (1 RTH day) | `mbp-1` | 6.2 M | 0.50 GB | $0.00 |
| Dev (1 RTH day) | `definition` | 1 | < 1 KB | $0.00 |
| Research (66 RTH days) | `mbp-1` | 349 M | 27.95 GB | $0.00 |
| Research | `definition` | 79 | < 1 KB | $0.00 |

The CME Plus plan covers L1 history, so everything costs $0. The loader also refuses billed requests by default (`max_cost=0`). Disk space and memory are the real limits: the research sample is too large for a single DataFrame, so the pipeline downloads and processes it one day at a time (#8).

**Fields used** (from `mbp-1`):

| Field | Use |
|---|---|
| `ts_event` | Exchange event time, the primary time index (`read_raw()` indexes by `ts_recv`, so cleaning re-indexes) |
| `ts_recv` | Capture time, used for latency and execution-delay modelling |
| `action`, `side` | Event type (`A`dd, `C`ancel, `M`odify, `T`rade in our samples); for trades, `side` is the aggressor (`B`/`A`), or `N` for auction trades at the 17:00 CT reopen |
| `price`, `size` | Event price and size (trade price and size when `action == "T"`) |
| `bid_px_00`, `ask_px_00` | Best bid/ask after the event: midprice, spread, microprice |
| `bid_sz_00`, `ask_sz_00` | Best bid/ask size: OBI, OFI, microprice. These are `uint32`, so cast to `int64` before subtracting, or `bid - ask` wraps around instead of going negative |
| `bid_ct_00`, `ask_ct_00` | Number of orders at the best bid/ask, used for liquidity measures |
| `instrument_id` | Contract identity and roll detection |
| `symbol` | Requested symbol (`ES.v.0`); not the contract code |
| `sequence`, `flags` | Ordering within a timestamp and record-quality flags |

**Checked on real data.** Small `mbp-1` pulls ($0) were read with `load_raw()` → `read_raw()`: 2026-10-08 14:00–14:01 UTC (21k rows) and 2026-09-15 20:14 UTC → 09-16 13:31 UTC across the roll (1.8M rows). All the fields above are present, with no NaN or zero top-of-book sizes. There were no crossed or locked books in the RTH minutes sampled. The only crossed rows were 3 rows at the 17:00 CT reopen, which the RTH filter removes. Cleaning (#7) should still check for them over the full sample.

**Access.** All data is pulled programmatically through the **Databento Historical API** with the `databento` Python client, using each member's **own API key** stored in a local `.env` file (see [How to Run](#how-to-run)). API credentials and raw market data will **not** be committed to the repository. Raw downloads are cached in the git-ignored `data/raw/` directory.

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

# 4. Run the tests
uv run pytest

# 5. Run the project
# Aspirational — the final entry point will execute the
# data -> features -> analysis -> backtest pipeline
uv run python -m finm37000_grp2
```

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
