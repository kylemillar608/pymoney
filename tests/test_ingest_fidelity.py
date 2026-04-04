"""Tests for Fidelity CSV ingest."""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

import pytest

from pymoney.ingest.fidelity import (
    FidelityTransaction,
    _parse_action_type,
    _parse_decimal,
    _parse_date,
    load_fidelity_csv,
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
    from datetime import date
    assert _parse_date("04/15/2024") == date(2024, 4, 15)


def test_parse_date_iso():
    from datetime import date
    assert _parse_date("2024-04-15") == date(2024, 4, 15)


def test_parse_date_empty():
    assert _parse_date("") is None


# --- CSV parsing tests ---

_CSV_HEADER = (
    "Run Date,Account,Account Number,Action,Symbol,Description,Type,"
    "Exchange Quantity,Exchange Currency,Currency,Price,Quantity,"
    "Exchange Rate,Commission,Fees,Accrued Interest,Amount,Settlement Date"
)

_SAMPLE_ROWS = [
    # BUY with fractional quantity
    "04/15/2024,Brokerage,Z12345678,YOU BOUGHT VANGUARD 500 ETF (VOO),VOO,"
    "VANGUARD S&P 500 ETF,ETF,,,,450.25,0.482,,0.00,0.00,,−216.92,04/17/2024",
    # DIVIDEND with empty symbol (cash transaction)
    "04/01/2024,Brokerage,Z12345678,DIVIDEND RECEIVED,,"
    "CASH DIVIDEND,Cash,,,,,,,,,, 25.00,",
    # SELL
    "04/20/2024,Brokerage,Z12345678,YOU SOLD APPLE INC (AAPL),AAPL,"
    "APPLE INC,Equity,,,,185.50,2,,0.00,0.00,,371.00,04/22/2024",
]


def _make_csv(rows: list[str], with_metadata: bool = False) -> str:
    lines = []
    if with_metadata:
        lines += [
            "FID-NET-BENEFIT",
            "",
            "Account Number: Z12345678",
            "",
        ]
    lines.append(_CSV_HEADER)
    lines.extend(rows)
    return "\n".join(lines)


def _write_temp_csv(content: str) -> Path:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


def test_load_simple_csv():
    """Parses standard CSV without metadata rows."""
    path = _write_temp_csv(_make_csv(_SAMPLE_ROWS))
    txs = load_fidelity_csv(path)
    assert len(txs) == 3


def test_load_csv_with_metadata_header():
    """Finds header row even when CSV has leading metadata lines."""
    path = _write_temp_csv(_make_csv(_SAMPLE_ROWS, with_metadata=True))
    txs = load_fidelity_csv(path)
    assert len(txs) == 3


def test_action_type_parsed_on_buy():
    path = _write_temp_csv(_make_csv([_SAMPLE_ROWS[0]]))
    txs = load_fidelity_csv(path)
    assert txs[0].action_type == "BUY"


def test_fractional_quantity():
    path = _write_temp_csv(_make_csv([_SAMPLE_ROWS[0]]))
    txs = load_fidelity_csv(path)
    assert txs[0].quantity == pytest.approx(0.482)


def test_empty_symbol_row_imported():
    """Rows with empty Symbol (cash transactions) should be imported."""
    path = _write_temp_csv(_make_csv([_SAMPLE_ROWS[1]]))
    txs = load_fidelity_csv(path)
    assert len(txs) == 1
    assert txs[0].symbol is None


def test_empty_csv_body():
    """CSV with no data rows returns empty list."""
    path = _write_temp_csv(_CSV_HEADER + "\n")
    txs = load_fidelity_csv(path)
    assert txs == []
