"""
Derived and temporal metrics — pure functions, computed at request time,
never stored. Snapshot-only metrics (current_arr, historic_value,
momentum_ratio, arr_at_risk) work with just the Snapshot file. Everything
else here (nrr, grr, the ARR bridge, usage_trend, silent_decliner,
health_trend) requires the Timeline.
"""
from datetime import date

UTIL_CLEAN, UTIL_BAD, UTIL_MAX_PENALTY = 70, 20, 15
MOMENTUM_MONTH_MAX_PENALTY = 15
MOMENTUM_MONTH_GROWTH_BONUS = 5
MOMENTUM_MONTH_DECLINE_RATIO = 0.9
MOMENTUM_MONTH_GROWTH_RATIO = 1.1

SILENT_DECLINE_MRR_FLOOR = 0.98        # mrr flat/up allows this much noise
SILENT_DECLINE_USAGE_DROP_PCT = -15.0  # utilisation must have dropped at least this much


def _ramp_down(value, bad, clean, max_penalty):
    if value >= clean:
        return 0.0
    if value <= bad:
        return max_penalty
    return max_penalty * (clean - value) / (clean - bad)


# ── Snapshot-only metrics ─────────────────────────────────────────────

def current_arr(account):
    return round((account.get("avg_monthly_revenue_6mo") or 0.0) * 12, 2)


def historic_value(account):
    return round(account.get("total_revenue_36mo") or 0.0, 2)


def momentum_ratio(account):
    """Run-rate vs. lifetime monthly average — the 'poor-man's trend' that
    works without a Timeline. >1.05 growing, <0.95 declining, else flat.
    """
    total_36mo = account.get("total_revenue_36mo")
    avg_6mo = account.get("avg_monthly_revenue_6mo")
    if not total_36mo or avg_6mo is None:
        return None
    lifetime_monthly_avg = total_36mo / 36
    if lifetime_monthly_avg <= 0:
        return None
    return round(avg_6mo / lifetime_monthly_avg, 3)


def enrich_snapshot_metrics(account):
    """Attach current_arr / historic_value / momentum_ratio to one account."""
    enriched = dict(account)
    enriched["current_arr"] = current_arr(account)
    enriched["historic_value"] = historic_value(account)
    enriched["momentum_ratio"] = momentum_ratio(account)
    return enriched


def apply_timeline_overrides(accounts, timeline_by_account):
    """Single-source-of-truth rule: when a Timeline exists for an account,
    recompute avg_monthly_revenue_6mo (mean of its most recent up-to-6
    months) and total_revenue_36mo (sum of up to its most recent 36
    months) from it, overriding any hand-entered Snapshot values.
    """
    overridden = {}
    for account_id, account in accounts.items():
        rows = timeline_by_account.get(account_id)
        if not rows:
            overridden[account_id] = account
            continue
        recent = rows[-6:]
        window = rows[-36:]
        updated = dict(account)
        updated["avg_monthly_revenue_6mo"] = round(sum(r["mrr"] for r in recent) / len(recent), 2)
        updated["total_revenue_36mo"] = round(sum(r["mrr"] for r in window), 2)
        overridden[account_id] = updated
    return overridden


def arr_at_risk(scored_accounts, today, days_ahead=91, bands=None):
    """Sum of current_arr for accounts renewing within `days_ahead`,
    optionally restricted to a set of health bands (e.g. only Critical/At-risk).
    """
    total = 0.0
    for a in scored_accounts:
        renewal_date = a.get("renewal_date")
        if not renewal_date:
            continue
        days_to = (renewal_date - today).days
        if 0 <= days_to <= days_ahead and (bands is None or a.get("band") in bands):
            total += a.get("current_arr", 0.0)
    return round(total, 2)


# ── Timeline-required metrics ─────────────────────────────────────────

def _cohort_start_end(rows, start_month, end_month):
    """rows sorted by month. Returns (start_mrr or None, end_mrr)."""
    start_mrr = next((r["mrr"] for r in rows if r["month"] == start_month), None)
    end_mrr = next((r["mrr"] for r in rows if r["month"] == end_month), 0.0)
    return start_mrr, end_mrr


