from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.mt5_parser import parse_mt5_csv
from src.data.normalizer import load_multiple_mt5_csvs, normalize_mt5_dataframe
from src.data.schemas import (
    NORMALIZED_COLUMNS,
    ROW_ID_COLUMN,
    SYMBOL_COLUMN,
    TIME_COLUMN,
    check_h1_frequency,
    validate_ohlc_values,
)

SAMPLES = Path("examples/data_samples")


def test_parse_csv_comma_combined_datetime() -> None:
    df = parse_mt5_csv(SAMPLES / "EURUSD_H1_sample.csv")
    assert not df.empty
    assert pd.api.types.is_datetime64_any_dtype(df[TIME_COLUMN])


def test_parse_csv_semicolon_separate_date_time() -> None:
    df = parse_mt5_csv(SAMPLES / "GBPUSD_H1_sample_semicolon.csv")
    assert not df.empty
    assert pd.api.types.is_datetime64_any_dtype(df[TIME_COLUMN])


def test_symbol_inference_from_filename() -> None:
    df = parse_mt5_csv(SAMPLES / "EURUSD_H1_sample.csv")
    assert set(df[SYMBOL_COLUMN].unique()) == {"EURUSD"}


def test_normalization_outputs_target_columns() -> None:
    parsed = parse_mt5_csv(SAMPLES / "USDJPY_H1_with_symbol.csv")
    normalized = normalize_mt5_dataframe(parsed)
    assert list(normalized.columns) == NORMALIZED_COLUMNS
    assert normalized[ROW_ID_COLUMN].tolist() == list(range(len(normalized)))


def test_ohlc_validation_catches_invalid_row() -> None:
    df = parse_mt5_csv(SAMPLES / "EURUSD_H1_sample.csv")
    df.loc[0, "low"] = df.loc[0, "high"] + 1
    with pytest.raises(ValueError, match="Invalid OHLC"):
        validate_ohlc_values(df)


def test_duplicate_timestamp_handling_keep_last() -> None:
    df = parse_mt5_csv(SAMPLES / "EURUSD_H1_sample.csv")
    duplicated = pd.concat([df, df.iloc[[0]].copy()], ignore_index=True)
    duplicated.loc[len(duplicated) - 1, "close"] = 1.10400

    normalized = normalize_mt5_dataframe(duplicated, duplicate_keep="last")
    selected = normalized[(normalized[SYMBOL_COLUMN] == "EURUSD") & (normalized[TIME_COLUMN] == normalized.loc[0, TIME_COLUMN])]
    assert len(selected) == 1
    assert float(selected.iloc[0]["close"]) == 1.10400


def test_h1_gap_summary_returns_dict() -> None:
    parsed = parse_mt5_csv(SAMPLES / "GBPUSD_H1_sample_semicolon.csv")
    normalized = normalize_mt5_dataframe(parsed)
    summary = check_h1_frequency(normalized, symbol="GBPUSD")
    assert isinstance(summary, dict)
    assert summary["invalid_gaps"] >= 1


def test_multi_file_loader_concatenates_and_sorts() -> None:
    df = load_multiple_mt5_csvs(
        [SAMPLES / "GBPUSD_H1_sample_semicolon.csv", SAMPLES / "EURUSD_H1_sample.csv"]
    )
    assert not df.empty
    assert list(df.columns) == NORMALIZED_COLUMNS
    assert df.sort_values([SYMBOL_COLUMN, TIME_COLUMN]).index.tolist() == list(df.index)


def test_missing_required_columns_fails() -> None:
    bad_path = SAMPLES / "BROKEN_missing_ohlc.csv"
    bad_path.write_text("Date,Time,Open,High,Close\n2024-01-02,00:00,1,2,1.5\n", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="Missing required price column"):
            parse_mt5_csv(bad_path, symbol="BROKEN")
    finally:
        bad_path.unlink(missing_ok=True)
