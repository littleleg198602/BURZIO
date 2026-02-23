"""Basic sanity checks for Task 1 scaffold."""

from __future__ import annotations

from src.config.loader import load_app_config


def test_import_main_module() -> None:
    """Main module should be importable."""
    import src.main  # noqa: F401


def test_load_example_config() -> None:
    """Example YAML config should load as dictionary."""
    config = load_app_config("configs/app_config.example.yaml")
    assert isinstance(config, dict)
    assert "app" in config
    assert "data" in config
