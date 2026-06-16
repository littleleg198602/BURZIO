"""Export cached analysis data to Excel with openpyxl."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from .database import Database


def export_excel(db: Database, tickers: tuple[str, ...], output_path: str) -> None:
    """Create one worksheet per ticker plus a PHRASE_STATS worksheet."""
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    for ticker in tickers:
        sheet = wb.create_sheet(title=ticker[:31])
        _write_rows(sheet, _ticker_rows(db, ticker))
    phrase_sheet = wb.create_sheet(title="PHRASE_STATS")
    _write_rows(phrase_sheet, _phrase_rows(db))
    wb.save(output_path)


def _ticker_rows(db: Database, ticker: str) -> list[list[object]]:
    news_by_guid = {row["guid"]: row for row in db.fetch_news(ticker)}
    grouped: dict[str, dict[int, float | None]] = {}
    for row in db.fetch_reactions(ticker):
        grouped.setdefault(row["guid"], {})[row["window_days"]] = row["return_pct"]
    rows: list[list[object]] = [["ticker", "published", "title", "summary", "link", "return_1d", "return_3d", "return_5d", "return_10d"]]
    for guid, news in news_by_guid.items():
        reactions = grouped.get(guid, {})
        rows.append([
            ticker,
            news["published"],
            news["title"],
            news["summary"],
            news["link"],
            reactions.get(1),
            reactions.get(3),
            reactions.get(5),
            reactions.get(10),
        ])
    return rows


def _phrase_rows(db: Database) -> list[list[object]]:
    rows: list[list[object]] = [["ticker", "window_days", "phrase", "occurrences", "average_return", "win_rate_up", "average_down_move", "confidence_score"]]
    rows.extend([
        [row["ticker"], row["window_days"], row["phrase"], row["occurrences"], row["average_return"], row["win_rate_up"], row["average_down_move"], row["confidence_score"]]
        for row in db.fetch_phrase_stats()
    ])
    return rows


def _write_rows(sheet, rows: list[list[object]]) -> None:
    for row in rows:
        sheet.append(row)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for column_cells in sheet.columns:
        width = min(60, max(len(str(cell.value or "")) for cell in column_cells) + 2)
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = width
