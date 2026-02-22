"""Path helpers for project directories."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return project root path based on this file location."""
    return Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    """Return root data directory path."""
    return project_root() / "data"


def raw_data_dir() -> Path:
    """Return raw data directory path."""
    return data_dir() / "raw"


def normalized_data_dir() -> Path:
    """Return normalized data directory path."""
    return data_dir() / "normalized"


def logs_dir() -> Path:
    """Return logs directory path."""
    return project_root() / "logs"


def ensure_runtime_directories() -> None:
    """Create runtime directories if they do not already exist."""
    for path in (data_dir(), raw_data_dir(), normalized_data_dir(), logs_dir()):
        path.mkdir(parents=True, exist_ok=True)
