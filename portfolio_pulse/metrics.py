"""ARR-first snapshot and timeline metrics for Portfolio Pulse."""

UTIL_TREND_CLEAN, UTIL_TREND_BAD, UTIL_TREND_MAX = 85, 30, 25
ACTIVE_TREND_CLEAN, ACTIVE_TREND_BAD, ACTIVE_TREND_MAX = 75, 20, 20
TICKET_TREND_CLEAN, TICKET_TREND_BAD, TICKET_TREND_MAX = 1, 8, 15
ARR_MOMENTUM_MAX = 20

SILENT_DECLINE_ARR_FLOOR = -2.0
SILENT_DECLINE_USAGE_DROP_PCT = -15.0
EXPANSION_DIVERGENCE_ARR_GROWTH_PCT = 20.0
EXPANSION_DIVERGENCE_USAGE_CEILING_PCT = 5.0


def _ramp_down(value, bad, clean, max_penalty):
    if value >= clean:
        return 0.0
    if value <= bad:
        return max_penalty
    return max_penalty * (clean - value) / (clean - bad)


def _ramp_up(value, clean, bad, max_penalty):
    if value <= clean:
        return 0.0
    if value >= bad:
        return max_penalty
    return max_penalty * (value - clean) / (bad - clean)


def current_arr(account):
    """Prefer the ARR-native field; accept the legacy monthly field."""
    value = account.get("current_arr")
    if value is not None:
        return round(value, 2)
    return round((account.get("avg_monthly_revenue_6mo") or 0.0) * 12, 2)


def historic_value(account):
    """Legacy lifetime revenue value retained only for old uploads/tests."""
    return round(account.get("total_revenue_36mo") or 0.0, 2)


def enrich_snapshot_metrics(account):
    enriched = dict(account)
    enriched["current_arr"] = current_arr(account)
    enriched["historic_value"] = historic_value(account)
    enriched.setdefault("arr_trend_pct", None)
    enriched.setdefault("arr_change_dollars", None)
    return enriched


def _comparison_points(rows, months=12):
    if len(rows) < 2:
        return None, None
    start_index = -min(len(rows), months + 1)
    return rows[start_index], rows[-1]


def arr_change_dollars(rows, months=12):
    start, end = _comparison_points(rows, months)
    if not start or not end:
        return None
    return round(end["arr"] - start["arr"], 2)


def arr_trend(rows, months=12):
    start, end = _comparison_points(rows, months)
    if not start or not end or start["arr"] <= 0:
        return None
    return round((end["arr"] - start["arr"]) / start["arr"] * 100, 1)


def usage_trend(rows, months=12):
    comparison_rows = rows[-min(len(rows), months + 1):]
    points = [
        row["seat_utilisation_pct"]
        for row in comparison_rows
        if row.get("seat_utilisation_pct") is not None
    ]
    if len(points) < 2 or points[0] <= 0:
        return None
    return round((points[-1] - points[0]) / points[0] * 100, 1)


def apply_timeline_overrides(accounts, timeline_by_account):
    """Make the ARR timeline the source of truth when it is present."""
    overridden = {}
    for account_id, account in accounts.items():
        rows = timeline_by_account.get(account_id)
        if not rows:
            overridden[account_id] = account
            continue
        updated = dict(account)
        updated["current_arr"] = round(rows[-1]["arr"], 2)
        updated["entry_arr"] = round(rows[0]["arr"], 2)
        updated["arr_trend_pct"] = arr_trend(rows)
        updated["arr_change_dollars"] = arr_change_dollars(rows)
        # Keep legacy fields populated for backward-compatible code paths.
        updated["avg_monthly_revenue_6mo"] = round(
            sum(row["arr"] for row in rows[-6:]) / len(rows[-6:]) / 12, 2,
        )
        updated["total_revenue_36mo"] = round(
            sum(row["arr"] / 12 for row in rows[-36:]), 2,
        )
        overridden[account_id] = updated
    return overridden


def is_hidden_renewal_risk(rows):
    arr_pct = arr_trend(rows)
    usage_pct = usage_trend(rows)
    return bool(
        arr_pct is not None
        and usage_pct is not None
        and (
            (
                arr_pct >= SILENT_DECLINE_ARR_FLOOR
                and usage_pct <= SILENT_DECLINE_USAGE_DROP_PCT
            )
            or (
                arr_pct >= EXPANSION_DIVERGENCE_ARR_GROWTH_PCT
                and usage_pct <= EXPANSION_DIVERGENCE_USAGE_CEILING_PCT
            )
        )
    )


def _months(timeline_by_account):
    return sorted({
        row["month"]
        for rows in timeline_by_account.values()
        for row in rows
    })


