"""DuckDB connection and schema initialization."""

import os
from pathlib import Path

import duckdb
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))

_DEFAULT_DB_PATH = str(Path(__file__).parent.parent / "data" / "finance.db")


def get_connection(db_path: str | None = None) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection, creating the schema if needed."""
    path = db_path or os.getenv("PYMONEY_DB_PATH", _DEFAULT_DB_PATH)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(path)
    init_schema(conn)
    return conn


def get_in_memory_connection() -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection with schema initialized."""
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    return conn


def init_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables if they don't exist. Idempotent."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id VARCHAR PRIMARY KEY,
            date DATE NOT NULL,
            description VARCHAR NOT NULL,
            full_description VARCHAR,
            amount DECIMAL(12,2) NOT NULL,
            category VARCHAR,
            account VARCHAR NOT NULL,
            account_number VARCHAR,
            institution VARCHAR,
            month VARCHAR,
            week VARCHAR,
            check_number VARCHAR,
            date_added DATE,
            categorized_date DATE,
            source VARCHAR,
            manually_overridden BOOLEAN DEFAULT FALSE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS account_balances (
            id VARCHAR PRIMARY KEY,
            date DATE NOT NULL,
            time VARCHAR,
            institution VARCHAR,
            account VARCHAR NOT NULL,
            account_number VARCHAR,
            account_id VARCHAR,
            balance DECIMAL(12,2) NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS investment_transactions (
            id VARCHAR PRIMARY KEY,
            run_date DATE NOT NULL,
            account VARCHAR,
            account_number VARCHAR,
            action VARCHAR NOT NULL,
            action_type VARCHAR,
            symbol VARCHAR,
            description VARCHAR,
            security_type VARCHAR,
            quantity DECIMAL(18,6),
            price DECIMAL(18,6),
            amount DECIMAL(12,2),
            commission DECIMAL(12,2),
            fees DECIMAL(12,2),
            settlement_date DATE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS net_worth_snapshots (
            id VARCHAR PRIMARY KEY,
            snapshot_date DATE NOT NULL,
            total_assets DECIMAL(12,2),
            total_liabilities DECIMAL(12,2),
            net_worth DECIMAL(12,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS transaction_labels (
            transaction_id VARCHAR NOT NULL,
            label          VARCHAR NOT NULL,
            PRIMARY KEY (transaction_id, label)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            name    VARCHAR PRIMARY KEY,
            type    VARCHAR,   -- cash, holding, investment, retirement, credit
            class   VARCHAR    -- asset, liability
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name VARCHAR PRIMARY KEY,
            group_name VARCHAR,
            is_income BOOLEAN DEFAULT FALSE,
            ignore BOOLEAN DEFAULT FALSE,
            exclude_from_reports BOOLEAN DEFAULT FALSE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget (
            id VARCHAR PRIMARY KEY,
            category VARCHAR NOT NULL,
            month VARCHAR NOT NULL,
            amount DECIMAL(12,2) NOT NULL
        )
    """)
