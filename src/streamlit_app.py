"""Streamlit web UI for the Yahoo Finance news-impact pipeline."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config import AppConfig, DEFAULT_DB_PATH, DEFAULT_EXCEL_PATH, DEFAULT_TICKERS
from src.database import Database
from src.main import run


def main() -> None:
    """Render and run the interactive Streamlit app."""
    st.set_page_config(page_title="Yahoo News Impact", page_icon="📈", layout="wide")
    st.title("📈 Yahoo News Impact Analyzer")
    st.caption("Analýza Yahoo Finance zpráv, cenových reakcí a frází. Neobchoduje.")

    with st.sidebar:
        st.header("Nastavení")
        tickers_text = st.text_input("Tickery", value=", ".join(DEFAULT_TICKERS))
        db_path = Path(st.text_input("SQLite databáze", value=str(DEFAULT_DB_PATH)))
        excel_path = Path(st.text_input("Excel výstup", value=str(DEFAULT_EXCEL_PATH)))
        min_occurrences = st.number_input("Min. počet výskytů fráze", min_value=1, max_value=100, value=1, step=1)
        run_button = st.button("Spustit analýzu", type="primary")

    tickers = tuple(_parse_tickers(tickers_text))
    if not tickers:
        st.warning("Zadej alespoň jeden ticker.")
        return

    if run_button:
        with st.spinner("Stahuji data z Yahoo, ukládám do SQLite a počítám statistiky..."):
            config = AppConfig(tickers=tickers, db_path=db_path, excel_path=excel_path)
            run(config, min_occurrences=int(min_occurrences))
        st.success(f"Hotovo. Excel uložen: {excel_path}")

    if db_path.exists():
        _render_database_preview(Database(db_path), tickers, excel_path)
    else:
        st.info("Databáze zatím neexistuje. Klikni na 'Spustit analýzu'.")


def _parse_tickers(value: str) -> list[str]:
    return [ticker.strip().upper() for ticker in value.replace(";", ",").split(",") if ticker.strip()]


def _render_database_preview(db: Database, tickers: tuple[str, ...], excel_path: Path) -> None:
    st.subheader("Výsledky")
    if excel_path.exists():
        st.download_button(
            "Stáhnout Excel",
            data=excel_path.read_bytes(),
            file_name=excel_path.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    phrase_stats = pd.DataFrame([dict(row) for row in db.fetch_phrase_stats()])
    st.markdown("### PHRASE_STATS")
    if phrase_stats.empty:
        st.info("Zatím nejsou dostupné statistiky frází. Spusť analýzu nebo sniž minimum výskytů.")
    else:
        st.dataframe(phrase_stats, use_container_width=True, hide_index=True)

    selected = st.selectbox("Ticker detail", tickers)
    news = pd.DataFrame([dict(row) for row in db.fetch_news(selected)])
    reactions = pd.DataFrame([dict(row) for row in db.fetch_reactions(selected)])
    prices = pd.DataFrame([dict(row) for row in db.fetch_prices(selected)])

    col1, col2, col3 = st.columns(3)
    col1.metric("Zprávy", len(news))
    col2.metric("Cenové řádky", len(prices))
    col3.metric("Reakce", len(reactions))

    st.markdown(f"### Zprávy a reakce: {selected}")
    if news.empty:
        st.info("Pro vybraný ticker zatím nejsou uložené zprávy.")
        return

    if not reactions.empty:
        pivot = reactions.pivot_table(index="guid", columns="window_days", values="return_pct", aggfunc="first").reset_index()
        pivot = pivot.rename(columns={1: "return_1d", 3: "return_3d", 5: "return_5d", 10: "return_10d"})
        news = news.merge(pivot, on="guid", how="left")
    st.dataframe(news, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