def portfolio_arr_series(timeline_by_account):
    months = _months(timeline_by_account)
    totals = {month: 0.0 for month in months}
    for rows in timeline_by_account.values():
        for row in rows:
            totals[row["month"]] += row["arr"]
    return [
        {"month": month, "arr": round(totals[month], 2)}
        for month in months
    ]


def health_trend_series(timeline_by_account):
    """ARR-weighted monthly signal health using all available timeline inputs.

    This is intentionally scoped to usage, activity, support, and ARR. It is
    not a replay of the full current health score because QBR, payment, and
    historical contract state are Snapshot-only.
    """
    months = _months(timeline_by_account)
    series = []
    for month in months:
        weighted_sum = 0.0
        weight_total = 0.0
        for rows in timeline_by_account.values():
            by_month = {row["month"]: row for row in rows}
            row = by_month.get(month)
            if not row:
                continue
            idx = next(i for i, candidate in enumerate(rows) if candidate["month"] == month)
            trailing = [candidate["arr"] for candidate in rows[max(0, idx - 3):idx]]
            trailing_avg = sum(trailing) / len(trailing) if trailing else row["arr"]

            penalty = 0.0
            if trailing_avg > 0:
                ratio = row["arr"] / trailing_avg
                if ratio < 1:
                    penalty += _ramp_down(ratio, 0.70, 1.0, ARR_MOMENTUM_MAX)
                elif ratio > 1.08:
                    penalty -= min(5.0, (ratio - 1.08) * 20)

            if row.get("seat_utilisation_pct") is not None:
                penalty += _ramp_down(
                    row["seat_utilisation_pct"],
                    UTIL_TREND_BAD,
                    UTIL_TREND_CLEAN,
                    UTIL_TREND_MAX,
                )
            if row.get("active_user_pct") is not None:
                penalty += _ramp_down(
                    row["active_user_pct"],
                    ACTIVE_TREND_BAD,
                    ACTIVE_TREND_CLEAN,
                    ACTIVE_TREND_MAX,
                )
            if row.get("tickets_opened") is not None:
                penalty += _ramp_up(
                    row["tickets_opened"],
                    TICKET_TREND_CLEAN,
                    TICKET_TREND_BAD,
                    TICKET_TREND_MAX,
                )

            score = max(0.0, min(100.0, 100 - penalty))
            weight = max(row["arr"], 0.01)
            weighted_sum += score * weight
            weight_total += weight
        if weight_total:
            series.append({
                "month": month,
                "health": round(weighted_sum / weight_total, 1),
            })
    return series


def monthly_arr_movement(timeline_by_account):
    months = _months(timeline_by_account)
    values_by_month = {}
    for month in months:
        values_by_month[month] = {
            account_id: next(
                (row["arr"] for row in rows if row["month"] == month),
                None,
            )
            for account_id, rows in timeline_by_account.items()
        }

    movement = []
    for previous_month, month in zip(months, months[1:]):
        previous = values_by_month[previous_month]
        current = values_by_month[month]
        new_arr = expansion = contraction = churn = 0.0
        for account_id in set(previous) | set(current):
            before = previous.get(account_id)
            after = current.get(account_id)
            if before is None and after is not None and after > 0:
                new_arr += after
            elif before is not None and before > 0 and (after is None or after <= 0):
                churn += before
            elif before is not None and after is not None and after > before:
                expansion += after - before
            elif before is not None and after is not None and 0 < after < before:
                contraction += before - after
        movement.append({
            "month": month,
            "new": round(new_arr, 2),
            "expansion": round(expansion, 2),
            "contraction": round(-contraction, 2),
            "churn": round(-churn, 2),
            "net": round(new_arr + expansion - contraction - churn, 2),
        })
    return movement


def revenue_by_group(accounts, timeline_by_account):
    account_group = {
        account["account_id"]: {
            "segment": account["segment"],
            "industry": account["industry"],
        }
        for account in accounts
    }
    months = _months(timeline_by_account)

    def series_for(key):
        groups = sorted({group[key] for group in account_group.values()})
        series = {group: [0.0] * len(months) for group in groups}
        month_index = {month: index for index, month in enumerate(months)}
        for account_id, rows in timeline_by_account.items():
            group = account_group.get(account_id, {}).get(key)
            if group is None:
                continue
            for row in rows:
                series[group][month_index[row["month"]]] += row["arr"]
        return {
            group: [round(value, 2) for value in values]
            for group, values in series.items()
        }

    return {
        "labels": [month.strftime("%b %Y") for month in months],
        "by_segment": series_for("segment"),
        "by_industry": series_for("industry"),
    }
