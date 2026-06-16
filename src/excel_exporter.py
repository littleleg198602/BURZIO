"""Export cached analysis data to Excel with openpyxl."""
from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .database import Database

PERCENT_COLUMNS_BY_HEADER = {
    "Reakce +1 den",
    "Reakce +3 dny",
    "Reakce +5 dní",
    "Reakce +10 dní",
    "Průměrný výnos",
    "Úspěšnost růstu",
    "Průměrný pokles",
}


def export_excel(db: Database, tickers: tuple[str, ...], output_path: str) -> None:
    """Create a human-friendly workbook with instructions, ticker sheets, and phrase stats."""
    wb = Workbook()
    default = wb.active
    default.title = "NAVOD"
    _write_help_sheet(default)

    for ticker in tickers:
        sheet = wb.create_sheet(title=ticker[:31])
        _write_rows(sheet, _ticker_rows(db, ticker))
    phrase_sheet = wb.create_sheet(title="PHRASE_STATS")
    _write_rows(phrase_sheet, _phrase_rows(db))
    wb.save(output_path)


def _write_help_sheet(sheet) -> None:
    sheet.append(["Yahoo News Impact Analyzer - jak číst výstup"])
    sheet.append([])
    sheet.append(["Listy s tickery", "Každý list NVDA/AAPL/MSFT/AMD/TSLA ukazuje zprávy a následnou procentní reakci ceny."])
    sheet.append(["Reakce +1/+3/+5/+10", "Změna ceny od prvního obchodního dne po zprávě do daného obchodního okna. 0,025 znamená +2,5 %."])
    sheet.append(["Prázdná reakce", "Pro danou zprávu ještě není dost budoucích obchodních dní v cenových datech."])
    sheet.append(["PHRASE_STATS", "Souhrn frází z titulků/souhrnů. Vyšší skóre jistoty znamená častější a konzistentnější historický pohyb."])
    sheet.append(["Důležité", "Výsledek je historická analýza, ne obchodní doporučení a ne důkaz příčiny."])
    sheet["A1"].font = Font(bold=True, size=14)
    for row in sheet.iter_rows(min_row=3, max_col=2):
        row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    sheet.column_dimensions["A"].width = 24
    sheet.column_dimensions["B"].width = 110


def _ticker_rows(db: Database, ticker: str) -> list[list[object]]:
    news_by_guid = {row["guid"]: row for row in db.fetch_news(ticker)}
    grouped: dict[str, dict[int, float | None]] = {}
    for row in db.fetch_reactions(ticker):
        grouped.setdefault(row["guid"], {})[row["window_days"]] = row["return_pct"]
    rows: list[list[object]] = [["Ticker", "Datum zprávy", "Titulek", "Shrnutí", "Odkaz", "Reakce +1 den", "Reakce +3 dny", "Reakce +5 dní", "Reakce +10 dní"]]
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
    rows: list[list[object]] = [["Ticker", "Okno dní", "Fráze", "Počet výskytů", "Průměrný výnos", "Úspěšnost růstu", "Průměrný pokles", "Skóre jistoty"]]
    rows.extend([
        [row["ticker"], row["window_days"], row["phrase"], row["occurrences"], row["average_return"], row["win_rate_up"], row["average_down_move"], row["confidence_score"]]
        for row in db.fetch_phrase_stats()
    ])
    return rows


def _write_rows(sheet, rows: list[list[object]]) -> None:
    for row in rows:
        sheet.append(row)
    _format_table(sheet)


def _format_table(sheet) -> None:
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    headers = [cell.value for cell in sheet[1]]
    percent_column_indexes = {index + 1 for index, header in enumerate(headers) if header in PERCENT_COLUMNS_BY_HEADER}
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            if cell.column in percent_column_indexes and isinstance(cell.value, (int, float)):
                cell.number_format = "0.00%"

    for column_cells in sheet.columns:
        header = str(column_cells[0].value or "")
        if header in {"Titulek", "Shrnutí", "Odkaz", "Fráze"}:
            width = {"Titulek": 58, "Shrnutí": 80, "Odkaz": 36, "Fráze": 42}[header]
        else:
            width = min(22, max(len(str(cell.value or "")) for cell in column_cells) + 2)
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = width