def revenue_retention(timeline_by_account, start_month, end_month):
    """NRR/GRR and the ARR-bridge components over [start_month, end_month],
    restricted to the cohort of accounts that existed at start_month
    (standard retention definition — excludes new-logo growth in the window).
    """
    starting_mrr = expansion = contraction = churn = 0.0

    for account_id, rows in timeline_by_account.items():
        start_mrr, end_mrr = _cohort_start_end(rows, start_month, end_month)
        if start_mrr is None or start_mrr <= 0:
            continue  # not part of the starting cohort
        starting_mrr += start_mrr
        if end_mrr <= 0:
            churn += start_mrr
        elif end_mrr > start_mrr:
            expansion += end_mrr - start_mrr
        elif end_mrr < start_mrr:
            contraction += start_mrr - end_mrr

    ending_mrr = starting_mrr + expansion - contraction - churn
    nrr = round(ending_mrr / starting_mrr * 100, 1) if starting_mrr else None
    grr = round((starting_mrr - contraction - churn) / starting_mrr * 100, 1) if starting_mrr else None

    return {
        "start": round(starting_mrr, 2),
        "expansion": round(expansion, 2),
        "contraction": round(contraction, 2),
        "churn": round(churn, 2),
        "end": round(ending_mrr, 2),
        "nrr": nrr,
        "grr": grr,
    }


def _pct_change_first_last(points):
    if len(points) < 2 or points[0] <= 0:
        return None
    return round((points[-1] - points[0]) / points[0] * 100, 1)


def usage_trend(rows):
    """Percent change in seat_utilisation_pct from the first to the last
    value present in the window. None if fewer than two data points.
    """
    points = [r["seat_utilisation_pct"] for r in rows if r["seat_utilisation_pct"] is not None]
    return _pct_change_first_last(points)


def mrr_trend(rows):
    """Percent change in mrr from the first to the last month in the window."""
    points = [r["mrr"] for r in rows]
    return _pct_change_first_last(points)


def is_silent_decliner(rows):
    """MRR flat-or-up while usage quietly collapses — pays on time,
    disengaging under the hood. The flagship leading indicator.
    """
    mrr_points = [r["mrr"] for r in rows]
    if len(mrr_points) < 2:
        return False
    trend = usage_trend(rows)
    mrr_holding = mrr_points[-1] >= mrr_points[0] * SILENT_DECLINE_MRR_FLOOR
    return bool(mrr_holding and trend is not None and trend <= SILENT_DECLINE_USAGE_DROP_PCT)


def health_trend_series(timeline_by_account):
    """A simplified, ARR-weighted monthly health proxy for the trend line.

    Only signals available at monthly granularity (mrr momentum vs. a
    trailing 3-month average, and seat_utilisation_pct) feed this — the
    Snapshot-only signals (contact recency, tickets, overdue) have no
    monthly history to reconstruct, so this is a proxy, not a replay of
    the full score.
    """
    months = sorted({r["month"] for rows in timeline_by_account.values() for r in rows})
    series = []
    for month in months:
        weighted_sum = 0.0
        weight_total = 0.0
        for rows in timeline_by_account.values():
            by_month = {r["month"]: r for r in rows}
            if month not in by_month:
                continue
            row = by_month[month]
            idx = [r["month"] for r in rows].index(month)
            trailing = [r["mrr"] for r in rows[max(0, idx - 3):idx]]
            trailing_avg = sum(trailing) / len(trailing) if trailing else row["mrr"]

            penalty = 0.0
            if trailing_avg > 0:
                ratio = row["mrr"] / trailing_avg
                if ratio < MOMENTUM_MONTH_DECLINE_RATIO:
                    penalty += MOMENTUM_MONTH_MAX_PENALTY
                elif ratio > MOMENTUM_MONTH_GROWTH_RATIO:
                    penalty -= MOMENTUM_MONTH_GROWTH_BONUS
            if row["seat_utilisation_pct"] is not None:
                penalty += _ramp_down(row["seat_utilisation_pct"], UTIL_BAD, UTIL_CLEAN, UTIL_MAX_PENALTY)

            monthly_score = max(0.0, min(100.0, 100 - penalty))
            weight = max(row["mrr"], 0.01)
            weighted_sum += monthly_score * weight
            weight_total += weight

        if weight_total:
            series.append({"month": month, "health": round(weighted_sum / weight_total, 1)})
    return series


def monthly_nrr_series(timeline_by_account):
    """Month-over-month net retention rate — a simplified NRR trend line
    (not a trailing-12-month figure; the headline NRR/GRR KPI uses the
    full uploaded window via revenue_retention() instead).
    """
    months = sorted({r["month"] for rows in timeline_by_account.values() for r in rows})
    series = []
    for prev_month, month in zip(months, months[1:]):
        result = revenue_retention(timeline_by_account, prev_month, month)
        if result["nrr"] is not None:
            series.append({"month": month, "nrr": result["nrr"]})
    return series
