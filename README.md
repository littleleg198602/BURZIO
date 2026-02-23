# Forex MVP Platform (Tasks 1-6)

MVP scaffold for a **multi-asset forex backtesting + paper-trading platform (H1)** using **MT5 CSV data**.

## Current status

✅ Task 1: project scaffold and modular architecture are in place.  
✅ Task 2: MT5 CSV parsing + normalization layer is implemented.
✅ Task 3: strategy layer and canonical signals are implemented.
✅ Task 4: single-symbol backtest engine is implemented.
✅ Task 5: multi-asset portfolio backtest layer with risk controls is implemented.
✅ Task 6: polling-based paper trading simulation runtime is implemented.

Still not implemented:
- live MT5 order placement
- full dashboard analytics wiring

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .[dev]
```

## Run

### Main placeholder bootstrap

```bash
python -m src.main
```

### Nejjednodušší spuštění (1 soubor)

```bash
python run.py
```

### Streamlit dashboard placeholder

```bash
streamlit run src/dashboard/app.py
```

### Tests

```bash
pytest
```

## Task 2: MT5 parser + normalizer

### Supported MT5 CSV variants
- Delimiters: `,`, `;`, `\t` (auto-detected, or explicit override).
- Datetime formats:
  - combined datetime column (`DateTime`, `Time`, `Timestamp` variants)
  - separate `Date` + `Time` columns
- Symbol source:
  - from CSV `Symbol` column
  - inferred from filename (e.g. `EURUSD_H1_sample.csv`)
  - explicit `symbol=` argument

### Normalized schema
Output is normalized to these columns (exact order):
- `time` (pandas datetime64)
- `symbol` (upper-case string)
- `open`
- `high`
- `low`
- `close`
- `volume` (float)
- `spread` (float, default `0.0` if missing)
- `source_file` (string)
- `row_id` (sequential int)

Sorted by `symbol, time`.

### Validation included
- required column checks
- OHLC logical checks (`low <= open/high/close <= high`)
- duplicate timestamp detection per symbol
- non-monotonic timestamp detection
- H1 gap summary (invalid gaps + missing bar estimate)

### Limitations (current)
- Weekend/session-aware gap filtering is **not** implemented yet.
- Broker-specific exotic exports may require adding extra column aliases.

### Quick usage

```python
from src.data.normalizer import normalize_from_csv, load_multiple_mt5_csvs

# Single file
norm = normalize_from_csv("examples/data_samples/EURUSD_H1_sample.csv")

# Multiple files
combined = load_multiple_mt5_csvs([
    "examples/data_samples/EURUSD_H1_sample.csv",
    "examples/data_samples/GBPUSD_H1_sample_semicolon.csv",
])
```

## Examples
- `examples/sample_mt5_format.md`
- `examples/data_samples/`

## Next planned step

➡️ **Task 3**: strategy interface + first strategy signal pipeline integration.

## Task 4: Single-symbol backtest engine

### What is supported now
- single-symbol backtest on normalized H1 OHLC data
- Task 3 signal ingestion (`time,symbol,signal,strategy`)
- LONG/SHORT execution
- stop-loss / take-profit exits
- opposite-signal close behavior (default: close only, no auto-reverse)
- deterministic trade log + equity curve + basic metrics

### Execution assumptions (no look-ahead)
- signal is observed at bar close `T`
- entry/exit decision is filled on next bar open `T+1`
- SL/TP are evaluated intrabar using bar high/low
- if both SL and TP are touched in one bar, conservative rule is used: **SL first**

### Current limitations
- single symbol only (multi-asset portfolio layer is Task 5)
- fixed quantity sizing
- SL/TP distances are absolute price distances (no pip conversion yet)

### Minimal usage snippet

```python
from src.engine import BacktestConfig, BacktestEngine
from src.strategies import MACrossoverStrategy

signals = MACrossoverStrategy(short_window=5, long_window=20).generate_signals(data)
result = BacktestEngine(BacktestConfig()).run(data, signals, strategy_name="ma_crossover")

print(result.trades.head())
print(result.equity_curve.tail())
print(result.metrics)
```

➡️ **Task 5**: multi-asset portfolio and allocation layer.

## Task 5: Multi-asset portfolio backtest layer

### What is supported now
- portfolio-level backtest across multiple symbols on shared timeline
- shared-capital simulation with multiple simultaneous positions
- one open position per symbol
- task-4-compatible execution semantics (signal at close T -> fill at next open T+1)
- portfolio outputs: trades, equity curve, metrics, rejected entry log

### Portfolio controls implemented
- `max_open_trades`
- `max_risk_per_trade_pct`
- `max_portfolio_risk_pct`
- `max_drawdown_guard_pct` (blocks new entries while active; exits still processed)

### Position sizing approach
- default risk-based sizing: `units = (equity * risk_per_trade_pct) / stop_loss_distance`
- simplified price-delta forex PnL model (same assumption family as Task 4)
- optional fixed-units fallback helper in sizing module

### Current limitations
- no base/quote currency exposure caps yet
- no correlation filters
- no live/paper integration in this layer
- simplified forex sizing (no pair-specific pip-value conversion)

➡️ **Task 6**: paper trading simulation loop.


## Task 6: Paper trading simulation loop

### What paper mode supports now
- polling a folder of MT5 CSV files for configured symbols
- incremental processing of newly confirmed H1 bars
- strategy signal generation via Task 3 (`ma_crossover` or `breakout`)
- paper-only entries/exits using Task 4/5 execution semantics
- portfolio/risk checks from Task 5 before accepting entries
- restart-safe persisted state and NDJSON event logging

### Polling workflow
1. discover symbol CSV files in `paper.input_dir`
2. detect changed files by mtime
3. normalize newly appended bars and skip newest `bar_confirmation_lag` bars
4. process only bars newer than `last_processed_by_symbol`
5. generate signals and simulate entries/exits
6. save state + update artifacts/logs

### Complete-bar rule
Default `bar_confirmation_lag: 1` means the newest bar is treated as potentially in-progress and is not processed until a newer bar appears.

### Persisted files/artifacts
- state JSON (`paper.state_path`)
- event log NDJSON (`paper.events_log_path`)
- trade log CSV (`paper.trades_path`)
- equity curve CSV (`paper.equity_path`)
- open positions JSON (`paper.positions_path`)
- latest loop status JSON (`paper.status_path`)

### Run paper mode
```bash
python -m src.paper.paper_runner
```

### Current limitations
- no live broker execution (paper simulation only)
- file polling only (no streaming/websocket runtime)
- simplified forex sizing/PnL model inherited from Task 5

➡️ **Task 7**: dashboard integration and paper monitoring UI.


## Task 7: Streamlit dashboard integration

### What dashboard supports now
- Backtest mode: configure strategy + risk/execution params, run portfolio backtest, and view metrics/equity/trades/rejections.
- Paper Monitor mode: read persisted paper artifacts (state/events/status/positions/trades/equity) and visualize current status + event stream.
- Robust handling of missing artifacts with clear empty-state messages.

### Run dashboard
```bash
streamlit run src/dashboard/app.py
```

### Paper Monitor artifact inputs
- required for full view: `state.json`, `paper_events.ndjson`, `latest_status.json`, `current_positions.json`, `paper_trades.csv`, `paper_equity.csv`
- dashboard still loads safely when some files are absent

### Current limitations
- manual refresh workflow (no websocket push)
- no live MT5 execution controls
- simplified forex sizing/PnL assumptions inherited from Tasks 5–6

➡️ **Task 8**: live bridge preparation and operator controls.
