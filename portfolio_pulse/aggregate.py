"""Build every Portfolio Pulse payload from scored accounts and ARR history."""
from . import metrics
from .scoring import BANDS, portfolio_health

BAND_LABELS = [label for _, label in BANDS]
RUNWAY_BUCKETS = [
    ("0-6 months", None, 183, "Immediate"),
    ("6-18 months", 184, 548, "Plan now"),
    ("18-36 months", 549, 1095, "Monitor"),
    ("36+ months", 1096, None, "Low timing pressure"),
]
TENURE_BUCKETS = [
    ("<1 year", 0, 364),
    ("1-3 years", 365, 1094),
    ("3-5 years", 1095, 1824),
    ("5-10 years", 1825, 3649),
    ("10+ years", 3650, None),
]
VALUE_TIERS = ("Gold", "Silver", "Bronze")


def _money(value):
    value = value or 0
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}k"
    return f"${value:.0f}"


def _contract_value(account):
    years = (account.get("term_length_months") or 0) / 12
    return round(account.get("current_arr", 0.0) * years, 2)


def _runway_label(days_to_renewal):
    if days_to_renewal is None:
        return "Unknown"
    for label, lower, upper, _ in RUNWAY_BUCKETS:
        if (lower is None or days_to_renewal >= lower) and (upper is None or days_to_renewal <= upper):
            return label
    return "Unknown"


def build_dashboard_context(scored_accounts, today, timeline_by_account=None):
    has_timeline = bool(timeline_by_account)
    # Current-state views describe the live book. Zero-ARR accounts remain in
    # the timeline so Revenue Story can still explain historical churn, but
    # they must not inflate current account counts or health distributions.
    active_accounts = [
        account for account in scored_accounts
        if account.get("current_arr", 0.0) > 0
    ]

    if has_timeline:
        for account in scored_accounts:
            rows = timeline_by_account.get(account["account_id"], [])
            account["usage_trend"] = metrics.usage_trend(rows)
            account["arr_trend_pct"] = metrics.arr_trend(rows)
            account["arr_change_dollars"] = metrics.arr_change_dollars(rows)
            attention_signal = metrics.classify_attention_signal(rows)
            evidence = attention_signal.get("evidence") or {}
            account["attention_state"] = attention_signal["attention_state"]
            account["attention_reason"] = attention_signal["attention_reason"]
            account["trend_evidence"] = evidence
            # Retained for backwards-compatible template and API consumers.
            account["hidden_renewal_risk"] = attention_signal["attention_state"] == "attention"

    context = {
        "has_timeline": has_timeline,
        "kpi": _build_kpi(active_accounts, timeline_by_account),
        "chart_concentration": _customer_concentration(active_accounts),
        "chart_arr_distribution": _arr_distribution(active_accounts),
        "chart_contract_runway": _contract_runway(active_accounts),
        "chart_customer_tenure": _customer_tenure(active_accounts),
        "chart_industry_portfolio": _industry_portfolio(active_accounts),
        "chart_health_distribution": _health_distribution(active_accounts),
        "chart_qbr_coverage": _qbr_coverage(active_accounts),
        "priority_accounts": _priority_accounts(active_accounts),
    }

    if has_timeline:
        context.update({
            "chart_growers_decliners": _growers_decliners(scored_accounts),
            "chart_usage_arr_divergence": _usage_arr_divergence(active_accounts),
            "attention_accounts": [
                account for account in active_accounts
                if account.get("attention_state") == "attention"
            ],
            "hidden_renewal_risks": [
                account for account in active_accounts
                if account.get("attention_state") == "attention"
            ],
            "accelerating_accounts": [
                account for account in active_accounts
                if account.get("attention_state") == "acceleration"
            ],
            "chart_account_journeys": _account_signal_journeys(
                active_accounts, timeline_by_account,
            ),
            "chart_arr_trend": _arr_trend(timeline_by_account),
            "chart_health_trend": _health_trend(timeline_by_account),
            "chart_arr_movement": _arr_movement(timeline_by_account),
            "chart_arr_by_group": metrics.revenue_by_group(
                scored_accounts, timeline_by_account,
            ),
        })

    context["summary_sentence"] = _summary_sentence(context["kpi"])
    return context


