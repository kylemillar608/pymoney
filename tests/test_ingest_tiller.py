"""Tests for Tiller ingest (gspread mocked)."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from pymoney.db import get_in_memory_connection
from pymoney.ingest.tiller import (
    _make_balance_id,
    _make_transaction_id,
    _parse_date,
    fetch_balances,
    fetch_transactions,
    ingest_balances,
    ingest_transactions,
)


# --- Unit tests ---

def test_parse_date_slash_format():
    assert _parse_date("4/15/2024") == date(2024, 4, 15)


def test_parse_date_iso_format():
    assert _parse_date("2024-04-15") == date(2024, 4, 15)


def test_parse_date_empty():
    assert _parse_date("") is None


def test_parse_date_invalid():
    assert _parse_date("not-a-date") is None


def test_make_transaction_id_uses_transaction_id_field():
    row = {"Transaction ID": "abc-123", "Date": "1/1/2024", "Amount": "10"}
    assert _make_transaction_id(row) == "abc-123"


def test_make_transaction_id_fallback():
    row = {"Date": "1/1/2024", "Description": "STARBUCKS", "Amount": "-5.50", "Account": "Chase"}
    tx_id = _make_transaction_id(row)
    assert isinstance(tx_id, str)
    assert len(tx_id) == 32  # md5 hex


# --- Integration tests with mocked gspread ---

_SAMPLE_TRANSACTIONS = [
    {
        "Date": "3/15/2024",
        "Description": "TRADER JOE'S",
        "Full Description": "TRADER JOE'S #123",
        "Amount": "-45.67",
        "Category": "Groceries",
        "Account": "Chase Checking",
        "Account #": "1234",
        "Institution": "Chase",
        "Month": "2024-03",
        "Week": "2024-03-11",
        "Transaction ID": "tx-001",
        "Account ID": "",
        "Check Number": "",
        "Full Description": "TRADER JOE'S #123",
        "Date Added": "3/16/2024",
        "Categorized Date": "",
        "Source": "tiller",
    }
]

_SAMPLE_BALANCES = [
    {
        "Date": "3/31/2024",
        "Time": "12:00",
        "Institution": "Chase",
        "Account": "Chase Checking",
        "Account #": "1234",
        "Account ID": "acct-001",
        "Balance": "5000.00",
    }
]


def _make_mock_sheet(transactions: list[dict], balances: list[dict]) -> MagicMock:
    sheet = MagicMock()
    tx_ws = MagicMock()
    tx_ws.get_all_records.return_value = transactions
    bal_ws = MagicMock()
    bal_ws.get_all_records.return_value = balances
    sheet.worksheet.side_effect = lambda name: tx_ws if name == "Transactions" else bal_ws
    return sheet


@patch("pymoney.ingest.tiller._get_sheet")
def test_fetch_transactions_returns_rows(mock_get_sheet):
    mock_get_sheet.return_value = _make_mock_sheet(_SAMPLE_TRANSACTIONS, [])
    rows = fetch_transactions()
    assert len(rows) == 1
    assert rows[0]["description"] == "TRADER JOE'S"
    assert rows[0]["amount"] == -45.67
    assert rows[0]["id"] == "tx-001"


@patch("pymoney.ingest.tiller._get_sheet")
def test_fetch_balances_returns_rows(mock_get_sheet):
    mock_get_sheet.return_value = _make_mock_sheet([], _SAMPLE_BALANCES)
    rows = fetch_balances()
    assert len(rows) == 1
    assert rows[0]["account"] == "Chase Checking"
    assert rows[0]["balance"] == 5000.0


@patch("pymoney.ingest.tiller._get_sheet")
@patch("pymoney.ingest.tiller.get_connection")
def test_ingest_transactions_upsert_dedup(mock_get_conn, mock_get_sheet):
    """Second ingest of same data should not insert duplicates."""
    conn = get_in_memory_connection()
    mock_get_conn.return_value = conn
    mock_get_sheet.return_value = _make_mock_sheet(_SAMPLE_TRANSACTIONS, [])

    count1 = ingest_transactions()
    count2 = ingest_transactions()

    assert count1 == 1
    assert count2 == 0

    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert total == 1


@patch("pymoney.ingest.tiller._get_sheet")
@patch("pymoney.ingest.tiller.get_connection")
def test_ingest_balances_upsert_dedup(mock_get_conn, mock_get_sheet):
    """Second balance ingest should not insert duplicates."""
    conn = get_in_memory_connection()
    mock_get_conn.return_value = conn
    mock_get_sheet.return_value = _make_mock_sheet([], _SAMPLE_BALANCES)

    count1 = ingest_balances()
    count2 = ingest_balances()

    assert count1 == 1
    assert count2 == 0
