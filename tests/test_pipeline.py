from pathlib import Path

from src.database import Database
from src.excel_exporter import export_excel
from src.phrase_stats import calculate_phrase_stats
from src.reaction_analyzer import analyze_reactions


def test_reactions_phrase_stats_and_excel_export(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.sqlite")
    db.upsert_prices(
        [
            ("TEST", "2026-01-02", 100, 101, 99, 100, 100, 1000),
            ("TEST", "2026-01-05", 101, 103, 100, 102, 102, 1000),
            ("TEST", "2026-01-06", 102, 104, 101, 104, 104, 1000),
            ("TEST", "2026-01-07", 104, 105, 100, 101, 101, 1000),
            ("TEST", "2026-01-08", 101, 106, 101, 105, 105, 1000),
            ("TEST", "2026-01-09", 105, 107, 104, 106, 106, 1000),
            ("TEST", "2026-01-12", 106, 108, 105, 107, 107, 1000),
            ("TEST", "2026-01-13", 107, 109, 106, 108, 108, 1000),
            ("TEST", "2026-01-14", 108, 110, 107, 109, 109, 1000),
            ("TEST", "2026-01-15", 109, 111, 108, 110, 110, 1000),
            ("TEST", "2026-01-16", 110, 112, 109, 111, 111, 1000),
            ("TEST", "2026-01-20", 111, 113, 110, 112, 112, 1000),
        ]
    )
    inserted = db.upsert_news(
        [
            ("TEST", "1", "2026-01-03T12:00:00+00:00", "AI growth accelerates", "AI chip growth surprises investors", "https://example.com/1"),
            ("TEST", "1", "2026-01-03T12:00:00+00:00", "AI growth accelerates", "AI chip growth surprises investors", "https://example.com/1"),
            ("TEST", "2", "2026-01-05T12:00:00+00:00", "AI growth continues", "AI chip demand accelerates", "https://example.com/2"),
        ]
    )

    assert inserted == 2
    assert analyze_reactions(db, "TEST", (1, 3, 5, 10)) == 8
    assert calculate_phrase_stats(db, ("TEST",), min_occurrences=1) > 0
    assert {row["window_days"] for row in db.fetch_phrase_stats()} == {1, 3, 5, 10}

    output = tmp_path / "analysis.xlsx"
    export_excel(db, ("TEST",), str(output))
    assert output.exists()
