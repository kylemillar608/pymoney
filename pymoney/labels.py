"""Label application engine driven by config/labels.yaml.

Labels are strings applied to transactions via rules. Unlike categories
(first-match), ALL rules that match apply their label — a transaction can
carry multiple labels simultaneously.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    import duckdb

from pymoney.categorize.rules import _eval_rule

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "labels.yaml"


def _load_label_defs(config_path: Path | None = None) -> list[dict[str, Any]]:
    path = config_path or _CONFIG_PATH
    if not path.exists():
        return []
    with path.open() as f:
        data = yaml.safe_load(f)
    return data.get("labels", [])


def apply_label_rules(
    description: str,
    full_description: str | None = None,
    account: str | None = None,
    institution: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    config_path: Path | None = None,
) -> set[str]:
    """
    Apply label rules to a transaction, returning the set of all matching labels.

    Unlike categories (first-match), every label definition whose rules match
    contributes its label to the result set.
    """
    label_defs = _load_label_defs(config_path)
    desc = description.upper()
    full_desc = (full_description or "").upper()
    acct = (account or "").upper()
    inst = (institution or "").upper()
    amt = float(amount) if amount is not None else 0.0
    cat = (category or "").upper()

    matched: set[str] = set()
    for label_def in label_defs:
        label = label_def["label"]
        for rule in label_def.get("rules", []):
            if _eval_rule(rule, desc, full_desc, acct, inst, amt, cat):
                matched.add(label)
                break  # one matching rule per label def is sufficient
    return matched


def label_unlabeled(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
) -> int:
    """
    Apply label rules to transactions that have no labels yet.

    Returns the number of labels applied.
    """
    rows = conn.execute("""
        SELECT id, description, full_description, account, institution, amount, category
        FROM transactions
        WHERE id NOT IN (SELECT DISTINCT transaction_id FROM transaction_labels)
    """).fetchall()

    count = 0
    for row_id, desc, full_desc, acct, inst, amount, cat in rows:
        labels = apply_label_rules(desc, full_desc, acct, inst, amount, cat, config_path)
        for label in labels:
            conn.execute(
                "INSERT INTO transaction_labels (transaction_id, label) VALUES (?, ?)",
                [row_id, label],
            )
            count += 1
    return count


def preview_label_unlabeled(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
) -> list[dict]:
    """
    Dry-run of label_unlabeled: show what labels would be applied to
    transactions that currently have no labels.

    Returns list of dicts: {label, description, change ('add'), count}.
    """
    rows = conn.execute("""
        SELECT id, description, full_description, account, institution, amount, category
        FROM transactions
        WHERE id NOT IN (SELECT DISTINCT transaction_id FROM transaction_labels)
    """).fetchall()

    tally: dict[tuple, int] = {}
    for row_id, desc, full_desc, acct, inst, amount, cat in rows:
        labels = apply_label_rules(desc, full_desc, acct, inst, amount, cat, config_path)
        for label in labels:
            key = (label, desc)
            tally[key] = tally.get(key, 0) + 1

    return [
        {"label": k[0], "description": k[1], "change": "add", "count": v}
        for k, v in sorted(tally.items(), key=lambda x: -x[1])
    ]


def preview_label_all(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
) -> list[dict]:
    """
    Dry-run of label_all. Returns changes grouped by (label, description).

    Each dict: {label, description, change ('add'|'remove'), count}
    sorted by count descending.
    """
    # Current labels per transaction
    current_rows = conn.execute(
        "SELECT transaction_id, label FROM transaction_labels"
    ).fetchall()
    current: dict[str, set[str]] = {}
    for tx_id, label in current_rows:
        current.setdefault(tx_id, set()).add(label)

    # Compute new labels for all transactions
    tx_rows = conn.execute("""
        SELECT id, description, full_description, account, institution, amount, category
        FROM transactions
    """).fetchall()

    desc_map: dict[str, str] = {r[0]: r[1] for r in tx_rows}
    proposed: dict[str, set[str]] = {}
    for row_id, desc, full_desc, acct, inst, amount, cat in tx_rows:
        labels = apply_label_rules(desc, full_desc, acct, inst, amount, cat, config_path)
        if labels:
            proposed[row_id] = labels

    # Diff
    tally: dict[tuple, int] = {}
    all_ids = set(current) | set(proposed)
    for tx_id in all_ids:
        old = current.get(tx_id, set())
        new = proposed.get(tx_id, set())
        desc = desc_map.get(tx_id, "?")
        for label in new - old:
            key = (label, desc, "add")
            tally[key] = tally.get(key, 0) + 1
        for label in old - new:
            key = (label, desc, "remove")
            tally[key] = tally.get(key, 0) + 1

    return [
        {"label": k[0], "description": k[1], "change": k[2], "count": v}
        for k, v in sorted(tally.items(), key=lambda x: -x[1])
    ]


def label_all(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
) -> int:
    """
    Delete all existing labels and reapply rules to every transaction.

    Returns the number of labels applied.
    """
    conn.execute("DELETE FROM transaction_labels")

    rows = conn.execute("""
        SELECT id, description, full_description, account, institution, amount, category
        FROM transactions
    """).fetchall()

    count = 0
    for row_id, desc, full_desc, acct, inst, amount, cat in rows:
        labels = apply_label_rules(desc, full_desc, acct, inst, amount, cat, config_path)
        for label in labels:
            conn.execute(
                "INSERT INTO transaction_labels (transaction_id, label) VALUES (?, ?)",
                [row_id, label],
            )
            count += 1
    return count
