"""Streamlit dashboard for backtest visualization and paper monitoring."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.dashboard.backtest_service import BacktestRunInput, run_backtest
from src.dashboard.loaders import discover_symbol_csvs, load_paper_artifacts


def _render_backtest_mode() -> None:
    st.header("Backtest")
    data_dir = st.sidebar.text_input("Data directory", value="data/raw")

    available = discover_symbol_csvs(data_dir)
    default_symbols = list(available.keys())[:2]

    strategy_name = st.selectbox("Strategy", options=["ma_crossover", "breakout"], index=0)
    c1, c2 = st.columns(2)
    with c1:
        symbols = st.multiselect("Symbols", options=list(available.keys()), default=default_symbols)
        initial_capital = st.number_input("Initial capital", min_value=1.0, value=100_000.0, step=1_000.0)
        stop_loss_distance = st.number_input("Stop-loss distance (price)", min_value=0.00001, value=0.0020, format="%.5f")
        take_profit_distance = st.number_input("Take-profit distance (price)", min_value=0.00001, value=0.0040, format="%.5f")
        use_data_spread = st.checkbox("Use spread column from data", value=True)
        fixed_spread = st.number_input("Fixed spread", min_value=0.0, value=0.0, format="%.5f")
        slippage = st.number_input("Slippage", min_value=0.0, value=0.0, format="%.5f")

    with c2:
        risk_per_trade_pct = st.number_input("Risk per trade %", min_value=0.0001, value=0.01, step=0.001, format="%.4f")
        max_open_trades = int(st.number_input("Max open trades", min_value=1, value=3, step=1))
        max_risk_per_trade_pct = st.number_input("Max risk/trade %", min_value=0.0001, value=0.02, step=0.001, format="%.4f")
        max_portfolio_risk_pct = st.number_input("Max portfolio risk %", min_value=0.0001, value=0.05, step=0.001, format="%.4f")
        max_drawdown_guard_pct = st.number_input("Max drawdown guard %", min_value=0.0001, value=0.20, step=0.01, format="%.4f")

        if strategy_name == "ma_crossover":
            short_window = int(st.number_input("MA short window", min_value=1, value=5, step=1))
            long_window = int(st.number_input("MA long window", min_value=2, value=20, step=1))
            strategy_params = {"short_window": short_window, "long_window": long_window}
        else:
            lookback = int(st.number_input("Breakout lookback", min_value=2, value=20, step=1))
            strategy_params = {"lookback": lookback}

    if st.button("Run Backtest", type="primary"):
        with st.spinner("Running backtest..."):
            try:
                payload = run_backtest(
                    BacktestRunInput(
                        data_dir=data_dir,
                        symbols=symbols,
                        strategy_name=strategy_name,
                        strategy_params=strategy_params,
                        initial_capital=initial_capital,
                        stop_loss_distance=stop_loss_distance,
                        take_profit_distance=take_profit_distance,
                        risk_per_trade_pct=risk_per_trade_pct,
                        max_open_trades=max_open_trades,
                        max_portfolio_risk_pct=max_portfolio_risk_pct,
                        max_drawdown_guard_pct=max_drawdown_guard_pct,
                        max_risk_per_trade_pct=max_risk_per_trade_pct,
                        use_data_spread=use_data_spread,
                        fixed_spread=fixed_spread,
                        slippage=slippage,
                    )
                )
                st.session_state["backtest_payload"] = payload
                st.success("Backtest completed.")
            except Exception as exc:
                st.error(f"Backtest failed: {exc}")

    payload = st.session_state.get("backtest_payload")
    if not payload:
        st.info("Run a backtest to see metrics, charts, and trades.")
        return

    result = payload["result"]
    metrics: dict[str, float] = result.metrics

    mcols = st.columns(6)
    mcols[0].metric("Total Return", f"{metrics.get('total_return', 0.0):.2%}")
    mcols[1].metric("Max Drawdown", f"{metrics.get('max_drawdown', 0.0):.2%}")
    mcols[2].metric("Trades", f"{int(metrics.get('number_of_trades', 0.0))}")
    mcols[3].metric("Win Rate", f"{metrics.get('win_rate', 0.0):.2%}")
    pf = metrics.get("profit_factor", 0.0)
    mcols[4].metric("Profit Factor", "inf" if pf == float("inf") else f"{pf:.2f}")
    mcols[5].metric("Rejected Entries", f"{int(metrics.get('rejected_entries_count', 0.0))}")

    st.subheader("Equity Curve")
    eq = result.equity_curve.copy()
    if not eq.empty:
        eq["time"] = pd.to_datetime(eq["time"], errors="coerce")
        st.line_chart(eq.set_index("time")["equity"])
    else:
        st.info("No equity points available.")

    st.subheader("Trades")
    trades = result.trades.copy()
    if not trades.empty:
        sym_filter = st.selectbox("Trade symbol filter", options=["ALL"] + sorted(trades["symbol"].astype(str).unique().tolist()))
        if sym_filter != "ALL":
            trades = trades[trades["symbol"].astype(str) == sym_filter]
        st.dataframe(trades, use_container_width=True)
    else:
        st.info("No closed trades yet.")

    st.subheader("Rejected Entries")
    rejected = result.rejected_signals.copy()
    if not rejected.empty:
        st.dataframe(rejected, use_container_width=True)
        counts = rejected.groupby("reason").size().reset_index(name="count")
        st.bar_chart(counts.set_index("reason"))
    else:
        st.info("No rejected entries.")


def _render_paper_monitor_mode() -> None:
    st.header("Paper Monitor")

    state_path = st.sidebar.text_input("Paper state path", value="data/paper/state.json")
    events_path = st.sidebar.text_input("Paper events path", value="logs/paper_events.ndjson")
    status_path = st.sidebar.text_input("Paper status path", value="logs/latest_status.json")
    positions_path = st.sidebar.text_input("Paper positions path", value="logs/current_positions.json")
    trades_path = st.sidebar.text_input("Paper trades path", value="logs/paper_trades.csv")
    equity_path = st.sidebar.text_input("Paper equity path", value="logs/paper_equity.csv")
    tail_n = int(st.sidebar.number_input("Recent events", min_value=10, value=200, step=10))

    if st.button("Refresh Paper Monitor"):
        st.session_state.pop("paper_payload", None)

    payload = st.session_state.get("paper_payload")
    if payload is None:
        payload = load_paper_artifacts(
            state_path=state_path,
            events_path=events_path,
            status_path=status_path,
            positions_path=positions_path,
            trades_path=trades_path,
            equity_path=equity_path,
            events_limit=tail_n,
        )
        st.session_state["paper_payload"] = payload

    state = payload["state"]
    status = payload["status"]
    positions = payload["positions"]
    trades = payload["trades"]
    equity = payload["equity"]
    events = payload["events"]

    st.subheader("Runner Status")
    if status is None and state is None:
        st.warning("No paper state/status found yet.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Cash", f"{(status or {}).get('cash', (state or {}).get('cash', 0.0)):.2f}")
        c2.metric("Peak Equity", f"{(status or {}).get('peak_equity', (state or {}).get('peak_equity', 0.0)):.2f}")
        c3.metric("Open Positions", str((status or {}).get("open_positions", len((positions or {})))))
        c4.metric("Trades", str((status or {}).get("trades", len((state or {}).get("trades", [])))))
        if state is not None:
            st.caption(f"Last run: {state.get('last_run_at', 'n/a')}")
            lps = state.get("last_processed_by_symbol", {})
            if lps:
                st.json(lps)

    st.subheader("Open Positions")
    if positions:
        pos_df = pd.DataFrame.from_dict(positions, orient="index").reset_index(drop=True)
        st.dataframe(pos_df, use_container_width=True)
    else:
        st.info("No open positions file/data available.")

    st.subheader("Paper Equity")
    if not equity.empty and "time" in equity.columns and "equity" in equity.columns:
        eq = equity.copy()
        eq["time"] = pd.to_datetime(eq["time"], errors="coerce")
        st.line_chart(eq.set_index("time")["equity"])
    else:
        st.info("No paper equity data found.")

    st.subheader("Recent Paper Trades")
    if not trades.empty:
        st.dataframe(trades.tail(200), use_container_width=True)
    else:
        st.info("No paper trades logged yet.")

    st.subheader("Event Log")
    if not events.empty:
        if "event_type" in events.columns:
            event_types = sorted(events["event_type"].dropna().astype(str).unique().tolist())
            selected = st.multiselect("Event type filter", options=event_types, default=event_types)
            filtered = events[events["event_type"].astype(str).isin(selected)] if selected else events
        else:
            filtered = events
        st.dataframe(filtered.tail(tail_n), use_container_width=True)

        if "event_type" in events.columns:
            rejected = events[events["event_type"] == "ENTRY_REJECTED"]
            if not rejected.empty and "reason" in rejected.columns:
                st.subheader("Rejected Entries by Reason")
                rej_counts = rejected.groupby("reason").size().reset_index(name="count")
                st.bar_chart(rej_counts.set_index("reason"))
    else:
        st.info("No event log found yet.")


def render_dashboard() -> None:
    """Render dashboard app."""
    st.set_page_config(page_title="Forex MVP Dashboard", layout="wide")
    st.title("Forex MVP Platform Dashboard")

    mode = st.sidebar.selectbox("Mode", options=["Backtest", "Paper Monitor"], index=0)

    if mode == "Backtest":
        _render_backtest_mode()
    else:
        _render_paper_monitor_mode()


if __name__ == "__main__":
    render_dashboard()
