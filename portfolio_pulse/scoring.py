"""Transparent account-health scoring for Portfolio Pulse.

There is one concept only: health. Low health means high risk. Every input
comes from the Snapshot or Timeline CSV and every deduction is explainable.
"""
from datetime import date
from math import exp

BANDS = [(50, "Critical"), (75, "Watch"), (100, "Healthy")]

DEFAULT_HEALTH_MODEL = "plain_pulse"
HEALTH_MODELS = {
    "plain_pulse": {
        "name": "Plain Pulse",
        "kind": "Auditable baseline",
        "short_explainer": (
            "Adds or removes fixed points for QBRs, payment, usage, contract length, "
            "renewal timing, and longevity."
        ),
        "interpretation": "Hand-calculable fixed thresholds, with no multipliers.",
    },
    "signal_compass": {
        "name": "Signal Compass",
        "kind": "Gradual contextual rules",
        "short_explainer": (
            "Starts at 100, then adjusts for engagement, payment, usage, contract length, "
            "renewal timing, longevity, and ARR decline."
        ),
        "interpretation": "A transparent warning index, not a churn probability.",
    },
    "retention_horizon": {
        "name": "Retention Horizon",
        "kind": "Experimental logistic index",
        "short_explainer": (
            "Weights the available signals, combines their contributions, then uses a "
            "logistic curve to produce a stable 0 to 100 index."
        ),
        "interpretation": (
            "An experimental weighted index, not a trained probability, because the CSV has no "
            "historical churn labels."
        ),
    },
}

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
NEW_ACCOUNT_MULTIPLIER = 1.15

ARR_DECLINE_THRESHOLD_PCT = -5.0
ARR_DECLINE_MULTIPLIER = 1.15

