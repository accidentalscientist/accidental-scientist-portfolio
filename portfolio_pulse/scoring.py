"""Transparent account-health scoring for Portfolio Pulse.

There is one concept only: health. Low health means high risk. Every input
comes from the Snapshot or Timeline CSV and every deduction is explainable.
"""
from datetime import date

BANDS = [(50, "Critical"), (75, "Watch"), (100, "Healthy")]

SEGMENT_THRESHOLDS = {
    "Enterprise": {"qbr_clean": 90, "qbr_bad": 365, "tickets_clean": 4, "tickets_bad": 25},
    "Mid-Market": {"qbr_clean": 120, "qbr_bad": 365, "tickets_clean": 2, "tickets_bad": 18},
    "SMB": {"qbr_clean": 180, "qbr_bad": 540, "tickets_clean": 1, "tickets_bad": 12},
}
DEFAULT_SEGMENT = "Mid-Market"

QBR_MAX_PENALTY = 25
PAYMENT_OVERDUE_PENALTY = 20
TICKETS_MAX_PENALTY = 15
PRIORITY_AMPLIFICATION_MAX = 0.5
UTIL_CLEAN, UTIL_BAD, UTIL_MAX_PENALTY = 70, 20, 15
ACTIVE_CLEAN, ACTIVE_BAD, ACTIVE_MAX_PENALTY = 60, 15, 10
ONE_YEAR_TERM_PENALTY = 15
TWO_YEAR_RENEWAL_PENALTY = 6

SIGNAL_MAX_WEIGHTS = {
    "qbr": QBR_MAX_PENALTY,
    "payment": PAYMENT_OVERDUE_PENALTY,
    "tickets": TICKETS_MAX_PENALTY,
    "utilisation": UTIL_MAX_PENALTY,
    "active_user": ACTIVE_MAX_PENALTY,
    "contract_term": ONE_YEAR_TERM_PENALTY,
}

RENEWAL_IMMEDIATE_DAYS = 183
RENEWAL_PLANNING_DAYS = 548
RENEWAL_IMMEDIATE_MULTIPLIER = 1.25
RENEWAL_PLANNING_MULTIPLIER = 1.10

NEW_ACCOUNT_DAYS = 180
ESTABLISHED_ACCOUNT_DAYS = 365 * 3
NEW_ACCOUNT_MULTIPLIER = 1.15
ESTABLISHED_ACCOUNT_MULTIPLIER = 0.9

ARR_DECLINE_THRESHOLD_PCT = -5.0
ARR_GROWTH_THRESHOLD_PCT = 5.0
ARR_DECLINE_MULTIPLIER = 1.15
ARR_GROWTH_MULTIPLIER = 0.9


def _ramp_up(value, clean, bad, max_penalty):
    if value <= clean:
        return 0.0
    if value >= bad:
        return max_penalty
    return max_penalty * (value - clean) / (bad - clean)


