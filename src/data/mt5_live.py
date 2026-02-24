"""Optional live MT5 pull helpers (Market Watch -> CSV snapshots)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(slots=True)
class MT5LiveConfig:
    """Configuration for optional MT5 snapshot export at startup."""

    enabled: bool = False
    output_dir: str = "data/raw"
    timeframe: str = "H1"
    bars: int = 500
    symbols: list[str] = field(default_factory=list)


def _import_mt5() -> Any:
    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception as exc:  # pragma: no cover - platform-specific import path
        raise RuntimeError(
            "MetaTrader5 Python package is not available. Install with: pip install MetaTrader5"
        ) from exc
    return mt5


def _timeframe_value(mt5: Any, timeframe: str) -> int:
    key = f"TIMEFRAME_{timeframe.upper()}"
    value = getattr(mt5, key, None)
    if value is None:
        raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")
    return int(value)


def export_market_watch_to_csv(config: MT5LiveConfig) -> list[str]:
    """Export Market Watch bars from opened MT5 terminal to CSV files.

    Returns list of file paths that were written.
    """
    if not config.enabled:
        return []

    mt5 = _import_mt5()
    written: list[str] = []
    root = Path(config.output_dir)
    root.mkdir(parents=True, exist_ok=True)

    tf = _timeframe_value(mt5, config.timeframe)

    if not mt5.initialize():
        raise RuntimeError(f"Failed to initialize MT5: {mt5.last_error()}")

    try:
        symbols = [s.upper() for s in config.symbols] if config.symbols else [
            str(s.name).upper() for s in (mt5.symbols_get() or []) if getattr(s, "visible", True)
        ]

        for symbol in symbols:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, int(config.bars))
            if rates is None or len(rates) == 0:
                continue

            df = pd.DataFrame(rates)
            if "time" not in df.columns:
                continue
            df["DateTime"] = pd.to_datetime(df["time"], unit="s", errors="coerce")

            out = pd.DataFrame(
                {
                    "DateTime": df["DateTime"],
                    "Open": df.get("open"),
                    "High": df.get("high"),
                    "Low": df.get("low"),
                    "Close": df.get("close"),
                    "TickVolume": df.get("tick_volume", 0),
                    "Spread": df.get("spread", 0),
                    "Symbol": symbol,
                }
            )
            path = root / f"{symbol}_{config.timeframe.upper()}.csv"
            out.to_csv(path, index=False)
            written.append(str(path))
    finally:
        mt5.shutdown()

    return written


def export_from_app_config(config: dict[str, Any]) -> list[str]:
    """Read mt5_live section and export snapshots when enabled."""
    section = config.get("mt5_live", {}) if isinstance(config, dict) else {}
    live_cfg = MT5LiveConfig(
        enabled=bool(section.get("enabled", False)),
        output_dir=str(section.get("output_dir", "data/raw")),
        timeframe=str(section.get("timeframe", "H1")),
        bars=int(section.get("bars", 500)),
        symbols=[str(s).upper() for s in section.get("symbols", [])],
    )
    return export_market_watch_to_csv(live_cfg)
