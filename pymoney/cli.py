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
def ingest_fidelity() -> None:
    """Ingest Fidelity investment transactions from Google Sheets."""
    from pymoney.ingest.fidelity import ingest_fidelity as _ingest_fidelity

    count = _ingest_fidelity()
    click.echo(f"Ingested {count} investment transactions from Fidelity tab.")


@ingest.command("coinbase")
def ingest_coinbase() -> None:
    """Ingest Coinbase BTC trades from Google Sheets (not yet implemented)."""
    from pymoney.ingest.coinbase import ingest_coinbase as _ingest_coinbase

    try:
        _ingest_coinbase()
    except NotImplementedError as e:
        click.echo(f"Not yet implemented: {e}")


@ingest.command("all")
def ingest_all() -> None:
    """Run full ingest: Tiller + Fidelity from Google Sheets (Coinbase skipped until implemented)."""
    from pymoney.ingest.fidelity import ingest_fidelity as _ingest_fidelity
    from pymoney.ingest.tiller import ingest_balances, ingest_transactions

    tx_count = ingest_transactions()
    bal_count = ingest_balances()
    click.echo(f"Tiller: {tx_count} transactions, {bal_count} balance records.")

    inv_count = _ingest_fidelity()
    click.echo(f"Fidelity: {inv_count} investment transactions.")

    click.echo("Coinbase: skipped (not yet implemented).")


@cli.command()
def categorize() -> None:
    """Re-run categorization rules on uncategorized transactions."""
    from pymoney.categorize.rules import categorize_uncategorized

    count = categorize_uncategorized()
    click.echo(f"Categorized {count} transactions.")


@cli.command("install-hooks")
def install_hooks() -> None:
    """Install git pre-commit hook to guard against committing financial data."""
    import shutil
    import stat
    import subprocess

    git_root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True
    ).stdout.strip()

    src = Path(git_root) / "scripts" / "check-no-data.sh"
    dest = Path(git_root) / ".git" / "hooks" / "pre-commit"

    if not src.exists():
        click.echo(f"Error: hook script not found at {src}", err=True)
        raise SystemExit(1)

    shutil.copy2(src, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    click.echo(f"Installed pre-commit hook: {dest}")


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
