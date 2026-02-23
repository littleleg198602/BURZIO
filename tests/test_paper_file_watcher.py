from __future__ import annotations

import time

from src.paper.file_watcher import discover_symbol_files, load_new_bars_for_symbol, poll_file_changes


def _write_mt5_csv(path, rows: list[dict[str, object]]) -> None:
    header = "DateTime,Open,High,Low,Close,TickVolume,Spread\n"
    lines = [header]
    for row in rows:
        lines.append(
            f"{row['DateTime']},{row['Open']},{row['High']},{row['Low']},{row['Close']},{row.get('TickVolume', 100)},{row.get('Spread', 0)}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")


def test_discover_symbol_files_and_poll_changes(tmp_path) -> None:
    eur = tmp_path / "EURUSD_H1.csv"
    gbp = tmp_path / "GBPUSD_H1.csv"
    _write_mt5_csv(eur, [{"DateTime": "2024-01-01 00:00:00", "Open": 1.1, "High": 1.11, "Low": 1.09, "Close": 1.105}])
    _write_mt5_csv(gbp, [{"DateTime": "2024-01-01 00:00:00", "Open": 1.2, "High": 1.21, "Low": 1.19, "Close": 1.205}])

    files = discover_symbol_files(tmp_path, ["EURUSD", "GBPUSD"])
    assert set(files) == {"EURUSD", "GBPUSD"}

    changed, mtimes = poll_file_changes(files)
    assert len(changed) == 2

    changed2, _ = poll_file_changes(files, mtimes)
    assert changed2 == []

    time.sleep(0.02)
    _write_mt5_csv(eur, [
        {"DateTime": "2024-01-01 00:00:00", "Open": 1.1, "High": 1.11, "Low": 1.09, "Close": 1.105},
        {"DateTime": "2024-01-01 01:00:00", "Open": 1.105, "High": 1.115, "Low": 1.1, "Close": 1.11},
    ])
    changed3, _ = poll_file_changes(files, mtimes)
    assert len(changed3) == 1
    assert changed3[0].symbol == "EURUSD"


def test_load_new_bars_respects_confirmation_lag_and_last_processed(tmp_path) -> None:
    eur = tmp_path / "EURUSD_H1.csv"
    _write_mt5_csv(
        eur,
        [
            {"DateTime": "2024-01-01 00:00:00", "Open": 1.1, "High": 1.11, "Low": 1.09, "Close": 1.105},
            {"DateTime": "2024-01-01 01:00:00", "Open": 1.105, "High": 1.115, "Low": 1.1, "Close": 1.11},
            {"DateTime": "2024-01-01 02:00:00", "Open": 1.11, "High": 1.12, "Low": 1.105, "Close": 1.115},
        ],
    )

    new_bars = load_new_bars_for_symbol(eur, "EURUSD", last_processed_time=None, confirmation_lag=1)
    assert len(new_bars) == 2
    assert str(new_bars.iloc[-1]["time"]) == "2024-01-01 01:00:00"

    newer = load_new_bars_for_symbol(eur, "EURUSD", last_processed_time="2024-01-01T00:00:00", confirmation_lag=1)
    assert len(newer) == 1
    assert str(newer.iloc[0]["time"]) == "2024-01-01 01:00:00"
