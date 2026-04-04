"""Google Sheets (Tiller) → transactions and account_balances ingest."""

from __future__ import annotations

import hashlib
import os
from datetime import date, datetime
from typing import Any

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

from pymoney.db import get_connection

load_dotenv()

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_TRANSACTIONS_TAB = "Transactions"
_BALANCES_TAB = "Balance History"


def _get_client() -> gspread.Client:
    """Build authenticated gspread client from service account JSON."""
    service_account_path = os.path.expanduser(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "~/.config/pymoney/service_account.json")
    )
    creds = Credentials.from_service_account_file(service_account_path, scopes=_SCOPES)
    return gspread.authorize(creds)


def _get_sheet() -> gspread.Spreadsheet:
    """Open the Tiller spreadsheet."""
    spreadsheet_id = os.getenv("TILLER_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ValueError("TILLER_SPREADSHEET_ID environment variable not set")
    client = _get_client()
    return client.open_by_key(spreadsheet_id)


def _parse_date(value: str) -> date | None:
    """Parse a date string from Tiller (M/D/YYYY or YYYY-MM-DD)."""
    if not value:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _make_transaction_id(row: dict[str, Any]) -> str:
    """Generate a stable ID for a transaction row."""
    transaction_id = row.get("Transaction ID", "")
    if transaction_id:
        return transaction_id
    # Fallback: hash of key fields
    key = f"{row.get('Date', '')}{row.get('Description', '')}{row.get('Amount', '')}{row.get('Account', '')}"
    return hashlib.md5(key.encode()).hexdigest()


def _make_balance_id(row: dict[str, Any]) -> str:
    """Generate a stable ID for a balance row."""
    key = f"{row.get('Date', '')}{row.get('Account', '')}{row.get('Account #', '')}{row.get('Balance', '')}"
    return hashlib.md5(key.encode()).hexdigest()


def fetch_transactions(since_date: date | None = None) -> list[dict[str, Any]]:
    """Read Transactions tab and return list of dicts ready for DB upsert."""
    sheet = _get_sheet()
    ws = sheet.worksheet(_TRANSACTIONS_TAB)
    records = ws.get_all_records()

    rows = []
    for r in records:
        tx_date = _parse_date(str(r.get("Date", "")))
        if tx_date is None:
            continue
        if since_date and tx_date < since_date:
            continue

        rows.append({
            "id": _make_transaction_id(r),
            "date": tx_date,
            "description": str(r.get("Description", "")).strip(),
            "full_description": str(r.get("Full Description", "")).strip() or None,
            "amount": float(r.get("Amount", 0)),
            "category": str(r.get("Category", "")).strip() or None,
            "account": str(r.get("Account", "")).strip(),
            "account_number": str(r.get("Account #", "")).strip() or None,
            "institution": str(r.get("Institution", "")).strip() or None,
            "month": str(r.get("Month", "")).strip() or None,
            "week": str(r.get("Week", "")).strip() or None,
            "check_number": str(r.get("Check Number", "")).strip() or None,
            "date_added": _parse_date(str(r.get("Date Added", ""))),
            "categorized_date": _parse_date(str(r.get("Categorized Date", ""))),
            "source": str(r.get("Source", "")).strip() or None,
            "manually_overridden": False,
        })
    return rows


def fetch_balances(since_date: date | None = None) -> list[dict[str, Any]]:
    """Read Balance History tab and return list of dicts ready for DB upsert."""
    sheet = _get_sheet()
    ws = sheet.worksheet(_BALANCES_TAB)
    records = ws.get_all_records()

    rows = []
    for r in records:
        bal_date = _parse_date(str(r.get("Date", "")))
        if bal_date is None:
            continue
        if since_date and bal_date < since_date:
            continue

        rows.append({
            "id": _make_balance_id(r),
            "date": bal_date,
            "time": str(r.get("Time", "")).strip() or None,
            "institution": str(r.get("Institution", "")).strip() or None,
            "account": str(r.get("Account", "")).strip(),
            "account_number": str(r.get("Account #", "")).strip() or None,
            "account_id": str(r.get("Account ID", "")).strip() or None,
            "balance": float(r.get("Balance", 0)),
        })
    return rows


def ingest_transactions(since_date: date | None = None, db_path: str | None = None) -> int:
    """Fetch transactions from Tiller and upsert into DB. Returns count inserted."""
    rows = fetch_transactions(since_date=since_date)
    if not rows:
        return 0

    conn = get_connection(db_path)
    inserted = 0
    for row in rows:
        result = conn.execute(
            "SELECT id FROM transactions WHERE id = ?", [row["id"]]
        ).fetchone()
        if result is None:
            conn.execute("""
                INSERT INTO transactions
                    (id, date, description, full_description, amount, category, account,
                     account_number, institution, month, week, check_number, date_added,
                     categorized_date, source, manually_overridden)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                row["id"], row["date"], row["description"], row["full_description"],
                row["amount"], row["category"], row["account"], row["account_number"],
                row["institution"], row["month"], row["week"], row["check_number"],
                row["date_added"], row["categorized_date"], row["source"],
                row["manually_overridden"],
            ])
            inserted += 1
    return inserted


def ingest_balances(since_date: date | None = None, db_path: str | None = None) -> int:
    """Fetch balances from Tiller and upsert into DB. Returns count inserted."""
    rows = fetch_balances(since_date=since_date)
    if not rows:
        return 0

    conn = get_connection(db_path)
    inserted = 0
    for row in rows:
        result = conn.execute(
            "SELECT id FROM account_balances WHERE id = ?", [row["id"]]
        ).fetchone()
        if result is None:
            conn.execute("""
                INSERT INTO account_balances
                    (id, date, time, institution, account, account_number, account_id, balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                row["id"], row["date"], row["time"], row["institution"],
                row["account"], row["account_number"], row["account_id"], row["balance"],
            ])
            inserted += 1
    return inserted
