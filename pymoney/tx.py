"""Transaction review and manual categorization."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    import duckdb

from pymoney.categorize.rules import _CONFIG_PATH, _load_rules
from pymoney.labels import _CONFIG_PATH as _LABEL_CONFIG_PATH


def get_summary(conn: duckdb.DuckDBPyConnection) -> dict:
    """Return uncategorized transaction stats."""
    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    uncategorized = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE category IS NULL OR category = ''"
    ).fetchone()[0]

    top = conn.execute("""
        SELECT description, COUNT(*) AS count, SUM(ABS(amount)) AS total
        FROM transactions
        WHERE category IS NULL OR category = ''
        GROUP BY description
        ORDER BY count DESC
        LIMIT 10
    """).fetchall()

    return {
        "total": total,
        "uncategorized": uncategorized,
        "unique_descriptions": conn.execute("""
            SELECT COUNT(DISTINCT description) FROM transactions
            WHERE category IS NULL OR category = ''
        """).fetchone()[0],
        "top_descriptions": top,
    }


def run_review(
    conn: duckdb.DuckDBPyConnection,
    config_path: Path | None = None,
    label_config_path: Path | None = None,
) -> None:
    """
    Interactive review of uncategorized transactions, grouped by description.

    For each description group: show stats, prompt for category, optionally write rule.
    """
    config_path = config_path or _CONFIG_PATH
    label_config_path = label_config_path or _LABEL_CONFIG_PATH
    cat_names = [c["name"] for c in _load_rules(config_path)]

    groups = conn.execute("""
        SELECT
            description,
            COUNT(*)         AS count,
            SUM(ABS(amount)) AS total,
            MIN(date)        AS first_date,
            MAX(date)        AS last_date
        FROM transactions
        WHERE category IS NULL OR category = ''
        GROUP BY description
        ORDER BY count DESC
    """).fetchall()

    if not groups:
        click.echo("No uncategorized transactions.")
        return

    total_groups = len(groups)
    click.echo(f"\n{total_groups} description groups to review. Press q to quit and save progress.\n")

    for i, (description, count, total, first_date, last_date) in enumerate(groups, 1):
        click.echo("─" * 60)
        click.echo(f"[{i}/{total_groups}]  {description}")
        click.echo(f"          {count} transactions · ${total:,.0f} total · {first_date} → {last_date}")
        click.echo()

        # Display categories in 3 columns
        per_row = 3
        col_w = 22
        for j in range(0, len(cat_names), per_row):
            row = cat_names[j : j + per_row]
            parts = [f"{j + k + 1:2}) {name:<{col_w}}" for k, name in enumerate(row)]
            click.echo("  " + "  ".join(parts))

        click.echo()
        click.echo("  s) Skip   r) Write rule hint   q) Quit")
        click.echo()

        while True:
            raw = click.prompt("  Pick", default="s").strip()

            if raw.lower() == "q":
                click.echo("\nProgress saved. Exiting.")
                return

            if raw.lower() == "s":
                break

            if raw.lower() == "r":
                _print_rule_hint(description)
                break

            chosen = _resolve_category(raw, cat_names)
            if chosen is None:
                continue

            # Apply one-off assignment
            conn.execute(
                """
                UPDATE transactions
                SET category = ?, manually_overridden = TRUE
                WHERE (category IS NULL OR category = '') AND description = ?
                """,
                [chosen, description],
            )
            click.echo(f"\n  ✓ {count} transaction(s) → {chosen}")

            # Offer rule writing as opt-in
            if click.confirm("  Also write a rule hint to screen?", default=False):
                _print_rule_hint(description)

            # Label prompt
            _prompt_labels(conn, description, label_config_path)

            break

        click.echo()

    click.echo("─" * 60)
    click.echo("Review complete.")


def _resolve_category(raw: str, cat_names: list[str]) -> str | None:
    """Resolve user input to a category name. Returns None and prints error on failure."""
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(cat_names):
            return cat_names[idx]
        click.echo(f"  Invalid number. Pick 1–{len(cat_names)}.")
        return None

    matches = [n for n in cat_names if raw.lower() in n.lower()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        click.echo(f"  Ambiguous: {', '.join(matches)}")
        return None

    click.echo("  Unknown category. Enter a number or partial category name.")
    return None


def _print_rule_hint(description: str) -> None:
    """Print a YAML snippet the user can paste into categories.yaml."""
    click.echo()
    click.echo("  Add to the relevant category's rules in config/categories.yaml:")
    click.echo(f'      - contains: ["{description}"]')
    click.echo()


def _prompt_labels(
    conn: duckdb.DuckDBPyConnection,
    description: str,
    label_config_path: Path | None = None,
) -> None:
    """Prompt to apply labels to all transactions with the given description."""
    existing_labels = [
        r[0] for r in conn.execute(
            "SELECT DISTINCT label FROM transaction_labels ORDER BY label"
        ).fetchall()
    ]

    while True:
        click.echo()
        if existing_labels:
            options = "  ".join(f"[{i + 1}] {l}" for i, l in enumerate(existing_labels))
            click.echo(f"  Labels: {options}")
        click.echo("  Add label (number, name, or Enter to skip):")
        raw = click.prompt("  Label", default="").strip()

        if not raw:
            break

        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(existing_labels):
                label_str = existing_labels[idx]
            else:
                click.echo(f"  Invalid number.")
                continue
        else:
            label_str = raw

        # Apply label to all transactions with this description
        tx_ids = [r[0] for r in conn.execute(
            "SELECT id FROM transactions WHERE description = ?", [description]
        ).fetchall()]
        for tx_id in tx_ids:
            conn.execute(
                "INSERT INTO transaction_labels (transaction_id, label) VALUES (?, ?) ON CONFLICT DO NOTHING",
                [tx_id, label_str],
            )
        click.echo(f"  ✓ Label '{label_str}' applied to {len(tx_ids)} transaction(s).")

        if label_str not in existing_labels:
            existing_labels.append(label_str)
            existing_labels.sort()
            _print_label_rule_hint(description, label_str)


def _print_label_rule_hint(description: str, label: str) -> None:
    """Print a YAML snippet the user can paste into labels.yaml."""
    click.echo()
    click.echo("  Add to config/labels.yaml to apply this label automatically:")
    click.echo(f"    - label: {label}")
    click.echo(f'      rules:')
    click.echo(f'        - contains: "{description}"')
    click.echo()
