# Forex MVP Platform (Task 1 Scaffold)

MVP scaffold for a **multi-asset forex backtesting + paper-trading platform (H1)** using **MT5 CSV data**.

## Current status

✅ **Task 1 only**: project scaffold and foundational structure are implemented.

Not implemented yet:
- real backtest engine logic
- MT5 normalization pipeline
- portfolio/risk algorithms
- live paper execution logic
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

## Project structure overview

```text
project_root/
  README.md
  pyproject.toml
  .gitignore
  .env.example
  configs/
    app_config.example.yaml
  data/
    raw/
    normalized/
  examples/
    sample_mt5_format.md
  logs/
  src/
    __init__.py
    main.py
    config/
      __init__.py
      loader.py
    data/
      __init__.py
      mt5_parser.py
      normalizer.py
      schemas.py
    engine/
      __init__.py
      backtest_engine.py
      execution_model.py
      events.py
    strategies/
      __init__.py
      base_strategy.py
      ma_crossover.py
      breakout.py
      signals.py
    portfolio/
      __init__.py
      portfolio_manager.py
      position_sizer.py
      risk_manager.py
    paper/
      __init__.py
      paper_runner.py
      state_store.py
      file_watcher.py
    reporting/
      __init__.py
      metrics.py
      equity.py
      exports.py
    dashboard/
      __init__.py
      app.py
    utils/
      __init__.py
      logging_setup.py
      time_utils.py
      paths.py
  tests/
    __init__.py
    test_sanity.py
```

## Next planned step

➡️ **Task 2**: implement MT5 CSV parser + normalization mapping and validations.
