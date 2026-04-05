#!/usr/bin/env bash
# pre-commit hook: block commits containing financial data files or patterns
# Install with: pymoney install-hooks

set -euo pipefail

FAILED=0
STAGED=$(git diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)

if [[ -z "$STAGED" ]]; then
    exit 0
fi

# 1. Block data files by path pattern
while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    case "$file" in
        data/raw/*)
            echo "BLOCKED: $file — raw data files must not be committed"
            FAILED=1
            ;;
        *.csv|*.tsv|*.xlsx)
            echo "BLOCKED: $file — spreadsheet/CSV files may contain financial data"
            FAILED=1
            ;;
        *.db|*.duckdb)
            echo "BLOCKED: $file — database files must not be committed"
            FAILED=1
            ;;
    esac
done <<< "$STAGED"

# 2. Scan staged additions for financial patterns (skip binary files)
while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    [[ ! -f "$file" ]] && continue

    # Skip known binary extensions
    case "$file" in
        *.png|*.jpg|*.jpeg|*.gif|*.ico|*.pdf|*.zip|*.tar|*.gz) continue ;;
    esac

    content=$(git diff --cached -- "$file" | grep "^+" | grep -v "^+++" 2>/dev/null || true)
    [[ -z "$content" ]] && continue

    # SSN pattern: ###-##-####
    if echo "$content" | grep -qP '\b\d{3}-\d{2}-\d{4}\b' 2>/dev/null; then
        echo "BLOCKED: $file — possible SSN pattern detected"
        FAILED=1
    fi

    # 10+ digit standalone numbers (account numbers)
    if echo "$content" | grep -qP '(?<!\d)\d{10,}(?!\d)' 2>/dev/null; then
        echo "BLOCKED: $file — possible account number (10+ digits) detected"
        FAILED=1
    fi

done <<< "$STAGED"

if [[ $FAILED -eq 1 ]]; then
    echo ""
    echo "pymoney pre-commit hook: commit blocked to prevent financial data leaks."
    echo "Remove the flagged files/content and try again."
    echo "To install this hook in a fresh clone: pymoney install-hooks"
    exit 1
fi

exit 0
