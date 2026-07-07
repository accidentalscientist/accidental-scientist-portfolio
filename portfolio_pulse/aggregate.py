"""
Turns scored accounts (+ optional Timeline metrics) into every payload the
templates need: the KPI strip, the auto-generated summary sentence, and
the ten chart payloads (six Snapshot-only, four Timeline-only). Branches
cleanly on whether a Timeline was uploaded.
"""
from . import metrics
from .scoring import BANDS, portfolio_health

BAND_LABELS = [label for _, label in BANDS]
GOLD_SHARE = 0.20
SILVER_SHARE = 0.30
RENEWAL_QUARTERS = [
    ("0-3mo", 0, 91), ("3-6mo", 92, 182), ("6-9mo", 183, 273), ("9-12mo", 274, 365),
]
MOMENTUM_TOP_N = 15
SOFTENING_TOP_N = 10  # among the N largest accounts, how many are struggling


def _band_for_score(score):
    for upper, label in BANDS:
        if score <= upper:
            return label
    return BANDS[-1][1]


def _money(value):
    value = value or 0
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"${value / 1_000:.0f}k"
    return f"${value:.0f}"


def build_dashboard_context(scored_accounts, today, timeline_by_account=None):
    has_timeline = bool(timeline_by_account)

    if has_timeline:
        for a in scored_accounts:
            rows = timeline_by_account.get(a["account_id"], [])
            a["usage_trend"] = metrics.usage_trend(rows)
            a["mrr_trend"] = metrics.mrr_trend(rows)
            a["silent_decliner"] = metrics.is_silent_decliner(rows)

    context = {
        "has_timeline": has_timeline,
        "kpi": _build_kpi(scored_accounts, today, timeline_by_account),
        "chart_revenue_concentration": _revenue_tiers(scored_accounts),
        "chart_revenue_vs_risk": _revenue_vs_risk(scored_accounts),
        "chart_revenue_vs_health": _revenue_vs_health(scored_accounts),
        "chart_renewal_wall": _renewal_wall(scored_accounts, today),
        "chart_industry_breakdown": _industry_breakdown(scored_accounts),
        "chart_coverage_engagement": _coverage_engagement(scored_accounts),
        "chart_momentum": _momentum(scored_accounts),
    }

    if has_timeline:
        months = sorted({r["month"] for rows in timeline_by_account.values() for r in rows})
        retention = metrics.revenue_retention(timeline_by_account, months[0], months[-1])
        context["kpi"]["nrr"] = retention["nrr"]
        context["kpi"]["grr"] = retention["grr"]
        context["chart_arr_bridge"] = _arr_bridge(retention)
        context["chart_health_nrr_trend"] = _health_nrr_trend(timeline_by_account)
        context["chart_usage_revenue_divergence"] = _usage_revenue_divergence(scored_accounts)
        context["chart_revenue_by_group"] = _revenue_by_group(scored_accounts, timeline_by_account)
        context["silent_decliners"] = [a for a in scored_accounts if a.get("silent_decliner")]

    context["summary_sentence"] = _summary_sentence(context["kpi"], has_timeline)
    return context


def _build_kpi(scored_accounts, today, timeline_by_account):
    health = portfolio_health(scored_accounts)
    total_arr = sum(a.get("current_arr", 0.0) for a in scored_accounts)

    band_counts = {label: 0 for label in BAND_LABELS}
    band_arr = {label: 0.0 for label in BAND_LABELS}
    for a in scored_accounts:
        band_counts[a["band"]] += 1
        band_arr[a["band"]] += a.get("current_arr", 0.0)

    arr_renewing_next_quarter = metrics.arr_at_risk(scored_accounts, today, days_ahead=91)

    top_accounts = sorted(scored_accounts, key=lambda a: a.get("current_arr", 0.0), reverse=True)[:SOFTENING_TOP_N]
    softening_count = sum(1 for a in top_accounts if a["band"] in ("Critical", "At-risk"))

    # A list, not a dict keyed by band label — Django templates can't dot into
    # a dict key containing a hyphen ("At-risk"), but looping a list is fine.
    band_rows = [
        {"label": label, "slug": label.lower().replace("-", ""),
         "count": band_counts[label], "arr": round(band_arr[label], 2)}
        for label in BAND_LABELS
    ]

    return {
        "health_weighted": health["weighted"],
        "health_unweighted": health["unweighted"],
        "total_arr": round(total_arr, 2),
        "account_count": len(scored_accounts),
        "avg_arr": round(total_arr / len(scored_accounts), 2) if scored_accounts else 0,
        "arr_renewing_next_quarter": arr_renewing_next_quarter,
        "softening_count": softening_count,
        "nrr": None,
        "grr": None,
        "band_rows": band_rows,
    }


def _summary_sentence(kpi, has_timeline):
    parts = [f"Book is {kpi['health_weighted']:.0f}% healthy at {_money(kpi['total_arr'])} ARR"]
    if has_timeline and kpi.get("nrr") is not None:
        parts[0] += f", running {kpi['nrr']:.0f}% NRR"

    renewal_clause = f"{_money(kpi['arr_renewing_next_quarter'])} renews next quarter"
    if kpi["softening_count"]:
        n = kpi["softening_count"]
        renewal_clause += f" with {n} large account{'s' if n != 1 else ''} softening"

    return parts[0] + "; " + renewal_clause + "."


