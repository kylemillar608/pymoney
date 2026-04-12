"""pymoney CLI entry point."""

from __future__ import annotations

from pathlib import Path

import click

from pymoney.db import get_connection


@click.group()
def cli() -> None:
    """pymoney — personal finance system."""


# ── ingest ────────────────────────────────────────────────────────────────────

@cli.group()
def ingest() -> None:
    """Ingest financial data into the database."""


@ingest.command("tiller")
@click.option("--since", default=None, help="Only ingest transactions since this date (YYYY-MM-DD)")
def ingest_tiller(since: str | None) -> None:
    """Ingest transactions and balances from Tiller (Google Sheets)."""
    from datetime import datetime

    from pymoney.ingest.tiller import ingest_balances, ingest_transactions

    since_date = None
    if since:
        since_date = datetime.strptime(since, "%Y-%m-%d").date()

    tx_count = ingest_transactions(since_date=since_date)
    bal_count = ingest_balances(since_date=since_date)
    click.echo(f"Ingested {tx_count} spending transactions, {bal_count} account balance records from Tiller.")


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
    click.echo(f"Tiller: {tx_count} spending transactions, {bal_count} account balance records.")

    inv_count = _ingest_fidelity()
    click.echo(f"Fidelity: {inv_count} investment transactions.")

    click.echo("Coinbase: skipped (not yet implemented).")


@ingest.result_callback()
def _ingest_result(*args: object, **kwargs: object) -> None:
    pass


# ── preview helpers ───────────────────────────────────────────────────────────

def _print_cat_preview(changes: list[dict], limit: int = 50) -> None:
    if not changes:
        click.echo("  No category changes.")
        return
    total = sum(r["count"] for r in changes)
    click.echo(f"  {'Current':<25} {'New':<25} {'Description':<32} {'#':>5}")
    click.echo("  " + "─" * 90)
    for r in changes[:limit]:
        old = r["old_category"] or "(none)"
        click.echo(
            f"  {old:<25} {r['new_category']:<25}"
            f" {r['description'][:32]:<32} {r['count']:>5}"
        )
    if len(changes) > limit:
        click.echo(f"  ... {len(changes) - limit} more groups")
    click.echo(f"\n  {total} transaction(s) across {len(changes)} group(s).")


def _print_label_preview(changes: list[dict], limit: int = 50) -> None:
    if not changes:
        click.echo("  No label changes.")
        return
    adds = sum(c["count"] for c in changes if c["change"] == "add")
    removes = sum(c["count"] for c in changes if c["change"] == "remove")
    click.echo(f"  {'Change':<8} {'Label':<20} {'Description':<36} {'#':>5}")
    click.echo("  " + "─" * 72)
    for r in changes[:limit]:
        click.echo(
            f"  {r['change']:<8} {r['label']:<20}"
            f" {r['description'][:36]:<36} {r['count']:>5}"
        )
    if len(changes) > limit:
        click.echo(f"  ... {len(changes) - limit} more groups")
    click.echo(f"\n  +{adds} added · -{removes} removed")


# ── categorize ────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--all", "run_all", is_flag=True, help="Re-categorize all transactions, not just uncategorized ones.")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them.")
def categorize(run_all: bool, dry_run: bool) -> None:
    """Run categorization rules on transactions."""
    from pymoney.categorize.rules import (
        categorize_all, categorize_uncategorized,
        preview_categorize_all, preview_categorize_uncategorized,
    )

    if run_all:
        changes = preview_categorize_all()
        click.echo()
        _print_cat_preview(changes)
        if dry_run:
            return
        if not changes:
            return
        click.echo()
        if not click.confirm("Apply changes?", default=False):
            click.echo("Cancelled.")
            return
        count = categorize_all()
        click.echo(f"Updated {count} transactions.")
    else:
        if dry_run:
            changes = preview_categorize_uncategorized()
            click.echo()
            _print_cat_preview(changes)
        else:
            count = categorize_uncategorized()
            click.echo(f"Categorized {count} transactions.")


# ── label ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--all", "run_all", is_flag=True, help="Re-label all transactions, not just unlabeled ones.")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them.")
def label(run_all: bool, dry_run: bool) -> None:
    """Apply label rules to transactions."""
    from pymoney.labels import label_all, label_unlabeled, preview_label_all, preview_label_unlabeled

    conn = get_connection()
    if run_all:
        changes = preview_label_all(conn)
        click.echo()
        _print_label_preview(changes)
        if dry_run:
            return
        if not changes:
            return
        click.echo()
        if not click.confirm("Apply changes?", default=False):
            click.echo("Cancelled.")
            return
        count = label_all(conn)
        click.echo(f"Applied {count} labels.")
    else:
        if dry_run:
            changes = preview_label_unlabeled(conn)
            click.echo()
            _print_label_preview(changes)
        else:
            count = label_unlabeled(conn)
            click.echo(f"Applied {count} labels to previously unlabeled transactions.")


