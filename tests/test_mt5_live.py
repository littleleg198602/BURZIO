from __future__ import annotations


import pandas as pd
import pytest

from src.data.mt5_live import MT5LiveConfig, export_from_app_config, export_market_watch_to_csv


class _Sym:
    def __init__(self, name: str, visible: bool = True):
        self.name = name
        self.visible = visible


class _FakeMT5:
    TIMEFRAME_H1 = 1

    def __init__(self):
        self.initialized = False

    def initialize(self):
        self.initialized = True
        return True

    def shutdown(self):
        self.initialized = False

    def last_error(self):
        return (0, "OK")

    def symbols_get(self):
        return [_Sym("EURUSD"), _Sym("GBPUSD", visible=False), _Sym("USDJPY")]

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, bars):
        if symbol == "USDJPY":
            return []
        return [
            {"time": 1704067200, "open": 1.1, "high": 1.2, "low": 1.0, "close": 1.15, "tick_volume": 10, "spread": 0},
            {"time": 1704070800, "open": 1.15, "high": 1.25, "low": 1.1, "close": 1.2, "tick_volume": 12, "spread": 0},
        ]


def test_export_disabled_returns_empty() -> None:
    out = export_market_watch_to_csv(MT5LiveConfig(enabled=False))
    assert out == []


def test_export_from_config_disabled() -> None:
    out = export_from_app_config({"mt5_live": {"enabled": False}})
    assert out == []


def test_export_market_watch_to_csv_with_fake_mt5(monkeypatch, tmp_path) -> None:
    fake = _FakeMT5()

    import src.data.mt5_live as live

    monkeypatch.setattr(live, "_import_mt5", lambda: fake)

    paths = export_market_watch_to_csv(
        MT5LiveConfig(enabled=True, output_dir=str(tmp_path), timeframe="H1", bars=100)
    )

    assert len(paths) == 1
    df = pd.read_csv(paths[0])
    assert list(df.columns) == ["DateTime", "Open", "High", "Low", "Close", "TickVolume", "Spread", "Symbol"]
    assert df["Symbol"].iloc[0] == "EURUSD"


def test_export_market_watch_to_csv_missing_mt5(monkeypatch) -> None:
    import src.data.mt5_live as live

    def _boom():
        raise RuntimeError("MetaTrader5 Python package is not available. Install with: pip install MetaTrader5")

    monkeypatch.setattr(live, "_import_mt5", _boom)

    with pytest.raises(RuntimeError):
        export_market_watch_to_csv(MT5LiveConfig(enabled=True))
