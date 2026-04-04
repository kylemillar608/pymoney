"""pymoney CLI entry point."""

from __future__ import annotations

from pathlib import Path

import click

from pymoney.db import get_connection


@click.group()
def cli() -> None:
    """pymoney — personal finance system."""


@cli.group()
def ingest() -> None:
    """Ingest financial data into the database."""


@ingest.command("tiller")
@click.option("--since", default=None, help="Only ingest transactions since this date (YYYY-MM-DD)")
def ingest_tiller(since: str | None) -> None:
    """Ingest transactions and balances from Tiller (Google Sheets)."""
    from datetime import date as date_type, datetime

    from pymoney.ingest.tiller import ingest_balances, ingest_transactions

    since_date = None
    if since:
        since_date = datetime.strptime(since, "%Y-%m-%d").date()

    tx_count = ingest_transactions(since_date=since_date)
    bal_count = ingest_balances(since_date=since_date)
    click.echo(f"Ingested {tx_count} transactions, {bal_count} balance records from Tiller.")


@ingest.command("fidelity")
@click.argument("files", nargs=-1, type=click.Path(exists=True))
def ingest_fidelity(files: tuple[str, ...]) -> None:
    """Process Fidelity CSV files from data/raw/ or specified paths."""
    from pymoney.ingest.fidelity import ingest_fidelity as _ingest_fidelity

    if not files:
        raw_dir = Path("data/raw")
        csv_files = list(raw_dir.glob("*.csv")) if raw_dir.exists() else []
        if not csv_files:
            click.echo("No CSV files found in data/raw/")
            return
        files = tuple(str(f) for f in csv_files)

    total = 0
    for filepath in files:
        count = _ingest_fidelity(filepath)
        click.echo(f"  {filepath}: {count} records inserted")
        total += count
    click.echo(f"Total: {total} investment transactions inserted.")


@ingest.command("all")
def ingest_all() -> None:
    """Run full ingest: Tiller + all Fidelity CSVs in data/raw/."""
    from pymoney.ingest.fidelity import ingest_fidelity as _ingest_fidelity
    from pymoney.ingest.tiller import ingest_balances, ingest_transactions

    tx_count = ingest_transactions()
    bal_count = ingest_balances()
    click.echo(f"Tiller: {tx_count} transactions, {bal_count} balance records.")

    raw_dir = Path("data/raw")
    csv_files = list(raw_dir.glob("*.csv")) if raw_dir.exists() else []
    inv_total = 0
    for filepath in csv_files:
        count = _ingest_fidelity(filepath)
        click.echo(f"  Fidelity {filepath.name}: {count} records")
        inv_total += count
    click.echo(f"Fidelity total: {inv_total} investment transactions.")


@cli.command()
def categorize() -> None:
    """Re-run categorization rules on uncategorized transactions."""
    from pymoney.categorize.rules import categorize_uncategorized

    count = categorize_uncategorized()
    click.echo(f"Categorized {count} transactions.")


@cli.command()
def status() -> None:
    """Show database statistics."""
    conn = get_connection()

    tx_row = conn.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM transactions").fetchone()
    uncategorized = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE category IS NULL OR category = ''"
    ).fetchone()[0]
    bal_row = conn.execute("SELECT COUNT(*) FROM account_balances").fetchone()
    inv_row = conn.execute("SELECT COUNT(*) FROM investment_transactions").fetchone()

    tx_count, tx_min, tx_max = tx_row
    click.echo(f"Transactions:            {tx_count:>8}")
    if tx_min:
        click.echo(f"  Date range:            {tx_min} → {tx_max}")
    click.echo(f"  Uncategorized:         {uncategorized:>8}")
    click.echo(f"Account balance records: {bal_row[0]:>8}")
    click.echo(f"Investment transactions: {inv_row[0]:>8}")


# Make `pymoney ingest` work as both a group and an alias for `ingest all`
# by overriding the default `ingest` behavior when called with no subcommand.
@ingest.result_callback()
def _ingest_result(*args: object, **kwargs: object) -> None:
    pass


if __name__ == "__main__":
    cli()
