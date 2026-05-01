"""Tests for brokerage Google Sheets ingest."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from pymoney.ingest.brokerage import (
    BrokerageTransaction,
    _parse_action_type,
    _parse_date,
    _parse_decimal,
    load_brokerage_sheet,
)


# --- Unit tests ---

def test_parse_action_type_buy():
    assert _parse_action_type("YOU BOUGHT VANGUARD 500 (VFIAX)") == "BUY"


def test_parse_action_type_sell():
    assert _parse_action_type("YOU SOLD APPLE INC (AAPL)") == "SELL"


def test_parse_action_type_dividend():
    assert _parse_action_type("DIVIDEND RECEIVED") == "DIVIDEND"


def test_parse_action_type_reinvestment():
    assert _parse_action_type("REINVESTMENT") == "REINVESTMENT"


def test_parse_action_type_transfer():
    assert _parse_action_type("TRANSFERRED TO ACCOUNT") == "TRANSFER"


def test_parse_action_type_other():
    assert _parse_action_type("JOURNAL ENTRY") == "OTHER"


def test_parse_decimal_normal():
    assert _parse_decimal("1234.56") == 1234.56


def test_parse_decimal_negative():
    assert _parse_decimal("-45.00") == -45.0


def test_parse_decimal_with_dollar():
    assert _parse_decimal("$1,234.56") == 1234.56


def test_parse_decimal_empty():
    assert _parse_decimal("") is None


def test_parse_decimal_whitespace():
    assert _parse_decimal("  ") is None


def test_parse_date_slash():
    assert _parse_date("04/15/2024") == date(2024, 4, 15)


def test_parse_date_iso():
    assert _parse_date("2024-04-15") == date(2024, 4, 15)


def test_parse_date_empty():
    assert _parse_date("") is None


# --- Google Sheets integration tests (mocked) ---

_SAMPLE_RECORDS = [
    {
        "Run Date": "04/15/2024",
        "Account": "Brokerage",
        "Account Number": "Z12345678",
        "Action": "YOU BOUGHT VANGUARD 500 ETF (VOO)",
        "Symbol": "VOO",
        "Description": "VANGUARD S&P 500 ETF",
        "Type": "ETF",
        "Quantity": "0.482",
        "Price": "450.25",
        "Amount": "-216.92",
        "Commission": "0.00",
        "Fees": "0.00",
        "Settlement Date": "04/17/2024",
    },
    {
        "Run Date": "04/01/2024",
        "Account": "Brokerage",
        "Account Number": "Z12345678",
        "Action": "DIVIDEND RECEIVED",
        "Symbol": "",
        "Description": "CASH DIVIDEND",
        "Type": "Cash",
        "Quantity": "",
        "Price": "",
        "Amount": "25.00",
        "Commission": "",
        "Fees": "",
        "Settlement Date": "",
    },
    {
        "Run Date": "04/20/2024",
        "Account": "Brokerage",
        "Account Number": "Z12345678",
        "Action": "YOU SOLD APPLE INC (AAPL)",
        "Symbol": "AAPL",
        "Description": "APPLE INC",
        "Type": "Equity",
        "Quantity": "2",
        "Price": "185.50",
        "Amount": "371.00",
        "Commission": "0.00",
        "Fees": "0.00",
        "Settlement Date": "04/22/2024",
    },
]


def _make_mock_sheet(records: list[dict]) -> MagicMock:
    mock_ws = MagicMock()
    mock_ws.get_all_records.return_value = records
    mock_sheet = MagicMock()
    mock_sheet.worksheet.return_value = mock_ws
    return mock_sheet


def test_load_brokerage_sheet_returns_all_rows():
    with patch("pymoney.ingest.brokerage._get_sheet", return_value=_make_mock_sheet(_SAMPLE_RECORDS)):
        txs = load_brokerage_sheet()
    assert len(txs) == 3


def test_load_brokerage_sheet_action_type_buy():
    with patch("pymoney.ingest.brokerage._get_sheet", return_value=_make_mock_sheet([_SAMPLE_RECORDS[0]])):
        txs = load_brokerage_sheet()
    assert txs[0].action_type == "BUY"


def test_load_brokerage_sheet_fractional_quantity():
    with patch("pymoney.ingest.brokerage._get_sheet", return_value=_make_mock_sheet([_SAMPLE_RECORDS[0]])):
        txs = load_brokerage_sheet()
    assert txs[0].quantity == pytest.approx(0.482)


def test_load_brokerage_sheet_empty_symbol_imported():
    """Rows with empty Symbol (cash transactions) should be imported."""
    with patch("pymoney.ingest.brokerage._get_sheet", return_value=_make_mock_sheet([_SAMPLE_RECORDS[1]])):
        txs = load_brokerage_sheet()
    assert len(txs) == 1
    assert txs[0].symbol is None


def test_load_brokerage_sheet_empty_records():
    with patch("pymoney.ingest.brokerage._get_sheet", return_value=_make_mock_sheet([])):
        txs = load_brokerage_sheet()
    assert txs == []


def test_load_brokerage_sheet_skips_missing_run_date():
    records = [{"Run Date": "", "Action": "BUY", "Amount": "100"}]
    with patch("pymoney.ingest.brokerage._get_sheet", return_value=_make_mock_sheet(records)):
        txs = load_brokerage_sheet()
    assert txs == []


def test_load_brokerage_sheet_uses_env_tab_name(monkeypatch):
    monkeypatch.setenv("BROKERAGE_TAB_NAME", "My Brokerage Tab")
    mock_sheet = _make_mock_sheet([_SAMPLE_RECORDS[0]])
    with patch("pymoney.ingest.brokerage._get_sheet", return_value=mock_sheet):
        load_brokerage_sheet()
    mock_sheet.worksheet.assert_called_once_with("My Brokerage Tab")
