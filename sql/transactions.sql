-- Transactions — most recent first
-- Run with: duckdb data/finance.db < sql/transactions.sql

SELECT
    t.date,
    t.description,
    t.amount,
    t.category,
    t.account,
    t.institution
FROM transactions t
ORDER BY t.date DESC, t.id DESC;
