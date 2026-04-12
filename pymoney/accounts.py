"""Account metadata sync from config/accounts.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    import duckdb

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "accounts.yaml"


def sync_accounts(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
) -> None:
    """Upsert account metadata from YAML config into the accounts DB table."""
    path = config_path or _CONFIG_PATH
    if not path.exists():
        return

    with path.open() as f:
        data = yaml.safe_load(f)

    for acct in data.get("accounts", []):
        name = acct["name"]
        acct_type = acct.get("type")
        acct_class = acct.get("class")
        conn.execute("DELETE FROM accounts WHERE name = ?", [name])
        conn.execute(
            "INSERT INTO accounts (name, type, class) VALUES (?, ?, ?)",
            [name, acct_type, acct_class],
        )
