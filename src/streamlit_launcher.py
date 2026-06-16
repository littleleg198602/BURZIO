"""Command-line launcher for the Streamlit app."""
from __future__ import annotations

from streamlit.web import cli as stcli


def main() -> int:
    """Start Streamlit with the project UI."""
    return stcli.main(["streamlit", "run", "src/streamlit_app.py"])


if __name__ == "__main__":
    raise SystemExit(main())