# ── apply ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--all", "run_all", is_flag=True, help="Re-categorize and re-label all transactions.")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying them.")
def apply(run_all: bool, dry_run: bool) -> None:
    """Run categorization and labeling together."""
    from pymoney.categorize.rules import (
        categorize_all, categorize_uncategorized,
        preview_categorize_all, preview_categorize_uncategorized,
    )
    from pymoney.labels import label_all, label_unlabeled, preview_label_all, preview_label_unlabeled

    conn = get_connection()
    if run_all:
        cat_changes = preview_categorize_all()
        label_changes = preview_label_all(conn)
        click.echo()
        click.echo("  Category changes:")
        _print_cat_preview(cat_changes)
        click.echo()
        click.echo("  Label changes:")
        _print_label_preview(label_changes)
        if dry_run:
            return
        if not cat_changes and not label_changes:
            return
        click.echo()
        if not click.confirm("Apply all changes?", default=False):
            click.echo("Cancelled.")
            return
        cat_count = categorize_all()
        label_count = label_all(conn)
        click.echo(f"Updated {cat_count} categories, applied {label_count} labels.")
    else:
        if dry_run:
            cat_changes = preview_categorize_uncategorized()
            label_changes = preview_label_unlabeled(conn)
            click.echo()
            click.echo("  Category changes:")
            _print_cat_preview(cat_changes)
            click.echo()
            click.echo("  Label changes:")
            _print_label_preview(label_changes)
        else:
            cat_count = categorize_uncategorized()
            label_count = label_unlabeled(conn)
            click.echo(f"Categorized {cat_count} transactions, labeled {label_count}.")


# ── migrate ───────────────────────────────────────────────────────────────────

@cli.group()
def migrate() -> None:
    """Migrate to rule-based categorization (compare old vs proposed categories)."""


@migrate.command("prepare")
def migrate_prepare() -> None:
    """Run rules into proposed_category column without touching existing categories."""
    from pymoney.migrate import prepare

    conn = get_connection()
    count = prepare(conn)
    click.echo(f"Prepared: {count} transactions matched a rule → proposed_category set.")
    click.echo("Run 'pymoney migrate diff' to review changes before applying.")


@migrate.command("diff")
@click.option("--limit", default=50, show_default=True, help="Max rows to display.")
def migrate_diff(limit: int) -> None:
    """Show side-by-side comparison of current vs proposed categories."""
    from pymoney.migrate import diff

    conn = get_connection()
    try:
        rows = diff(conn)
    except RuntimeError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)

    if not rows:
        click.echo("No differences — proposed categories match existing ones.")
        return

    same_count = conn.execute("""
        SELECT COUNT(*) FROM transactions
        WHERE category IS NOT DISTINCT FROM proposed_category
    """).fetchone()[0]

    click.echo()
    click.echo(f"{'Old Category':<25} {'Proposed':<25} {'Description':<32} {'#':>5}")
    click.echo("─" * 90)
    for r in rows[:limit]:
        click.echo(
            f"{r['old_category']:<25} {r['proposed_category']:<25}"
            f" {r['description'][:32]:<32} {r['count']:>5}"
        )
    if len(rows) > limit:
        click.echo(f"\n  ... {len(rows) - limit} more rows (use --limit to see more)")

    click.echo(f"\n  {same_count} transactions already match · {len(rows)} groups differ")
    click.echo("\nRun 'pymoney migrate apply' to commit the proposed categories.")


@migrate.command("apply")
@click.option("--dry-run", is_flag=True, help="Show count without writing changes.")
def migrate_apply(dry_run: bool) -> None:
    """Copy proposed_category → category for all rows where a rule matched."""
    from pymoney.migrate import apply

    conn = get_connection()
    try:
        if dry_run:
            count = conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE proposed_category IS NOT NULL"
            ).fetchone()[0]
            click.echo(f"Would update {count} transactions (dry run).")
        else:
            count = apply(conn)
            click.echo(f"Updated {count} transactions.")
            click.echo("Run 'pymoney migrate clean' to remove the proposed_category column.")
    except RuntimeError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


@migrate.command("clean")
def migrate_clean() -> None:
    """Drop the proposed_category column once migration is complete."""
    from pymoney.migrate import clean

    conn = get_connection()
    clean(conn)
    click.echo("Dropped proposed_category column.")


# ── tx ────────────────────────────────────────────────────────────────────────

@cli.group()
def tx() -> None:
    """Review and manually categorize transactions."""


@tx.command("summary")
def tx_summary() -> None:
    """Show uncategorized transaction counts and top descriptions."""
    from pymoney.tx import get_summary

    conn = get_connection()
    s = get_summary(conn)

    click.echo(f"\nTotal transactions:    {s['total']:>8,}")
    click.echo(f"Uncategorized:        {s['uncategorized']:>8,}")
    click.echo(f"Unique descriptions:  {s['unique_descriptions']:>8,}")

    if s["top_descriptions"]:
        click.echo(f"\n  {'Description':<42} {'Count':>6}  {'Total':>10}")
        click.echo("  " + "─" * 62)
        for desc, count, total in s["top_descriptions"]:
            click.echo(f"  {desc[:42]:<42} {count:>6}  ${total:>9,.0f}")


@tx.command("review")
def tx_review() -> None:
    """Interactive review: assign categories to uncategorized transactions."""
    from pymoney.tx import run_review

    conn = get_connection()
    run_review(conn)


# ── sync ──────────────────────────────────────────────────────────────────────

@cli.command()
def sync() -> None:
    """Sync categories and budget from config YAML files into the database."""
    from pymoney.accounts import sync_accounts
    from pymoney.budget import sync_budget
    from pymoney.categorize.rules import sync_categories

    conn = get_connection()
    sync_categories(conn)
    sync_accounts(conn)
    budget_count = sync_budget(conn)
    click.echo(f"Synced categories, accounts, and {budget_count} budget targets.")


# ── misc ──────────────────────────────────────────────────────────────────────

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
    click.echo(f"Spending transactions:   {tx_count:>8,}")
    if tx_min:
        click.echo(f"  Date range:            {tx_min} → {tx_max}")
    click.echo(f"  Uncategorized:         {uncategorized:>8,}")
    click.echo(f"Account balance records: {bal_row[0]:>8,}")
    click.echo(f"Investment transactions: {inv_row[0]:>8,}")


if __name__ == "__main__":
    cli()
