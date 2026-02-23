"""Event schema placeholders for engine internals."""

from dataclasses import dataclass


@dataclass(slots=True)
class Event:
    """Base event object for future event-driven flow."""

    event_type: str
