"""Streamlit dashboard placeholder for Task 1 scaffold."""

from __future__ import annotations

import streamlit as st


def render_dashboard() -> None:
    """Render placeholder UI sections for the MVP dashboard."""
    st.set_page_config(page_title="Forex MVP Dashboard", layout="wide")

    st.title("Forex MVP Platform")
    st.success("MVP scaffold ready")

    st.header("Backtest controls")
    st.info("Placeholder: parameter controls and backtest trigger will be added later.")

    st.header("Paper trading status")
    st.info("Placeholder: live paper runner status and latest signals.")

    st.header("Equity curve")
    st.info("Placeholder: equity chart will appear here.")

    st.header("Metrics")
    st.info("Placeholder: drawdown, Sharpe, win-rate, and other KPIs.")


if __name__ == "__main__":
    render_dashboard()
