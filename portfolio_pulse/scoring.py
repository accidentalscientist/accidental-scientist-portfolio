"""
Portfolio Pulse scoring engine — v2.

Every input is objective — a number or date pulled straight from a
billing/CRM export (or, for `momentum_ratio`, computed upstream by
metrics.py). There is no manual "CSM says it's red" field: the health
score is always derived from the data itself.

Continuous ramps replace v1's step buckets so an account at 89 vs 91 days
differs by ~1 point, not a whole band. Missing optional signals contribute
zero deduction — never a penalty — and are tracked via `data_completeness`
so a data-poor score is understood in context rather than taken at face
value.
"""
from datetime import date

# ── Health/risk bands (0-100) — 3 tiers, kept simple by design ───────
BANDS = [(50, "Critical"), (75, "At-risk"), (100, "Healthy")]

# ── Per-signal ramp thresholds and max deduction weight ─────────────
# Each signal's max deduction is sized so a worst-case, fully-present
# account bottoms out near 0 — the pool sums to 100.
SEGMENT_THRESHOLDS = {
    "Enterprise": {"contact_clean": 60, "contact_bad": 365, "tickets_clean": 4, "tickets_bad": 25},
    "Mid-Market": {"contact_clean": 45, "contact_bad": 270, "tickets_clean": 2, "tickets_bad": 18},
    "SMB":        {"contact_clean": 30, "contact_bad": 180, "tickets_clean": 1, "tickets_bad": 12},
}
DEFAULT_SEGMENT = "Mid-Market"

CONTACT_MAX_PENALTY = 30
PAYMENT_OVERDUE_PENALTY = 25  # flat: overdue_flag is boolean, no magnitude to ramp over
TICKETS_MAX_PENALTY = 20
PRIORITY_AMPLIFICATION_MAX = 0.5  # tickets penalty can be amplified up to +50% by pct_high_priority
UTIL_CLEAN, UTIL_BAD, UTIL_MAX_PENALTY = 70, 20, 15
ACTIVE_CLEAN, ACTIVE_BAD, ACTIVE_MAX_PENALTY = 60, 15, 10

SIGNAL_MAX_WEIGHTS = {
    "contact": CONTACT_MAX_PENALTY,
    "payment": PAYMENT_OVERDUE_PENALTY,
    "tickets": TICKETS_MAX_PENALTY,
    "utilisation": UTIL_MAX_PENALTY,
    "active_user": ACTIVE_MAX_PENALTY,
}

# ── Multipliers, applied to the combined base deduction ─────────────
RENEWAL_WINDOW_DAYS = 90
RENEWAL_MULTIPLIER = 1.25

NEW_ACCOUNT_DAYS = 180
ESTABLISHED_ACCOUNT_DAYS = 365 * 3
NEW_ACCOUNT_MULTIPLIER = 1.15
ESTABLISHED_ACCOUNT_MULTIPLIER = 0.9

MOMENTUM_DECLINE_THRESHOLD = 0.95
MOMENTUM_GROWTH_THRESHOLD = 1.05
MOMENTUM_DECLINE_MULTIPLIER = 1.15
MOMENTUM_GROWTH_MULTIPLIER = 0.9


def _ramp_up(value, clean, bad, max_penalty):
    """0 at/below `clean`, `max_penalty` at/above `bad`, linear between."""
    if value <= clean:
        return 0.0
    if value >= bad:
        return max_penalty
    return max_penalty * (value - clean) / (bad - clean)


def _ramp_down(value, bad, clean, max_penalty):
    """`max_penalty` at/below `bad`, 0 at/above `clean` — for signals where low is bad."""
    if value >= clean:
        return 0.0
    if value <= bad:
        return max_penalty
    return max_penalty * (clean - value) / (clean - bad)


def _band(score):
    for upper, label in BANDS:
        if score <= upper:
            return label
    return BANDS[-1][1]