def _ramp_down(value, bad, clean, max_penalty):
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
    """Return an account enriched with one 0-100 health score.

    A missing QBR is treated as "never happened": its effective age is the
    customer's full tenure. Completeness still records that the QBR date was
    absent, so inferred data never looks fully complete.
    """
    today = today or date.today()
    thresholds = SEGMENT_THRESHOLDS.get(
        account.get("segment"), SEGMENT_THRESHOLDS[DEFAULT_SEGMENT],
    )

    signals_present = 0
    deduction = 0.0
    drivers = []

    customer_since = account.get("customer_since")
    tenure_days = (today - customer_since).days if customer_since else None
    last_qbr_date = account.get("last_qbr_date")
    qbr_inferred = last_qbr_date is None
    if last_qbr_date:
        days_since_qbr = max(0, (today - last_qbr_date).days)
        signals_present += 1
    elif tenure_days is not None:
        days_since_qbr = max(0, tenure_days)
    else:
        days_since_qbr = None

    if days_since_qbr is not None:
        qbr_penalty = _ramp_up(
            days_since_qbr,
            thresholds["qbr_clean"],
            thresholds["qbr_bad"],
            QBR_MAX_PENALTY,
        )
        deduction += qbr_penalty
        if qbr_penalty:
            drivers.append({
                "signal": "No QBR recorded" if qbr_inferred else "QBR overdue",
                "penalty": round(qbr_penalty, 1),
            })

    overdue_flag = account.get("overdue_flag")
    if overdue_flag is not None:
        signals_present += 1
        if overdue_flag:
            deduction += PAYMENT_OVERDUE_PENALTY
            drivers.append({"signal": "Payment overdue", "penalty": PAYMENT_OVERDUE_PENALTY})

    tickets_12mo = account.get("tickets_12mo")
    if tickets_12mo is not None:
        signals_present += 1
        ticket_penalty = _ramp_up(
            tickets_12mo,
            thresholds["tickets_clean"],
            thresholds["tickets_bad"],
            TICKETS_MAX_PENALTY,
        )
        pct_high_priority = account.get("pct_high_priority")
        if pct_high_priority is not None:
            ticket_penalty *= 1 + (pct_high_priority / 100) * PRIORITY_AMPLIFICATION_MAX
        deduction += ticket_penalty
        if ticket_penalty:
            drivers.append({"signal": "Support load", "penalty": round(ticket_penalty, 1)})

    seat_utilisation_pct = account.get("seat_utilisation_pct")
    if seat_utilisation_pct is not None:
        signals_present += 1
        util_penalty = _ramp_down(
            seat_utilisation_pct, UTIL_BAD, UTIL_CLEAN, UTIL_MAX_PENALTY,
        )
        deduction += util_penalty
        if util_penalty:
            drivers.append({
                "signal": "Low seat utilisation", "penalty": round(util_penalty, 1),
            })

    active_user_pct = account.get("active_user_pct")
    if active_user_pct is not None:
        signals_present += 1
        active_penalty = _ramp_down(
            active_user_pct, ACTIVE_BAD, ACTIVE_CLEAN, ACTIVE_MAX_PENALTY,
        )
        deduction += active_penalty
        if active_penalty:
            drivers.append({
                "signal": "Low active-user rate", "penalty": round(active_penalty, 1),
            })

    term_length_months = account.get("term_length_months")
    if term_length_months is not None:
        signals_present += 1
        contract_start = account.get("contract_start")
        is_new_customer_term = bool(
            customer_since
            and contract_start
            and abs((contract_start - customer_since).days) <= 45
        )
        term_penalty = 0.0
        if term_length_months <= 12:
            term_penalty = ONE_YEAR_TERM_PENALTY
        elif term_length_months <= 24 and not is_new_customer_term:
            term_penalty = TWO_YEAR_RENEWAL_PENALTY
        deduction += term_penalty
        if term_penalty:
            drivers.append({
                "signal": f"{term_length_months}-month contract",
                "penalty": round(term_penalty, 1),
            })

    data_completeness = round(signals_present / len(SIGNAL_MAX_WEIGHTS) * 100, 1)

    renewal_date = account.get("renewal_date")
    days_to_renewal = (renewal_date - today).days if renewal_date else None
    if days_to_renewal is not None and days_to_renewal <= RENEWAL_IMMEDIATE_DAYS:
        renewal_mult = RENEWAL_IMMEDIATE_MULTIPLIER
    elif days_to_renewal is not None and days_to_renewal <= RENEWAL_PLANNING_DAYS:
        renewal_mult = RENEWAL_PLANNING_MULTIPLIER
    else:
        renewal_mult = 1.0

    if tenure_days is not None and tenure_days < NEW_ACCOUNT_DAYS:
        tenure_mult = NEW_ACCOUNT_MULTIPLIER
    elif tenure_days is not None and tenure_days > ESTABLISHED_ACCOUNT_DAYS:
        tenure_mult = ESTABLISHED_ACCOUNT_MULTIPLIER
    else:
        tenure_mult = 1.0

    arr_trend_pct = account.get("arr_trend_pct")
    if arr_trend_pct is not None and arr_trend_pct < ARR_DECLINE_THRESHOLD_PCT:
        arr_mult = ARR_DECLINE_MULTIPLIER
    elif arr_trend_pct is not None and arr_trend_pct > ARR_GROWTH_THRESHOLD_PCT:
        arr_mult = ARR_GROWTH_MULTIPLIER
    else:
        arr_mult = 1.0

    penalty = deduction * renewal_mult * tenure_mult * arr_mult
    score = round(max(0.0, min(100.0, 100 - penalty)), 1)
    drivers.sort(key=lambda item: item["penalty"], reverse=True)

    return {
        **account,
        "days_to_renewal": days_to_renewal,
        "days_since_qbr": days_since_qbr,
        "qbr_inferred": qbr_inferred,
        "tenure_days": tenure_days,
        "score": score,
        "band": _band(score),
        "data_completeness": data_completeness,
        "health_drivers": drivers,
    }


def score_portfolio(accounts, today=None):
    return [score_account(account, today) for account in accounts]


def portfolio_health(scored_accounts):
    if not scored_accounts:
        return {"weighted": 0.0, "unweighted": 0.0}

    unweighted = round(
        sum(account["score"] for account in scored_accounts) / len(scored_accounts), 1,
    )
    total_arr = sum(account.get("current_arr", 0.0) for account in scored_accounts)
    if total_arr:
        weighted = round(
            sum(
                account["score"] * account.get("current_arr", 0.0)
                for account in scored_accounts
            )
            / total_arr,
            1,
        )
    else:
        weighted = unweighted
    return {"weighted": weighted, "unweighted": unweighted}
