-- pymoney database schema
-- Canonical reference — mirrors db.py:init_schema()

-- ── Core spending transactions ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id                   VARCHAR PRIMARY KEY,
    date                 DATE NOT NULL,
    description          VARCHAR NOT NULL,   -- short description (from Tiller)
    full_description     VARCHAR,            -- long description (from Tiller)
    amount               DECIMAL(12,2) NOT NULL,  -- negative = debit, positive = credit
    category             VARCHAR,            -- assigned category name
    account              VARCHAR NOT NULL,   -- account name (e.g. "Chase Checking")
    account_number       VARCHAR,
    institution          VARCHAR,            -- institution name (e.g. "Chase")
    month                VARCHAR,            -- YYYY-MM, as supplied by Tiller
    week                 VARCHAR,            -- week label, as supplied by Tiller
    check_number         VARCHAR,
    date_added           DATE,               -- date the row was added to Tiller
    categorized_date     DATE,
    source               VARCHAR,            -- ingest source (e.g. "tiller")
    manually_overridden  BOOLEAN DEFAULT FALSE,  -- TRUE = set by hand, not rules
    proposed_category    VARCHAR             -- used during migration; dropped after
);

-- ── Daily account balances ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS account_balances (
    id             VARCHAR PRIMARY KEY,
    date           DATE NOT NULL,
    time           VARCHAR,
    institution    VARCHAR,
    account        VARCHAR NOT NULL,
    account_number VARCHAR,
    account_id     VARCHAR,
    balance        DECIMAL(12,2) NOT NULL
);

-- ── Fidelity investment transactions ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investment_transactions (
    id              VARCHAR PRIMARY KEY,
    run_date        DATE NOT NULL,
    account         VARCHAR,
    account_number  VARCHAR,
    action          VARCHAR NOT NULL,   -- e.g. "You Bought", "Dividend Received"
    action_type     VARCHAR,
    symbol          VARCHAR,
    description     VARCHAR,
    security_type   VARCHAR,
    quantity        DECIMAL(18,6),
    price           DECIMAL(18,6),
    amount          DECIMAL(12,2),
    commission      DECIMAL(12,2),
    fees            DECIMAL(12,2),
    settlement_date DATE
);

-- ── Net worth snapshots ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS net_worth_snapshots (
    id              VARCHAR PRIMARY KEY,
    snapshot_date   DATE NOT NULL,
    total_assets    DECIMAL(12,2),
    total_liabilities DECIMAL(12,2),
    net_worth       DECIMAL(12,2),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── Transaction labels ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transaction_labels (
    transaction_id VARCHAR NOT NULL,
    label          VARCHAR NOT NULL,
    PRIMARY KEY (transaction_id, label)
);

-- ── Account metadata ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS accounts (
    name    VARCHAR PRIMARY KEY,
    type    VARCHAR,   -- cash, holding, investment, retirement, credit
    class   VARCHAR    -- asset, liability
);

-- ── Category metadata ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS categories (
    name                VARCHAR PRIMARY KEY,
    group_name          VARCHAR,
    is_income           BOOLEAN DEFAULT FALSE,   -- counted as income in cash flow
    ignore              BOOLEAN DEFAULT FALSE,   -- excluded from income and expenses
    exclude_from_reports BOOLEAN DEFAULT FALSE
);

-- ── Monthly budget targets ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget (
    id        VARCHAR PRIMARY KEY,
    category  VARCHAR NOT NULL,
    month     VARCHAR NOT NULL,   -- YYYY-MM, or 'default' for the standing target
    amount    DECIMAL(12,2) NOT NULL
);