def _build_kpi(accounts, timeline_by_account):
    health = portfolio_health(accounts)
    total_arr = sum(account.get("current_arr", 0.0) for account in accounts)
    ranked = sorted(accounts, key=lambda account: account.get("current_arr", 0.0), reverse=True)
    top5_arr = sum(account.get("current_arr", 0.0) for account in ranked[:5])

    immediate_arr = sum(
        account.get("current_arr", 0.0)
        for account in accounts
        if account.get("days_to_renewal") is not None
        and account["days_to_renewal"] <= 183
    )
    planning_arr = sum(
        account.get("current_arr", 0.0)
        for account in accounts
        if account.get("days_to_renewal") is not None
        and account["days_to_renewal"] <= 548
    )
    one_year_arr = sum(
        account.get("current_arr", 0.0)
        for account in accounts
        if (account.get("term_length_months") or 0) <= 12
    )
    immediate_count = sum(
        1 for account in accounts
        if account.get("days_to_renewal") is not None
        and account["days_to_renewal"] <= 183
    )
    established_accounts = [
        account for account in accounts
        if account.get("tenure_days") is not None
        and account["tenure_days"] >= 365 * 5
    ]
    established_arr = sum(
        account.get("current_arr", 0.0) for account in established_accounts
    )

    band_counts = {label: 0 for label in BAND_LABELS}
    band_arr = {label: 0.0 for label in BAND_LABELS}
    for account in accounts:
        band_counts[account["band"]] += 1
        band_arr[account["band"]] += account.get("current_arr", 0.0)

    band_rows = [
        {
            "label": label,
            "slug": label.lower().replace("-", ""),
            "count": band_counts[label],
            "arr": round(band_arr[label], 2),
        }
        for label in BAND_LABELS
    ]
    critical_watch_arr = sum(
        row["arr"] for row in band_rows
        if row["label"] in ("Critical", "Watch")
    )

    arr_change = arr_change_pct = None
    if timeline_by_account:
        series = metrics.portfolio_arr_series(timeline_by_account)
        if len(series) >= 2:
            start = series[-min(len(series), 13)]["arr"]
            end = series[-1]["arr"]
            arr_change = round(end - start, 2)
            arr_change_pct = round(arr_change / start * 100, 1) if start else None

    completeness = (
        round(sum(account["data_completeness"] for account in accounts) / len(accounts), 1)
        if accounts else 0
    )
    return {
        "health_weighted": health["weighted"],
        "health_unweighted": health["unweighted"],
        "data_completeness": completeness,
        "total_arr": round(total_arr, 2),
        "account_count": len(accounts),
        "avg_arr": round(total_arr / len(accounts), 2) if accounts else 0,
        "immediate_arr": round(immediate_arr, 2),
        "immediate_count": immediate_count,
        "planning_arr": round(planning_arr, 2),
        "planning_pct": round(planning_arr / total_arr * 100, 1) if total_arr else 0,
        "top5_share": round(top5_arr / total_arr * 100, 1) if total_arr else 0,
        "one_year_arr": round(one_year_arr, 2),
        "critical_watch_arr": round(critical_watch_arr, 2),
        "critical_watch_pct": round(critical_watch_arr / total_arr * 100, 1) if total_arr else 0,
        "established_arr": round(established_arr, 2),
        "established_count": len(established_accounts),
        "arr_change": arr_change,
        "arr_change_pct": arr_change_pct,
        "band_rows": band_rows,
    }


def _summary_sentence(kpi):
    sentence = (
        f"Portfolio holds {_money(kpi['total_arr'])} ARR at "
        f"{kpi['health_weighted']:.0f} health; "
        f"{_money(kpi['planning_arr'])} ({kpi['planning_pct']:.0f}%) "
        "needs renewal planning within 18 months"
    )
    if kpi.get("arr_change") is not None:
        direction = "up" if kpi["arr_change"] >= 0 else "down"
        sentence += f", with ARR {direction} {_money(abs(kpi['arr_change']))} over 12 months"
    return sentence + "."


def _customer_concentration(accounts):
    ranked = sorted(accounts, key=lambda account: account.get("current_arr", 0.0), reverse=True)
    total_arr = sum(account.get("current_arr", 0.0) for account in ranked)
    running = 0.0
    rows = []
    for account in ranked[:50]:
        arr = account.get("current_arr", 0.0)
        running += arr
        rows.append({
            "name": account["account_name"],
            "arr": round(arr, 2),
            "health": account["score"],
            "band": account["band"],
            "contract_value": _contract_value(account),
            "term_months": account.get("term_length_months"),
        })
    return {
        "accounts": rows,
        "largest_share": round(rows[0]["arr"] / total_arr * 100, 1) if rows and total_arr else 0,
        "top5_share": round(
            sum(account.get("current_arr", 0.0) for account in ranked[:5])
            / total_arr * 100, 1,
        ) if total_arr else 0,
        "top10_share": round(
            sum(account.get("current_arr", 0.0) for account in ranked[:10])
            / total_arr * 100, 1,
        ) if total_arr else 0,
        "shown_count": len(rows),
        "portfolio_count": len(ranked),
        "shown_arr_share": round(running / total_arr * 100, 1) if total_arr else 0,
    }


