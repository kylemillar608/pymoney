"""Transaction review and manual categorization."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    import duckdb

from pymoney.categorize.rules import _CONFIG_PATH, _load_rules


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
) -> None:
    """
    Interactive review of uncategorized transactions, grouped by description.

    For each description group: show stats, prompt for category, optionally write rule.
    """
    config_path = config_path or _CONFIG_PATH
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
