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

## Example

Cleaned rows from 2026-10-08, 14:00 UTC (09:00 CT). `ts_recv` is omitted
for width, and `ts_event` is shown as time of day.

```text
ts_event         instrument_id  sequence  flags action side    price  size   bid_px   ask_px  bid_sz  ask_sz  locked   roll  session_start
14:00:00.001084          10252  30531835    128      A    A  7831.50     1  7831.25  7831.50      20      26   False  False           True
14:00:00.002103          10252  30531836    128      C    B  7831.25     1  7831.25  7831.50      19      26   False  False          False
...
14:00:00.032455          10252  30531963    128      A    A  7831.25     1  7831.00  7831.25      50      12   False  False          False
14:00:00.033220          10252  30531964      0      T    B  7831.25    11  7831.00  7831.25      50      12   False  False          False
14:00:00.033220          10252  30531965    128      C    A  7831.25     1  7831.00  7831.50      50      51   False  False          False
14:00:00.033444          10252  30531966    128      A    B  7831.25     3  7831.25  7831.50       3      51   False  False          False
14:00:00.033465          10252  30531967    128      A    B  7831.25     1  7831.25  7831.50       4      51   False  False          False
```

Each row is one event, followed by the top of book after it. For example,
`A B 7831.25 3` adds a 3-lot bid at 7831.25, and `bid_sz` becomes 3.

The last five rows show a buyer sweeping the offer:

- **`T` (30531964):** an 11-lot buy at 7831.25. The book columns still show
  the book *before* the trade, and `flags` is 0 (no `F_LAST`).
- **`C` (30531965):** same `ts_event`. The 7831.25 ask level is gone, and
  the best ask moves up to 7831.50. This is the trade's effect on the book.
- **`A` (30531966 on):** new bids step up to 7831.25.

`book_states(df)` drops the `T` row and keeps the others. In this minute,
the 21,212 cleaned rows split into 20,237 book states and 975 trades.

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