def _revenue_tiers(accounts):
    """Accounts sorted into Gold/Silver/Bronze by ARR rank alone — the top
    20% by ARR are Gold, the next 30% Silver, the remaining 50% Bronze.
    """
    ranked = sorted(accounts, key=lambda a: a.get("current_arr", 0.0), reverse=True)
    n = len(ranked)
    gold_n = max(1, round(n * GOLD_SHARE)) if n else 0
    silver_n = max(1, round(n * SILVER_SHARE)) if n else 0
    tier_groups = [
        ("Gold", ranked[:gold_n]),
        ("Silver", ranked[gold_n:gold_n + silver_n]),
        ("Bronze", ranked[gold_n + silver_n:]),
    ]

    total_arr = sum(a.get("current_arr", 0.0) for a in ranked)
    tiers = []
    for label, group in tier_groups:
        arr = sum(a.get("current_arr", 0.0) for a in group)
        tiers.append({
            "tier": label, "arr": round(arr, 2), "count": len(group),
            "pct_of_total": round(arr / total_arr * 100, 1) if total_arr else 0,
            "top_accounts": [a["account_name"] for a in group[:5]],
        })
    return {"tiers": tiers}


def _revenue_vs_risk(accounts):
    return [
        {"name": a["account_name"], "risk_score": a["risk_score"], "current_arr": round(a.get("current_arr", 0.0), 2),
         "historic_value": round(a.get("historic_value", 0.0), 2), "risk_band": a["risk_band"]}
        for a in accounts
    ]


def _revenue_vs_health(accounts):
    return [
        {"name": a["account_name"], "score": a["score"], "current_arr": round(a.get("current_arr", 0.0), 2),
         "historic_value": round(a.get("historic_value", 0.0), 2), "band": a["band"]}
        for a in accounts
    ]


def _renewal_wall(accounts, today):
    labels = [q[0] for q in RENEWAL_QUARTERS]
    series = {label: [0.0] * len(RENEWAL_QUARTERS) for label in BAND_LABELS}
    for a in accounts:
        days_to = a.get("days_to_renewal")
        if days_to is None or days_to < 0:
            continue
        for i, (_, lo, hi) in enumerate(RENEWAL_QUARTERS):
            if lo <= days_to <= hi:
                series[a["band"]][i] += a.get("current_arr", 0.0)
                break
    return {"labels": labels, "series": {k: [round(v, 2) for v in vals] for k, vals in series.items()}}


def _industry_breakdown(accounts):
    by_industry = {}
    for a in accounts:
        bucket = by_industry.setdefault(a["industry"], {"arr": 0.0, "scores": [], "count": 0})
        bucket["arr"] += a.get("current_arr", 0.0)
        bucket["scores"].append(a["score"])
        bucket["count"] += 1

    rows = []
    for industry, b in by_industry.items():
        avg_score = sum(b["scores"]) / len(b["scores"])
        rows.append({
            "industry": industry, "arr": round(b["arr"], 2), "account_count": b["count"],
            "avg_health": round(avg_score, 1), "band": _band_for_score(avg_score),
        })
    rows.sort(key=lambda r: r["arr"], reverse=True)
    return rows


def _coverage_engagement(accounts):
    return [
        {"name": a["account_name"], "days_since_contact": a["days_since_contact"],
         "current_arr": round(a.get("current_arr", 0.0), 2), "band": a["band"]}
        for a in accounts if a.get("days_since_contact") is not None
    ]


def _momentum(accounts):
    with_momentum = [a for a in accounts if a.get("momentum_ratio") is not None]
    ranked = sorted(with_momentum, key=lambda a: a.get("current_arr", 0.0), reverse=True)[:MOMENTUM_TOP_N]
    ranked.sort(key=lambda a: a["momentum_ratio"])
    return [
        {"name": a["account_name"], "deviation_pct": round((a["momentum_ratio"] - 1) * 100, 1),
         "current_arr": round(a.get("current_arr", 0.0), 2), "band": a["band"]}
        for a in ranked
    ]


def _arr_bridge(retention):
    return {
        "start": retention["start"], "expansion": retention["expansion"],
        "contraction": retention["contraction"], "churn": retention["churn"], "end": retention["end"],
    }


def _health_nrr_trend(timeline_by_account):
    health_series = metrics.health_trend_series(timeline_by_account)
    nrr_series = metrics.monthly_nrr_series(timeline_by_account)
    return {
        "health_labels": [p["month"].strftime("%b %Y") for p in health_series],
        "health": [p["health"] for p in health_series],
        "nrr_labels": [p["month"].strftime("%b %Y") for p in nrr_series],
        "nrr": [p["nrr"] for p in nrr_series],
    }


def _usage_revenue_divergence(accounts):
    return [
        {"name": a["account_name"], "mrr_trend": a.get("mrr_trend"), "usage_trend": a.get("usage_trend"),
         "silent_decliner": a.get("silent_decliner", False), "current_arr": round(a.get("current_arr", 0.0), 2)}
        for a in accounts if a.get("mrr_trend") is not None and a.get("usage_trend") is not None
    ]


def _revenue_by_group(accounts, timeline_by_account):
    account_group = {a["account_id"]: {"segment": a["segment"], "industry": a["industry"]} for a in accounts}
    months = sorted({r["month"] for rows in timeline_by_account.values() for r in rows})

    def _series_for(key):
        groups = sorted({g[key] for g in account_group.values()})
        series = {g: [0.0] * len(months) for g in groups}
        month_index = {m: i for i, m in enumerate(months)}
        for account_id, rows in timeline_by_account.items():
            group = account_group.get(account_id, {}).get(key)
            if group is None:
                continue
            for r in rows:
                series[group][month_index[r["month"]]] += r["mrr"]
        return {g: [round(v, 2) for v in vals] for g, vals in series.items()}

    return {
        "labels": [m.strftime("%b %Y") for m in months],
        "by_segment": _series_for("segment"),
        "by_industry": _series_for("industry"),
    }
