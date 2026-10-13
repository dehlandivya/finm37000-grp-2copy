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

The exact Databento schema and sample period will be determined during initial data exploration.

A Databento API key and appropriate CME data access will be required. API credentials and raw market data will **not** be committed to the repository. Local raw data should be stored in the git-ignored `data/` directory.

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
