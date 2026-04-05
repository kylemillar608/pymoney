# pymoney

Personal finance system built on DuckDB + Marimo. Ingests transactions from
[Tiller](https://www.tillerhq.com/) (Google Sheets) and investment activity
from Fidelity CSV exports, then surfaces spending, net worth, and investment
reports as reactive notebooks.

## Setup

```bash
# Install dependencies (requires Python 3.12+)
uv sync

# Configure environment
cp .env.example .env
# Edit .env — see "Configuration" below
```

## Data Sources

### Tiller (transactions & account balances)

Tiller syncs your bank/credit card data into a Google Sheet. pymoney reads
directly from that sheet via the Sheets API.

**One-time setup:**

1. Create a Google Cloud project and enable the Sheets API
2. Create a service account, download the JSON key
3. Share your Tiller spreadsheet with the service account email
4. Set in `.env`:
   ```
   GOOGLE_SERVICE_ACCOUNT_JSON=~/.config/pymoney/service_account.json
   TILLER_SPREADSHEET_ID=<id from the spreadsheet URL>
   ```

### Fidelity (investment transactions)

Paste your Fidelity CSV export into a dedicated tab in the same Google Spreadsheet
(default tab name: `Fidelity`). pymoney reads directly from that tab via the Sheets API.

The expected columns match the Fidelity CSV export format: Run Date, Account, Account
Number, Action, Symbol, Description, Type, Quantity, Price, Amount, Commission, Fees,
Settlement Date.

Set `FIDELITY_TAB_NAME` in `.env` if your tab has a different name.

### Coinbase (BTC trades) — coming soon

A `Coinbase` tab is reserved for future BTC trade history. Running
`pymoney ingest coinbase` will show a not-yet-implemented message until the column
format is finalized. Set `COINBASE_TAB_NAME` in `.env` to configure the tab name.

## Data Safety

pymoney reads sensitive financial data. These guardrails prevent it from being
committed to the repo:

- `.gitignore` blocks `*.csv`, `*.tsv`, `*.db`, `*.duckdb`, `*.json`, and `data/raw/`
- A pre-commit hook scans staged files for SSN patterns and 10+ digit account numbers

**After cloning, install the pre-commit hook:**

```bash
pymoney install-hooks
```

Never commit `.env`, `service_account.json`, or any data exports.

## Ingesting Data

```bash
# Pull everything (Tiller + Fidelity from Google Sheets)
pymoney ingest all

# Tiller only — optionally limit to recent data
pymoney ingest tiller
pymoney ingest tiller --since 2025-01-01

# Fidelity only (reads from Fidelity tab in Google Sheets)
pymoney ingest fidelity

# Re-run category rules on uncategorized transactions
pymoney categorize

# Check what's in the database
pymoney status
```

## Views

Notebooks are built with [Marimo](https://marimo.io/) — they're reactive Python
scripts, not `.ipynb` files.

```bash
# Monthly spending review (vs budget)
marimo run notebooks/monthly_review.py

# Drill down into a category or time range
marimo run notebooks/drilldown.py
```

To edit a notebook interactively:

```bash
marimo edit notebooks/monthly_review.py
```

## Configuration

| File | Purpose |
|------|---------|
| `config/categories.yaml` | Keyword rules for auto-categorizing transactions |
| `config/budget.yaml` | Monthly budget targets per category |
| `.env` | Secrets and paths (never commit this) |

The database is stored at `data/finance.db` by default (set `PYMONEY_DB_PATH`
in `.env` to change it).

## Development

```bash
uv run pytest
```
