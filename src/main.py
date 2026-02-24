"""Application entry point for Task 1 scaffold."""

from __future__ import annotations

import os
from pathlib import Path

from src.config.loader import load_app_config
from src.data.mt5_live import export_from_app_config
from src.utils.logging_setup import setup_logging
from src.utils.paths import ensure_runtime_directories


def main() -> None:
    """Bootstrap application configuration and runtime environment."""
    config_path = os.getenv("CONFIG_PATH", "configs/app_config.example.yaml")
    config = load_app_config(config_path)

    app_cfg = config.get("app", {}) if isinstance(config, dict) else {}
    log_level = str(app_cfg.get("log_level", os.getenv("LOG_LEVEL", "INFO")))

    logger = setup_logging(level=log_level, log_file=Path("logs") / "app.log")
    ensure_runtime_directories()

    logger.info("Starting Forex MVP Platform scaffold.")
    logger.info("Loaded config from: %s", config_path)
    try:
        exported = export_from_app_config(config)
        if exported:
            logger.info("MT5 startup export wrote %s file(s) into data directory.", len(exported))
    except Exception as exc:
        logger.warning("MT5 startup export skipped: %s", exc)

    logger.info("Task 1 scaffold is ready.")


if __name__ == "__main__":
    main()