QBR_STRENGTH_POINTS = 2
UTIL_STRONG, UTIL_STRENGTH_POINTS = 80, 2
ACTIVE_STRONG, ACTIVE_STRENGTH_POINTS = 70, 2
TENURE_ONE_YEAR_DAYS = 365
TENURE_THREE_YEAR_DAYS = 365 * 3
TENURE_FIVE_YEAR_DAYS = 365 * 5
TENURE_STRENGTH_POINTS = ((TENURE_FIVE_YEAR_DAYS, 8), (TENURE_THREE_YEAR_DAYS, 5), (TENURE_ONE_YEAR_DAYS, 2))


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


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _model_result(base, model_id, score, drivers, strengths, **details):
    drivers.sort(key=lambda item: item["penalty"], reverse=True)
    strengths.sort(key=lambda item: item["points"], reverse=True)
    return {
        **base,
        "score": round(_clamp(score, 0.0, 100.0), 1),
        "band": _band(round(_clamp(score, 0.0, 100.0), 1)),
        "health_drivers": drivers,
        "health_strengths": strengths,
        "positive_points": round(sum(item["points"] for item in strengths), 1),
        "health_model": model_id,
        "health_model_name": HEALTH_MODELS[model_id]["name"],
        **details,
    }


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
    positive_points = 0.0
    strengths = []

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
        elif not qbr_inferred:
            positive_points += QBR_STRENGTH_POINTS
            strengths.append({"signal": "Recent QBR", "points": QBR_STRENGTH_POINTS})

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
        if seat_utilisation_pct >= UTIL_STRONG:
            positive_points += UTIL_STRENGTH_POINTS
            strengths.append({
                "signal": "Strong seat utilisation", "points": UTIL_STRENGTH_POINTS,
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
        if active_user_pct >= ACTIVE_STRONG:
            positive_points += ACTIVE_STRENGTH_POINTS
            strengths.append({
                "signal": "Strong active-user rate", "points": ACTIVE_STRENGTH_POINTS,
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

    if tenure_days is not None:
        for minimum_days, points in TENURE_STRENGTH_POINTS:
            if tenure_days >= minimum_days:
                positive_points += points
                strengths.append({"signal": "Customer longevity", "points": points})
                break

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
    else:
        tenure_mult = 1.0

    arr_trend_pct = account.get("arr_trend_pct")
    if arr_trend_pct is not None and arr_trend_pct < ARR_DECLINE_THRESHOLD_PCT:
        arr_mult = ARR_DECLINE_MULTIPLIER
    else:
        arr_mult = 1.0

    penalty = deduction * renewal_mult * tenure_mult * arr_mult
    score = round(max(0.0, min(100.0, 100 - penalty + positive_points)), 1)
    drivers.sort(key=lambda item: item["penalty"], reverse=True)
    strengths.sort(key=lambda item: item["points"], reverse=True)

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
        "positive_points": round(positive_points, 1),
        "health_strengths": strengths,
        "health_model": "signal_compass",
        "health_model_name": HEALTH_MODELS["signal_compass"]["name"],
    }


def score_plain_pulse_account(account, today=None):
    """A hand-calculable checklist using only fields in the existing CSVs."""
    base = score_account(account, today)
    deduction = 0.0
    positive = 0.0
    drivers = []
    strengths = []

    days_since_qbr = base.get("days_since_qbr")
    if days_since_qbr is not None and days_since_qbr > 180:
        deduction += 20
        drivers.append({
            "signal": "No QBR recorded" if base.get("qbr_inferred") else "QBR over 180 days ago",
            "penalty": 20,
        })
    elif days_since_qbr is not None and not base.get("qbr_inferred"):
        positive += 2
        strengths.append({"signal": "Recent QBR", "points": 2})

    if account.get("overdue_flag"):
        deduction += 20
        drivers.append({"signal": "Payment overdue", "penalty": 20})

    utilisation = account.get("seat_utilisation_pct")
    if utilisation is not None:
        if utilisation < 50:
            deduction += 10
            drivers.append({"signal": "Seat utilisation below 50%", "penalty": 10})
        elif utilisation >= 80:
            positive += 2
            strengths.append({"signal": "Strong seat utilisation", "points": 2})

    active_user = account.get("active_user_pct")
    if active_user is not None:
        if active_user < 40:
            deduction += 10
            drivers.append({"signal": "Active-user rate below 40%", "penalty": 10})
        elif active_user >= 70:
            positive += 2
            strengths.append({"signal": "Strong active-user rate", "points": 2})

    term = account.get("term_length_months")
    if term is not None and term <= 12:
        deduction += 15
        drivers.append({"signal": "12-month contract", "penalty": 15})
    elif term is not None and term <= 24:
        deduction += 5
        drivers.append({"signal": "24-month contract", "penalty": 5})

    if base.get("days_to_renewal") is not None and base["days_to_renewal"] <= 183:
        deduction += 10
        drivers.append({"signal": "Renewal within 6 months", "penalty": 10})

    tenure_days = base.get("tenure_days")
    if tenure_days is not None:
        for minimum_days, points in TENURE_STRENGTH_POINTS:
            if tenure_days >= minimum_days:
                positive += points
                strengths.append({"signal": "Customer longevity", "points": points})
                break

    return _model_result(
        base,
        "plain_pulse",
        100 - deduction + positive,
        drivers,
        strengths,
        raw_deduction=round(deduction, 1),
        model_adjustment=round(positive, 1),
    )


def score_retention_horizon_account(account, today=None):
    """A fixed logistic-style model using current CSV features without outcome training."""
    base = score_account(account, today)
    contributions = []

    def add(signal, value):
        if value:
            contributions.append({"signal": signal, "value": round(value, 3)})

    tenure_days = base.get("tenure_days")
    if tenure_days is not None:
        add("Customer longevity", 1.10 * _clamp(tenure_days / TENURE_FIVE_YEAR_DAYS, 0, 1))

    days_since_qbr = base.get("days_since_qbr")
    if days_since_qbr is not None:
        qbr_signal = 1 - 2 * _clamp(days_since_qbr / 365, 0, 1)
        add("QBR recency", 0.70 * qbr_signal)

    utilisation = account.get("seat_utilisation_pct")
    if utilisation is not None:
        add("Seat utilisation", 0.80 * _clamp((utilisation - 50) / 50, -1, 1))

    active_user = account.get("active_user_pct")
    if active_user is not None:
        add("Active-user rate", 0.70 * _clamp((active_user - 40) / 40, -1, 1))

    term = account.get("term_length_months")
    if term is not None:
        add("Contract commitment", 0.55 * _clamp((term - 24) / 12, -1, 1))

    days_to_renewal = base.get("days_to_renewal")
    if days_to_renewal is not None:
        runway_signal = 2 * _clamp(days_to_renewal / 1095, 0, 1) - 1
        add("Renewal runway", 0.45 * runway_signal)

    if account.get("overdue_flag"):
        add("Payment overdue", -1.20)

    tickets = account.get("tickets_12mo")
    thresholds = SEGMENT_THRESHOLDS.get(
        account.get("segment"), SEGMENT_THRESHOLDS[DEFAULT_SEGMENT],
    )
    if tickets is not None:
        ticket_risk = _clamp(
            (tickets - thresholds["tickets_clean"])
            / max(1, thresholds["tickets_bad"] - thresholds["tickets_clean"]),
            0,
            1,
        )
        add("High support demand", -0.45 * ticket_risk)

    arr_trend = account.get("arr_trend_pct")
    if arr_trend is not None and arr_trend < 0:
        add("ARR decline", -0.55 * _clamp(abs(arr_trend) / 30, 0, 1))

    linear_score = 0.40 + sum(item["value"] for item in contributions)
    score = 100 / (1 + exp(-linear_score))
    drivers = [
        {"signal": item["signal"], "penalty": round(abs(item["value"]) * 10, 1)}
        for item in contributions if item["value"] < 0
    ]
    strengths = [
        {"signal": item["signal"], "points": round(item["value"] * 10, 1)}
        for item in contributions if item["value"] > 0
    ]
    return _model_result(
        base,
        "retention_horizon",
        score,
        drivers,
        strengths,
        linear_score=round(linear_score, 3),
        model_contributions=contributions,
    )


def score_portfolio(accounts, today=None, model=DEFAULT_HEALTH_MODEL):
    scorers = {
        "signal_compass": score_account,
        "plain_pulse": score_plain_pulse_account,
        "retention_horizon": score_retention_horizon_account,
    }
    scorer = scorers.get(model, scorers[DEFAULT_HEALTH_MODEL])
    return [scorer(account, today) for account in accounts]


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