def score_account(account, today=None):
    """Compute the 0-100 health score, band, and data_completeness for one account.

    `account` is a dict from parsing.py, optionally already carrying a
    `momentum_ratio` key attached upstream by metrics.py.
    """
    today = today or date.today()
    thresholds = SEGMENT_THRESHOLDS.get(account.get("segment"), SEGMENT_THRESHOLDS[DEFAULT_SEGMENT])

    signals_present = 0
    deduction = 0.0

    days_since_contact = account.get("days_since_contact")
    if days_since_contact is not None:
        signals_present += 1
        deduction += _ramp_up(days_since_contact, thresholds["contact_clean"], thresholds["contact_bad"], CONTACT_MAX_PENALTY)

    overdue_flag = account.get("overdue_flag")
    if overdue_flag is not None:
        signals_present += 1
        if overdue_flag:
            deduction += PAYMENT_OVERDUE_PENALTY

    tickets_12mo = account.get("tickets_12mo")
    if tickets_12mo is not None:
        signals_present += 1
        ticket_ded = _ramp_up(tickets_12mo, thresholds["tickets_clean"], thresholds["tickets_bad"], TICKETS_MAX_PENALTY)
        pct_high_priority = account.get("pct_high_priority")
        if pct_high_priority is not None:
            ticket_ded *= 1 + (pct_high_priority / 100) * PRIORITY_AMPLIFICATION_MAX
        deduction += ticket_ded

    seat_utilisation_pct = account.get("seat_utilisation_pct")
    if seat_utilisation_pct is not None:
        signals_present += 1
        deduction += _ramp_down(seat_utilisation_pct, UTIL_BAD, UTIL_CLEAN, UTIL_MAX_PENALTY)

    active_user_pct = account.get("active_user_pct")
    if active_user_pct is not None:
        signals_present += 1
        deduction += _ramp_down(active_user_pct, ACTIVE_BAD, ACTIVE_CLEAN, ACTIVE_MAX_PENALTY)

    data_completeness = round(signals_present / len(SIGNAL_MAX_WEIGHTS) * 100, 1)

    # ── Multipliers ──
    renewal_date = account.get("renewal_date")
    days_to_renewal = (renewal_date - today).days if renewal_date else None
    renewal_mult = RENEWAL_MULTIPLIER if (days_to_renewal is not None and 0 <= days_to_renewal <= RENEWAL_WINDOW_DAYS) else 1.0

    customer_since = account.get("customer_since")
    tenure_days = (today - customer_since).days if customer_since else None
    if tenure_days is not None and tenure_days < NEW_ACCOUNT_DAYS:
        tenure_mult = NEW_ACCOUNT_MULTIPLIER
    elif tenure_days is not None and tenure_days > ESTABLISHED_ACCOUNT_DAYS:
        tenure_mult = ESTABLISHED_ACCOUNT_MULTIPLIER
    else:
        tenure_mult = 1.0

    momentum_ratio = account.get("momentum_ratio")
    if momentum_ratio is not None and momentum_ratio < MOMENTUM_DECLINE_THRESHOLD:
        momentum_mult = MOMENTUM_DECLINE_MULTIPLIER
    elif momentum_ratio is not None and momentum_ratio > MOMENTUM_GROWTH_THRESHOLD:
        momentum_mult = MOMENTUM_GROWTH_MULTIPLIER
    else:
        momentum_mult = 1.0

    # Risk = the raw signal read, before any timing/context adjustment.
    risk_score = round(min(100.0, deduction), 1)

    penalty = deduction * renewal_mult * tenure_mult * momentum_mult
    score = round(max(0.0, min(100.0, 100 - penalty)), 1)

    return {
        **account,
        "days_to_renewal": days_to_renewal,
        "tenure_days": tenure_days,
        "score": score,
        "band": _band(score),
        "risk_score": risk_score,
        "risk_band": _band(max(0.0, 100 - risk_score)),
        "data_completeness": data_completeness,
    }


def score_portfolio(accounts, today=None):
    return [score_account(a, today) for a in accounts]


def portfolio_health(scored_accounts):
    """ARR-weighted and unweighted (logo) portfolio health averages.

    The gap between the two is itself informative — a wide gap means a few
    large accounts are propping up (or dragging down) a headline number
    that doesn't reflect the typical account.
    """
    if not scored_accounts:
        return {"weighted": 0.0, "unweighted": 0.0}

    unweighted = round(sum(a["score"] for a in scored_accounts) / len(scored_accounts), 1)

    total_arr = sum(a.get("current_arr", 0.0) for a in scored_accounts)
    if total_arr:
        weighted = round(sum(a["score"] * a.get("current_arr", 0.0) for a in scored_accounts) / total_arr, 1)
    else:
        weighted = unweighted

    return {"weighted": weighted, "unweighted": unweighted}
