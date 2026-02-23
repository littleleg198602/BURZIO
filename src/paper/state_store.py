"""JSON-backed state store for paper trading runtime."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PaperState:
    """Persisted runtime state for restart-safe paper simulation."""

    last_processed_by_symbol: dict[str, str] = field(default_factory=dict)
    open_positions: dict[str, dict[str, Any]] = field(default_factory=dict)
    trades: list[dict[str, Any]] = field(default_factory=list)
    rejected_entries: list[dict[str, Any]] = field(default_factory=list)
    equity_curve: list[dict[str, Any]] = field(default_factory=list)
    history_by_symbol: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    latest_close_by_symbol: dict[str, float] = field(default_factory=dict)
    cash: float = 100_000.0
    peak_equity: float = 100_000.0
    last_run_at: str = ""


class PaperStateStore:
    """Manage loading/saving state and appending paper events."""

    def __init__(self, state_path: str | Path, events_log_path: str | Path):
        self.state_path = Path(state_path)
        self.events_log_path = Path(events_log_path)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.events_log_path.parent.mkdir(parents=True, exist_ok=True)

    def load_state(self, initial_capital: float = 100_000.0) -> PaperState:
        """Load state from disk or initialize a fresh state."""
        if not self.state_path.exists():
            return PaperState(cash=initial_capital, peak_equity=initial_capital)

        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid paper state JSON: {self.state_path}") from exc

        data.setdefault("cash", initial_capital)
        data.setdefault("peak_equity", data["cash"])
        return PaperState(**data)

    def save_state(self, state: PaperState) -> None:
        """Persist state with atomic replace semantics."""
        state.last_run_at = datetime.now(UTC).isoformat()
        payload = asdict(state)
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.state_path)

    def append_event(self, event: dict[str, Any]) -> None:
        """Append one newline-delimited JSON event."""
        event = {"event_time": datetime.now(UTC).isoformat(), **event}
        with self.events_log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")
