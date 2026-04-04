"""Fidelity CSV → investment_transactions ingest."""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator

from pymoney.db import get_connection


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


def _find_header_row(rows: list[list[str]]) -> int | None:
    """Find the index of the header row by looking for 'Run Date'."""
    for i, row in enumerate(rows):
        if row and row[0].strip() == "Run Date":
            return i
    return None


def load_fidelity_csv(filepath: str | Path) -> list[FidelityTransaction]:
    """Parse a Fidelity CSV export and return validated transactions."""
    path = Path(filepath)
    raw_rows: list[list[str]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            raw_rows.append(row)

    header_idx = _find_header_row(raw_rows)
    if header_idx is None:
        raise ValueError(f"Could not find header row in {filepath}")

    headers = [h.strip() for h in raw_rows[header_idx]]
    transactions: list[FidelityTransaction] = []

    for row in raw_rows[header_idx + 1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))

        data: dict[str, str] = dict(zip(headers, row))
        run_date_val = data.get("Run Date", "")
        if not run_date_val or not run_date_val.strip():
            continue

        run_date = _parse_date(run_date_val)
        if run_date is None:
            continue

        action = data.get("Action", "").strip()
        symbol = data.get("Symbol", "").strip() or None
        account_number = data.get("Account Number", "").strip() or None
        amount_val = _parse_decimal(data.get("Amount", ""))
        tx_id = _make_id(account_number or "", run_date, symbol or "", action, amount_val)

        tx = FidelityTransaction(
            id=tx_id,
            run_date=run_date,
            account=data.get("Account", "").strip() or None,
            account_number=account_number,
            action=action,
            action_type=_parse_action_type(action),
            symbol=symbol,
            description=data.get("Description", "").strip() or None,
            security_type=data.get("Type", "").strip() or None,
            quantity=_parse_decimal(data.get("Quantity", "") or data.get("Exchange Quantity", "")),
            price=_parse_decimal(data.get("Price", "")),
            amount=amount_val,
            commission=_parse_decimal(data.get("Commission", "")),
            fees=_parse_decimal(data.get("Fees", "")),
            settlement_date=_parse_date(data.get("Settlement Date", "")),
        )
        transactions.append(tx)

    return transactions


def ingest_fidelity(filepath: str | Path, db_path: str | None = None) -> int:
    """Load and upsert Fidelity CSV into investment_transactions. Returns count inserted."""
    transactions = load_fidelity_csv(filepath)
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