def _arr_distribution(accounts):
    """Split the ARR-ranked book into balanced Gold / Silver / Bronze cohorts."""
    ranked = sorted(
        accounts,
        key=lambda account: account.get("current_arr", 0.0),
        reverse=True,
    )
    base, remainder = divmod(len(ranked), len(VALUE_TIERS))
    tier_sizes = [
        base + (1 if index < remainder else 0)
        for index in range(len(VALUE_TIERS))
    ]
    rows = []
    cursor = 0
    for label, size in zip(VALUE_TIERS, tier_sizes):
        group = ranked[cursor:cursor + size]
        cursor += size
        total = sum(account.get("current_arr", 0.0) for account in group)
        values = [account.get("current_arr", 0.0) for account in group]
        rows.append({
            "label": label,
            "count": len(group),
            "average_arr": round(total / len(group), 2) if group else 0,
            "total_arr": round(total, 2),
            "highest_arr": round(max(values), 2) if values else 0,
            "lowest_arr": round(min(values), 2) if values else 0,
        })
    return rows


def _contract_runway(accounts):
    rows = []
    for label, lower, upper, action in RUNWAY_BUCKETS:
        group = [
            account for account in accounts
            if account.get("days_to_renewal") is not None
            and (lower is None or account["days_to_renewal"] >= lower)
            and (upper is None or account["days_to_renewal"] <= upper)
        ]
        arr = sum(account.get("current_arr", 0.0) for account in group)
        rows.append({
            "label": label,
            "action": action,
            "arr": round(arr, 2),
            "count": len(group),
            "resign_value": round(arr * 3, 2),
            "secured_value": round(sum(_contract_value(account) for account in group), 2),
            "one_year_arr": round(sum(
                account.get("current_arr", 0.0)
                for account in group
                if (account.get("term_length_months") or 0) <= 12
            ), 2),
        })
    return rows


def _customer_tenure(accounts):
    rows = []
    for label, lower, upper in TENURE_BUCKETS:
        group = [
            account for account in accounts
            if account.get("tenure_days") is not None
            and account["tenure_days"] >= lower
            and (upper is None or account["tenure_days"] <= upper)
        ]
        rows.append({
            "label": label,
            "arr": round(sum(account.get("current_arr", 0.0) for account in group), 2),
            "count": len(group),
            "contract_value": round(sum(_contract_value(account) for account in group), 2),
        })
    return rows


def _industry_portfolio(accounts):
    by_industry = {}
    for account in accounts:
        bucket = by_industry.setdefault(account["industry"], {
            "count": 0,
            "total_arr": 0.0,
            "weighted_health": 0.0,
            "bands": {label: 0.0 for label in BAND_LABELS},
            "largest_arr": 0.0,
        })
        arr = account.get("current_arr", 0.0)
        bucket["count"] += 1
        bucket["total_arr"] += arr
        bucket["weighted_health"] += account["score"] * arr
        bucket["bands"][account["band"]] += arr
        bucket["largest_arr"] = max(bucket["largest_arr"], arr)

    rows = []
    for industry, bucket in by_industry.items():
        total = bucket["total_arr"]
        rows.append({
            "industry": industry,
            "count": bucket["count"],
            "total_arr": round(total, 2),
            "healthy_arr": round(bucket["bands"].get("Healthy", 0.0), 2),
            "watch_arr": round(bucket["bands"].get("Watch", 0.0), 2),
            "critical_arr": round(bucket["bands"].get("Critical", 0.0), 2),
            "avg_health": round(bucket["weighted_health"] / total, 1) if total else 0,
            "largest_share": round(bucket["largest_arr"] / total * 100, 1) if total else 0,
        })
    rows.sort(key=lambda row: row["total_arr"], reverse=True)
    return rows


def _health_distribution(accounts):
    rows = []
    for label in BAND_LABELS:
        group = [account for account in accounts if account["band"] == label]
        rows.append({
            "band": label,
            "count": len(group),
            "arr": round(sum(account.get("current_arr", 0.0) for account in group), 2),
        })
    return rows


def _qbr_coverage(accounts):
    return [{
        "name": account["account_name"],
        "days_since_qbr": account.get("days_since_qbr"),
        "arr": round(account.get("current_arr", 0.0), 2),
        "runway": _runway_label(account.get("days_to_renewal")),
        "renewal_days": account.get("days_to_renewal"),
        "health": account["score"],
        "qbr_inferred": account.get("qbr_inferred", False),
        "owner": account.get("csm_owner"),
    } for account in accounts if account.get("days_since_qbr") is not None]


