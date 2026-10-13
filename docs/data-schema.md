# Clean Data Schema (#7)

`finm37000_grp2.data.clean.clean(raw)` turns raw Databento `mbp-1` records
into the event-level dataset below. This schema is the interface between the
data pipeline (#7, #8) and the analysis (#2). `validate(df)` checks every
invariant listed here.

```python
from finm37000_grp2.data import clean, ingest

df = clean.clean(ingest.read_raw(path))
clean.write_clean(df)  # data/processed/ES/{YYYY-MM-DD}.parquet
df = clean.read_clean("2026-10-08")

book = clean.book_states(df)  # input for OFI, OBI, midprice, microprice
fills = clean.trades(df)  # trade prints
```

## Columns

One row per raw `mbp-1` record, indexed by `ts_event`.

| Column | dtype | Notes |
|---|---|---|
| `ts_event` (index) | `datetime64[ns, UTC]` | Exchange event time, sorted |
| `ts_recv` | `datetime64[ns, UTC]` | Databento capture time |
| `instrument_id` | `uint32` | Changes on a contract roll |
| `sequence` | `int64` | Exchange message sequence number. Fills from one match event share it; a trade and its book update need not |
| `flags` | `uint8` | Databento flags; `0x80` (`F_LAST`) marks a complete book state |
| `action` | `category` | `A`dd, `C`ancel, `M`odify, clea`R`, `T`rade, `F`ill |
| `side` | `category` | `A`sk, `B`id, `N`one. For trades, the aggressor |
| `price`, `size` | `float64`, `int64` | Event price and size (fill price and size for trades). `price` may be NaN |
| `bid_px`, `ask_px` | `float64` | Best bid and ask |
| `bid_sz`, `ask_sz` | `int64` | Displayed size at the best bid and ask |
| `locked` | `bool` | `bid_px == ask_px` |
| `roll` | `bool` | `instrument_id` differs from the previous row |
| `session_start` | `bool` | First row of an RTH session |

Sizes are `int64` (raw data is `uint32`) so that differences such as
`bid_sz - ask_sz` can go negative.

## Invariants

- Only regular trading hours: 08:30–15:15 CT, excluding 2026-07-03 and
  2026-09-07.
- No NaNs in any column except `price`.
- `bid_px <= ask_px`. Crossed books are dropped, and locked books are kept
  and flagged.
- `bid_sz > 0` and `ask_sz > 0`.
- Rows from one packet keep their original order.

## Using the data for features

**Use `book_states(df)` for book features.** It keeps only `F_LAST` rows. In
`mbp-1`, a trade row carries the book *before* the trade and is not
`F_LAST`. The trade's effect on the book appears in the next `F_LAST` row
from the same packet, so dropping trade rows loses no book information.
`book_states` recomputes `roll` and `session_start` for the rows it keeps.

**Reset at segment boundaries.** Anything computed from consecutive rows
(returns, OFI) must not span a row where `roll | session_start` is True.
`ES.v.0` rolls overnight, so when sessions are cleaned one at a time a roll
only appears as a new `instrument_id` at a `session_start`.

**Duplicates are real.** Several fills from one match event are reported as
identical `T` rows (same `ts_event`, `sequence`, price and size), so exact
duplicates are kept. Count volume with `trades(df)["size"].sum()`.

**Not included yet:** the contract code (e.g. `ESZ6`) from the `definition`
schema. Join `instrument_id` to `raw_symbol` if it is needed.
