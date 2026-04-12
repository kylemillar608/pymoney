# pymoney

pymoney is a local-first personal finance system built to be owned, not just used.
Your data lives in a local DuckDB file. Your rules live in YAML. Every report is
a plain Python notebook. Nothing is hidden, nothing is magic — and everything is
editable.

The whole thing was built in a weekend using [Gastown](https://github.com/gastown-dev/gastown),
an AI-native dev framework. That's not a footnote — it's the point. pymoney is
designed from the ground up to be understandable and modifiable by AI, which
makes it a fundamentally different kind of personal finance tool.

### The real unlock is Claude

Because every piece of pymoney is plain text — Python notebooks, YAML configs,
SQL queries, a CLI with human-readable commands — Claude can read, write, and
reason about all of it. That changes what it means to "use" this software:

- **You don't need to read these docs.** Fork the repo and open a Claude Code
  session. Ask it to onboard you. It will read the codebase, walk you through
  setup, explain any part of the system, and get you running — no manual required.
- **Ask about your finances in plain English.** With your data in a local DB,
  you can ask Claude things like *"what did I spend the most on two months ago,
  excluding recurring payments?"* and get a real answer backed by actual SQL
  against your actual transactions. No dashboards, no CSV exports, no privacy
  trade-off.
- **Build whatever you want.** The YAML configs expose categories, labels,
  budgets, and account metadata. But the notebooks and CLI are raw Python —
  there's no ceiling. Ask Claude to add a custom report, wire up a new metric,
  or build something the configs don't expose yet. The whole codebase is fair
  game.

### Key properties

- **Rule-based and accurate.** Categories are defined by rules you write, not a
  black-box model. Income, expenses, and transfers are classified by type — so
  your numbers reflect reality, not just the sign of a transaction.
- **SQL-native.** Everything lives in DuckDB — a full SQL engine embedded in a
  single local file. Query your finances directly, join across tables, or drop
  into a Marimo SQL cell in the notebook. No ORM, no abstraction layer.
- **Beautiful, reactive interface.** Reports are [Marimo](https://marimo.io/)
  notebooks: interactive filters, live charts, and a clean UI — without the
  overhead of a web app. Notebooks are plain `.py` files, so they diff cleanly,
  work with version control, and Claude can edit them directly.
- **Intuitive CLI.** A small set of composable commands (`ingest`, `categorize`,
  `label`, `apply`, `sync`, `tx review`) cover the full workflow with no
  surprises. `--dry-run` and `--all` flags work consistently across commands.
- **Easy migration from Tiller.** Already using Tiller? There's a built-in
  migration workflow that runs your new rules into a staging column, shows you
  a side-by-side diff of what would change, and lets you commit when you're
  happy — without touching your existing categories until you're ready.
- **Private by default.** Your data never leaves your machine. No accounts,
  no sync, no cloud. The pre-commit hook and `.gitignore` rules make it hard
  to accidentally push financial data even if you're not thinking about it.

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

# Show database stats (transaction count, date range, uncategorized count)
uv run pymoney status
```

### Categorization

```bash
# Categorize only uncategorized transactions
uv run pymoney categorize

# Re-run rules on all transactions (shows preview + confirmation prompt)
uv run pymoney categorize --all

# Preview what would change without applying
uv run pymoney categorize --dry-run
uv run pymoney categorize --all --dry-run
```

### Labeling

Labels are strings applied to transactions independently of categories. Unlike
categories (first-match), every matching label rule is applied — a transaction
can carry multiple labels.

```bash
# Apply labels to transactions that don't have any yet
uv run pymoney label

# Re-run label rules on all transactions (shows preview + confirmation prompt)
uv run pymoney label --all

# Preview what would change without applying
uv run pymoney label --dry-run
uv run pymoney label --all --dry-run
```

### Categorize + Label Together

```bash
# Run both in one shot
uv run pymoney apply
uv run pymoney apply --all
uv run pymoney apply --all --dry-run
```

### Sync Config

Pushes category metadata, account metadata, and budget targets from YAML into
the database. Run this after editing any config file.

```bash
uv run pymoney sync
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

After assigning a category, you'll also be prompted to add or confirm labels for
that description.

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
# Monthly overview: balances, net worth, cash flow, category spotlight,
# recurring payments tracker, and transaction viewer
uv run marimo run notebooks/monthly_review.py

# Raw transaction drilldown
uv run marimo run notebooks/drilldown.py
```

To edit a notebook interactively:

```bash
uv run marimo edit notebooks/monthly_review.py
```

Notebooks are plain `.py` files — they diff cleanly and work well with version
control and AI tools.

---

## Configuration

All config files are personal and not committed to the repo. Copy from the
examples to get started:

```bash
cp config/categories.example.yaml config/categories.yaml
cp config/budget.example.yaml config/budget.yaml
```

### `config/categories.yaml`

Defines categories, their group, and keyword/regex rules for auto-classification.

| Flag | Effect |
|------|--------|
| `is_income: true` | Counted as income in cash flow reports |
| `ignore: true` | Excluded from income, expense, and budget reports (transfers, investments) |

**Example:**

```yaml
categories:
  - name: Paycheck
    group: Primary Income
    is_income: true
    rules:
      - contains: "Google Llc Payroll"

  - name: Groceries
    group: Mandatory
    rules:
      - contains:
          - "Whole Foods"
          - "Trader Joe"
      - regex: '^Instacart'

  - name: Apple TV
    group: Discretionary
    rules:
      - all_of:
          - contains: "Apple.com/bill"
          - amount_gte: 9.99
          - amount_lte: 9.99

  - name: CC Payment
    group: Transfer
    ignore: true
    rules:
      - contains: "Autopay"
```

**Rule types:**

| Key | Matches when |
|-----|-------------|
| `contains: "text"` | Description contains text (case-insensitive) |
| `contains: [list]` | Description contains any item in the list |
| `regex: 'pattern'` | Description matches regex pattern |
| `account: "name"` | Account name contains value |
| `institution: "name"` | Institution name contains value |
| `amount_gte: N` | Absolute transaction amount ≥ N |
| `amount_lte: N` | Absolute transaction amount ≤ N |
| `all_of: [...]` | All sub-rules match (AND compound) |

Top-level rules within a category are OR'd. Run `pymoney categorize` after editing.

### `config/labels.yaml`

Defines string labels applied to transactions. Unlike categories, all matching
labels are applied (not just the first). Labels can match on `category` in
addition to all the rule types above.

The built-in `is_recurring` label drives the Recurring Payments tracker in the
monthly review notebook.

**Example:**

```yaml
labels:
  - label: is_recurring
    rules:
      - category: "Rent"
      - category: "Netflix"
      - category: "Internet"
```

Run `pymoney label --all` after editing.

### `config/accounts.yaml`

Maps account names to display metadata used in the balance tiles.

| Field | Values |
|-------|--------|
| `type` | `cash`, `holding`, `investment`, `retirement`, `credit` |
| `class` | `asset`, `liability` |

**Example:**

```yaml
accounts:
  - name: Checking
    type: cash
    class: asset
  - name: Freedom Unlimited
    type: credit
    class: liability
```

Run `pymoney sync` after editing.

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
- `.gitignore` also blocks all personal config files (`categories.yaml`, `labels.yaml`, `accounts.yaml`, `budget.yaml`)
- The pre-commit hook scans staged files for SSN patterns and 10+ digit account numbers

Never commit `.env`, `service_account.json`, or any data exports.
