"""YAML configuration loader for the application."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigError(RuntimeError):
    """Raised when application configuration cannot be loaded."""


def load_app_config(path: str) -> dict[str, Any]:
    """Load YAML application config from ``path``.

    Args:
        path: Path to YAML config file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        ConfigError: If file is missing, invalid YAML, or root is not a mapping.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in configuration file: {config_path}") from exc
    except OSError as exc:
        raise ConfigError(f"Unable to read configuration file: {config_path}") from exc

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ConfigError(
            f"Invalid configuration format in {config_path}: root must be a mapping"
        )

    return data
