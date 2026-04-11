# pymoney

Most personal finance tools give you charts you don't need and bury the numbers
you actually care about. pymoney is the opposite: a lean, local system that pulls
your real transaction data, runs it through rules you control, and surfaces the
handful of metrics worth paying attention to each month.

**Key properties:**

- **Accurate by default.** Income, expenses, and transfers are classified by
  category type — not just the sign of the transaction. Zelle rent splits
  reduce your expenses rather than inflate income. Payroll and equity are
  your actual income, not just any positive number that came through.
- **Fully customizable.** Categories, rules, and budget targets live in YAML
  files you own. Adjust a few lines and your reports immediately reflect your
  actual financial picture.
- **AI-friendly.** Because data stays local in a DuckDB file and notebooks
  are plain Python scripts, you can paste queries or notebook cells directly
  into a conversation with an AI and get real analysis — no upload, no
  privacy risk.
- **Minimal surface area.** A handful of CLI commands to ingest and inspect,
  one reactive notebook per view. Nothing to maintain beyond keeping your
  data sources in sync.

## Tech Stack

| Layer | Tool |
|-------|------|
| Database | [DuckDB](https://duckdb.org/) — fast, embedded, zero-dependency |
| Notebooks | [Marimo](https://marimo.io/) — reactive Python notebooks (plain `.py` files, version-control friendly) |
| Charts | [Plotly](https://plotly.com/python/) — interactive, in-browser |
| Data sources | [gspread](https://github.com/burnash/gspread) — reads directly from Google Sheets via the Sheets API |
| CLI | [Click](https://click.palletsprojects.com/) |
| Package manager | [uv](https://github.com/astral-sh/uv) |

All data stays local. Nothing is sent to a third-party service.

---

## Setup

### 1. Install dependencies

Requires Python 3.12+.

```bash
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — see the full reference in the **Configuration** section below.

### 3. Install the pre-commit hook

This blocks financial data from being accidentally committed.

```bash
uv run pymoney install-hooks
```

### 4. Connect Google Sheets

pymoney reads all data (transactions, balances, investment activity) from tabs
in a single Google Spreadsheet. One-time setup:

1. Create a [Google Cloud project](https://console.cloud.google.com/) and enable the **Google Sheets API**
2. Create a **service account**, assign it **Viewer** role, and download the JSON key
3. Share your spreadsheet with the service account email address
4. Set the following in `.env`:
   ```
   GOOGLE_SERVICE_ACCOUNT_JSON=~/.config/pymoney/service_account.json
   TILLER_SPREADSHEET_ID=<id from the spreadsheet URL>
   ```

---

## Data Sources

### Tiller (transactions & account balances)

[Tiller](https://www.tillerhq.com/) syncs your bank and credit card data into a
Google Sheet automatically. pymoney reads the `Transactions` and `Balance History`
tabs directly via the Sheets API — no CSV exports needed.

### Fidelity (investment transactions)

Paste your Fidelity CSV export into a dedicated tab in the same spreadsheet
(default tab name: `Fidelity`). The expected columns match Fidelity's standard
CSV export format: Run Date, Account, Account Number, Action, Symbol, Description,
Type, Quantity, Price, Amount, Commission, Fees, Settlement Date.

Set `FIDELITY_TAB_NAME` in `.env` if your tab has a different name.

### Coinbase (BTC trades) — coming soon

A `Coinbase` tab is reserved for future BTC trade history. Set `COINBASE_TAB_NAME`
in `.env` to configure the tab name.

---

## Commands

```bash
# Pull everything (Tiller + Fidelity)
uv run pymoney ingest all

# Tiller only — optionally limit to recent data
uv run pymoney ingest tiller
uv run pymoney ingest tiller --since 2025-01-01

# Fidelity only
uv run pymoney ingest fidelity

# Categorize: uncategorized only (default) or re-run on everything
uv run pymoney categorize
uv run pymoney categorize --all

# Show database stats (transaction count, date range, uncategorized count)
uv run pymoney status
```

### Transaction Review

```bash
# How many uncategorized? What are the top descriptions?
uv run pymoney tx summary

# Interactive review — work through each uncategorized description group
uv run pymoney tx review
```

In `tx review`, for each description group you can:
- Pick a category by number or partial name (one-off assignment)
- Press `r` to print a YAML rule snippet you can paste into `categories.yaml`
- Press `s` to skip, `q` to quit and save progress

### Categorization Migration

Use this workflow when switching from Tiller-assigned categories to pymoney rules:

```bash
# 1. Run rules into proposed_category (doesn't touch existing categories)
uv run pymoney migrate prepare

# 2. Review what would change
uv run pymoney migrate diff
uv run pymoney migrate diff --limit 100

# 3. Dry-run to see the scope
uv run pymoney migrate apply --dry-run

# 4. Commit the new categories
uv run pymoney migrate apply

# 5. Clean up the temporary column
uv run pymoney migrate clean
```

---

## Notebooks

```bash
# Monthly overview: cash flow, aggregate stats, category spotlight
uv run marimo run notebooks/monthly_review.py
```

To edit a notebook interactively:

```bash
uv run marimo edit notebooks/monthly_review.py
```

Notebooks are plain `.py` files — they diff cleanly and work well with version
control and AI tools.

---

## Configuration

### `config/categories.yaml`

Defines categories, their group, and keyword/regex rules for auto-classification.
Each category can carry flags that control how it appears in reports:

| Flag | Effect |
|------|--------|
| `is_income: true` | Counted as income in cash flow reports |
| `is_transfer: true` | Excluded from both income and expenses |
| `hide_from_budget: true` | Hidden from budget variance reports |

**Example:**

```yaml
categories:
  - name: Paycheck
    group: Income
    is_income: true
    rules:
      - regex: "PAYROLL|DIRECT DEPOSIT|SALARY"

  - name: CC Payment
    group: Transfers
    is_transfer: true
    hide_from_budget: true
```

Add your own categories, adjust the rules, and re-run `pymoney categorize` to
reclassify existing transactions.

### `config/budget.yaml`

Monthly budget targets per category. Used by the spotlight report to flag
categories that are consistently over or under budget.

### `.env`

| Variable | Description |
|----------|-------------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to service account key file |
| `TILLER_SPREADSHEET_ID` | Google Sheets spreadsheet ID |
| `FIDELITY_TAB_NAME` | Tab name for Fidelity data (default: `Fidelity`) |
| `COINBASE_TAB_NAME` | Tab name for Coinbase data (default: `Coinbase`) |
| `TILLER_IMPORT_CATEGORIES` | Set to `false` to ignore Tiller's categories on ingest (default: `true`) |
| `PYMONEY_DB_PATH` | Path to DuckDB file (default: `data/finance.db`) |

---

## Data Safety

pymoney reads sensitive financial data. These guardrails keep it out of the repo:

- `.gitignore` blocks `*.csv`, `*.tsv`, `*.db`, `*.duckdb`, `*.json`, and `data/raw/`
- The pre-commit hook scans staged files for SSN patterns and 10+ digit account numbers

Never commit `.env`, `service_account.json`, or any data exports.
