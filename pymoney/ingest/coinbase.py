"""Coinbase (Google Sheets tab) → investment_transactions ingest (stub)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def ingest_coinbase(db_path: str | None = None) -> int:
    """Ingest Coinbase BTC trades from Google Sheets tab.

    Not yet implemented. Configure tab name via COINBASE_TAB_NAME env var (default: Coinbase).
    """
    tab_name = os.getenv("COINBASE_TAB_NAME", "Coinbase")
    raise NotImplementedError(
        f"Coinbase ingest not yet implemented. "
        f"Will read from tab '{tab_name}' (set COINBASE_TAB_NAME to override). "
        f"Column format TBD."
    )
