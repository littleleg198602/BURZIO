from __future__ import annotations

import json

from src.paper.state_store import PaperState, PaperStateStore


def test_state_store_initializes_when_missing(tmp_path) -> None:
    store = PaperStateStore(tmp_path / "state.json", tmp_path / "events.ndjson")
    state = store.load_state(initial_capital=12_345)
    assert state.cash == 12_345
    assert state.peak_equity == 12_345
    assert state.last_processed_by_symbol == {}


def test_state_store_save_and_reload_roundtrip(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    events_path = tmp_path / "events.ndjson"
    store = PaperStateStore(state_path, events_path)

    state = PaperState(cash=1000.0, peak_equity=1100.0)
    state.last_processed_by_symbol["EURUSD"] = "2024-01-01T00:00:00"
    state.open_positions["EURUSD"] = {"side": "LONG", "entry_price": 1.1}
    store.save_state(state)

    reloaded = store.load_state(initial_capital=1.0)
    assert reloaded.cash == 1000.0
    assert reloaded.peak_equity == 1100.0
    assert reloaded.open_positions["EURUSD"]["side"] == "LONG"

    state.cash = 2000.0
    store.save_state(state)
    reloaded2 = store.load_state(initial_capital=1.0)
    assert reloaded2.cash == 2000.0


def test_append_event_writes_ndjson(tmp_path) -> None:
    store = PaperStateStore(tmp_path / "state.json", tmp_path / "events.ndjson")
    store.append_event({"event_type": "LOOP_STATUS", "message": "ok"})
    lines = (tmp_path / "events.ndjson").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["event_type"] == "LOOP_STATUS"
    assert "event_time" in event
