"""Fidelity (Google Sheets tab) → investment_transactions ingest."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import date, datetime
from typing import Any

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from pydantic import BaseModel, field_validator

from pymoney.db import get_connection

load_dotenv()

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

_ACTION_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"BOUGHT|BUY", "BUY"),
    (r"SOLD|SELL", "SELL"),
    (r"REINVESTMENT|REINVEST", "REINVESTMENT"),
    (r"DIVIDEND", "DIVIDEND"),
    (r"TRANSFER", "TRANSFER"),
]


def _parse_action_type(action: str) -> str:
    """Parse a verbose Fidelity action string into a normalized action_type."""
    upper = action.upper()
    for pattern, action_type in _ACTION_TYPE_PATTERNS:
        if re.search(pattern, upper):
            return action_type
    return "OTHER"


def _parse_date(value: str) -> date | None:
    """Parse Fidelity date strings."""
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: str) -> float | None:
    """Parse a decimal string, stripping $ and commas."""
    if not value or not value.strip():
        return None
    cleaned = value.strip().replace("$", "").replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _make_id(account_number: str, run_date: Any, symbol: str, action: str, amount: Any) -> str:
    """Generate a stable ID by hashing key fields."""
    key = f"{account_number}|{run_date}|{symbol}|{action}|{amount}"
    return hashlib.md5(key.encode()).hexdigest()


class FidelityTransaction(BaseModel):
    """Validated Fidelity investment transaction."""

    id: str
    run_date: date
    account: str | None
    account_number: str | None
    action: str
    action_type: str
    symbol: str | None
    description: str | None
    security_type: str | None
    quantity: float | None
    price: float | None
    amount: float | None
    commission: float | None
    fees: float | None
    settlement_date: date | None

    @field_validator("run_date", mode="before")
    @classmethod
    def parse_run_date(cls, v: Any) -> date:
        if isinstance(v, date):
            return v
        parsed = _parse_date(str(v))
        if parsed is None:
            raise ValueError(f"Cannot parse date: {v!r}")
        return parsed


def _get_client() -> gspread.Client:
    """Build authenticated gspread client from service account JSON."""
    service_account_path = os.path.expanduser(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "~/.config/pymoney/service_account.json")
    )
    creds = Credentials.from_service_account_file(service_account_path, scopes=_SCOPES)
    return gspread.authorize(creds)


def _get_sheet() -> gspread.Spreadsheet:
    """Open the spreadsheet."""
    spreadsheet_id = os.getenv("TILLER_SPREADSHEET_ID")
    if not spreadsheet_id:
        raise ValueError("TILLER_SPREADSHEET_ID environment variable not set")
    client = _get_client()
    return client.open_by_key(spreadsheet_id)


def load_fidelity_sheet() -> list[FidelityTransaction]:
    """Read Fidelity tab from Google Sheets and return validated transactions."""
    tab_name = os.getenv("FIDELITY_TAB_NAME", "Fidelity")
    sheet = _get_sheet()
    ws = sheet.worksheet(tab_name)
    records = ws.get_all_records()

    transactions: list[FidelityTransaction] = []
    for r in records:
        run_date_val = str(r.get("Run Date", "")).strip()
        if not run_date_val:
            continue
        run_date = _parse_date(run_date_val)
        if run_date is None:
            continue

        action = str(r.get("Action", "")).strip()
        symbol = str(r.get("Symbol", "")).strip() or None
        account_number = str(r.get("Account Number", "")).strip() or None
        amount_val = _parse_decimal(str(r.get("Amount", "")))
        tx_id = _make_id(account_number or "", run_date, symbol or "", action, amount_val)

        tx = FidelityTransaction(
            id=tx_id,
            run_date=run_date,
            account=str(r.get("Account", "")).strip() or None,
            account_number=account_number,
            action=action,
            action_type=_parse_action_type(action),
            symbol=symbol,
            description=str(r.get("Description", "")).strip() or None,
            security_type=str(r.get("Type", "")).strip() or None,
            quantity=_parse_decimal(str(r.get("Quantity", ""))),
            price=_parse_decimal(str(r.get("Price", ""))),
            amount=amount_val,
            commission=_parse_decimal(str(r.get("Commission", ""))),
            fees=_parse_decimal(str(r.get("Fees", ""))),
            settlement_date=_parse_date(str(r.get("Settlement Date", ""))),
        )
        transactions.append(tx)

    return transactions


def ingest_fidelity(db_path: str | None = None) -> int:
    """Load Fidelity tab from Google Sheets and upsert into investment_transactions.

    Returns count inserted.
    """
    transactions = load_fidelity_sheet()
    if not transactions:
        return 0

    conn = get_connection(db_path)
    inserted = 0
    for tx in transactions:
        result = conn.execute(
            "SELECT id FROM investment_transactions WHERE id = ?", [tx.id]
        ).fetchone()
        if result is None:
            conn.execute("""
                INSERT INTO investment_transactions
                    (id, run_date, account, account_number, action, action_type, symbol,
                     description, security_type, quantity, price, amount, commission,
                     fees, settlement_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                tx.id, tx.run_date, tx.account, tx.account_number, tx.action,
                tx.action_type, tx.symbol, tx.description, tx.security_type,
                tx.quantity, tx.price, tx.amount, tx.commission, tx.fees,
                tx.settlement_date,
            ])
            inserted += 1
    return inserted
