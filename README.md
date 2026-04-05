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

Export activity CSVs from Fidelity's website and drop them in `data/raw/`.
pymoney picks up any `*.csv` in that directory automatically.

## Ingesting Data

```bash
# Pull everything (Tiller + all Fidelity CSVs in data/raw/)
pymoney ingest all

# Tiller only — optionally limit to recent data
pymoney ingest tiller
pymoney ingest tiller --since 2025-01-01

# Fidelity only — specific files or all of data/raw/
pymoney ingest fidelity
pymoney ingest fidelity data/raw/History_for_Account_1234.csv

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
