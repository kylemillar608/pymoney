"""Budget config loader."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    import duckdb

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "budget.yaml"


def sync_budget(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
) -> int:
    """
    Upsert default monthly budget targets from budget.yaml into the budget table.

    Each entry is written as month='default' so reports can join on it without
    knowing the current month. Returns the number of categories upserted.
    """
    path = config_path or _CONFIG_PATH
    with path.open() as f:
        data = yaml.safe_load(f)

    entries = data.get("budget", {})
    count = 0
    for category, amount in entries.items():
        row_id = hashlib.md5(f"default:{category}".encode()).hexdigest()
        conn.execute("DELETE FROM budget WHERE id = ?", [row_id])
        conn.execute(
            "INSERT INTO budget (id, category, month, amount) VALUES (?, ?, 'default', ?)",
            [row_id, category, float(amount)],
        )
        count += 1
    return count
