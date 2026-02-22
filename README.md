# Forex MVP Platform (Tasks 1-2)

MVP scaffold for a **multi-asset forex backtesting + paper-trading platform (H1)** using **MT5 CSV data**.

## Current status

✅ Task 1: project scaffold and modular architecture are in place.  
✅ Task 2: MT5 CSV parsing + normalization layer is implemented.

Not implemented yet:
- backtesting engine logic
- strategy execution loop
- paper trading runtime
- dashboard analytics wiring

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