def _priority_accounts(accounts):
    rows = []
    for account in accounts:
        days = account.get("days_to_renewal")
        if days is None or days > 1095:
            renewal_factor = 1.0
        elif days <= 183:
            renewal_factor = 2.0
        elif days <= 548:
            renewal_factor = 1.5
        else:
            renewal_factor = 1.15
        severity = max(1.0, 100 - account["score"])
        priority = account.get("current_arr", 0.0) * severity * renewal_factor
        drivers = [driver["signal"] for driver in account.get("health_drivers", [])[:3]]
        rows.append({
            "name": account["account_name"],
            "arr": round(account.get("current_arr", 0.0), 2),
            "contract_value": _contract_value(account),
            "health": account["score"],
            "band": account["band"],
            "runway": _runway_label(days),
            "days_to_renewal": days,
            "days_since_qbr": account.get("days_since_qbr"),
            "qbr_inferred": account.get("qbr_inferred", False),
            "drivers": drivers or ["No material deductions"],
            "owner": account.get("csm_owner") or "Unassigned",
            "data_completeness": account["data_completeness"],
            "term_months": account.get("term_length_months"),
            "priority": priority,
        })
    rows.sort(key=lambda row: row["priority"], reverse=True)
    return rows[:6]


def _growers_decliners(accounts):
    comparable = [
        account for account in accounts
        if account.get("arr_change_dollars") is not None
    ]
    decliners = sorted(comparable, key=lambda account: account["arr_change_dollars"])[:5]
    growers = sorted(
        comparable, key=lambda account: account["arr_change_dollars"], reverse=True,
    )[:5]
    combined = decliners + list(reversed(growers))
    return [{
        "name": account["account_name"],
        "change": round(account["arr_change_dollars"], 2),
        "change_pct": account.get("arr_trend_pct"),
        "arr": round(account.get("current_arr", 0.0), 2),
    } for account in combined]


def _usage_arr_divergence(accounts):
    rows = []
    for account in accounts:
        evidence = account.get("trend_evidence") or {}
        if (
            evidence.get("arr_change_pct") is None
            or evidence.get("usage_change_pp") is None
        ):
            continue
        rows.append({
            "id": account["account_id"],
            "name": account["account_name"],
            "arr_trend": evidence["arr_change_pct"],
            "usage_trend": evidence["usage_change_pp"],
            "attention_state": account.get("attention_state", "standard"),
            "attention_reason": account.get("attention_reason"),
            "arr": round(account.get("current_arr", 0.0), 2),
            "eligible": evidence.get("eligible", False),
            "window_label": evidence.get("window_label"),
            "observation_count": evidence.get("observation_count"),
            "span_months": evidence.get("span_months"),
            "method": evidence.get("method"),
            "validation": evidence.get("validation"),
        })
    return rows


def _account_signal_journeys(accounts, timeline_by_account):
    account_by_id = {account["account_id"]: account for account in accounts}
    journeys = []
    for account_id, account in account_by_id.items():
        rows = timeline_by_account.get(account_id, [])
        if not rows:
            continue
        journeys.append({
            "id": account_id,
            "name": account["account_name"],
            "attention_state": account.get("attention_state", "standard"),
            "attention_reason": account.get("attention_reason"),
            "current_arr": round(account.get("current_arr", 0.0), 2),
            "window_label": (account.get("trend_evidence") or {}).get("window_label"),
            "labels": [row["month"].strftime("%b %Y") for row in rows],
            "arr": [round(row["arr"], 2) for row in rows],
            "usage": [row.get("seat_utilisation_pct") for row in rows],
        })
    state_rank = {"attention": 0, "acceleration": 1, "standard": 2}
    journeys.sort(key=lambda row: (
        state_rank.get(row["attention_state"], 3),
        -row["current_arr"],
        row["name"],
    ))
    return journeys


def _arr_trend(timeline_by_account):
    series = metrics.portfolio_arr_series(timeline_by_account)
    return {
        "labels": [point["month"].strftime("%b %Y") for point in series],
        "arr": [point["arr"] for point in series],
    }


def _health_trend(timeline_by_account):
    series = metrics.health_trend_series(timeline_by_account)
    return {
        "labels": [point["month"].strftime("%b %Y") for point in series],
        "health": [point["health"] for point in series],
    }


def _arr_movement(timeline_by_account):
    series = metrics.monthly_arr_movement(timeline_by_account)
    return {
        "labels": [point["month"].strftime("%b %Y") for point in series],
        "new": [point["new"] for point in series],
        "expansion": [point["expansion"] for point in series],
        "contraction": [point["contraction"] for point in series],
        "churn": [point["churn"] for point in series],
        "net": [point["net"] for point in series],
    }
