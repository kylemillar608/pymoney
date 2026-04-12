"""Recurring payment tracker.

Detects active recurring payments by querying transactions tagged with the
'is_recurring' label, grouped by category (each recurring item has its own
category). Cadence is inferred from the median inter-payment interval after
filtering out micro-intervals (<4 days) that represent adjustments or
duplicate charges rather than real payment cycles.
"""

from __future__ import annotations

from datetime import date
from statistics import median
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import duckdb

# (max_days, label, cadence_days, monthly_divisor)
_CADENCE_BUCKETS = [
    (10,  "weekly",      7,   30 / 7),
    (21,  "biweekly",    14,  30 / 14),
    (45,  "monthly",     30,  1),
    (120, "quarterly",   91,  3),
    (270, "semi-annual", 182, 6),
    (999, "annual",      365, 12),
]


def _infer_cadence(intervals_days: list[float]) -> tuple[str, int]:
    """Return (label, cadence_days) from a list of inter-payment intervals.

    Micro-intervals (<4 days) are dropped before computing the median so that
    same-day adjustments and near-duplicate charges don't corrupt the result.
    Falls back to the raw list if filtering would leave nothing.
    """
    filtered = [iv for iv in intervals_days if iv >= 4]
    med = median(filtered if filtered else intervals_days)
    for max_days, label, cadence_days, _ in _CADENCE_BUCKETS:
        if med <= max_days:
            return label, cadence_days
    return "annual", 365


def _monthly_equivalent(amount: float, cadence_label: str) -> float:
    for _, label, _, divisor in _CADENCE_BUCKETS:
        if label == cadence_label:
            return amount / divisor
    return amount


def get_subscriptions(conn: duckdb.DuckDBPyConnection) -> list[dict]:
    """
    Detect active subscriptions from Subscriptions-categorized transactions.

    Groups by description, infers cadence from median payment interval,
    and filters to subscriptions whose last payment is recent enough to
    still be considered active (last_paid + cadence * 1.5 >= today).

    Returns list of dicts sorted by next_expected date.
    """
    rows = conn.execute("""
        SELECT t.category, t.date, ABS(t.amount) AS amount
        FROM transactions t
        JOIN transaction_labels tl ON tl.transaction_id = t.id AND tl.label = 'is_recurring'
        WHERE t.amount < 0
          AND t.category IS NOT NULL AND t.category != ''
        ORDER BY t.category, t.date
    """).fetchall()

    # Group by category — each recurring subscription has its own category
    groups: dict[str, list[tuple[date, float]]] = {}
    for cat, dt, amt in rows:
        groups.setdefault(cat, []).append((dt, amt))

    today = date.today()
    results = []

    for canonical, payments in groups.items():  # canonical = category name
        payments.sort(key=lambda x: x[0])
        dates = [p[0] for p in payments]
        amounts = [p[1] for p in payments]

        last_paid = dates[-1]
        last_amount = amounts[-1]
        avg_amount = sum(amounts) / len(amounts)
        payment_count = len(payments)

        if payment_count == 1:
            cadence_label = "monthly"
            cadence_days = 30
            cadence_estimated = True
        else:
            intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
            cadence_label, cadence_days = _infer_cadence(intervals)
            cadence_estimated = False

        # Active check: last payment within 1.5× cadence.
        # For estimated cadence (single payment), use a fixed 60-day window —
        # enough to catch new subscriptions, but filters out old one-off charges.
        days_since = (today - last_paid).days
        cutoff = 60 if cadence_estimated else cadence_days * 1.5
        if days_since > cutoff:
            continue

        next_expected = date.fromordinal(last_paid.toordinal() + cadence_days)
        monthly_eq = _monthly_equivalent(float(avg_amount), cadence_label)

        results.append({
            "name": canonical,
            "cadence": cadence_label,
            "cadence_estimated": cadence_estimated,
            "last_paid": last_paid,
            "last_amount": last_amount,
            "avg_amount": avg_amount,
            "next_expected": next_expected,
            "monthly_equivalent": monthly_eq,
            "payment_count": payment_count,
        })

    results.sort(key=lambda r: r["next_expected"])
    return results
