from datetime import timedelta
from collections import defaultdict

from django.shortcuts import render
from django.db.models import Sum, Max
from django.utils.timezone import localtime

from .models import FuelGenerationData

# ── Fuel reference data ──────────────────────────────────────────────
# Muted, editorial palette that sits with the site's austro-indo-french look
# while keeping each fuel recognisable (coal dark, solar gold, wind/hydro cool).
FUEL_METADATA = [
    {"fuel": "Black coal",  "icon": "🪨", "color": "#2b2b2b"},
    {"fuel": "Brown coal",  "icon": "⛏️", "color": "#6b4a2b"},
    {"fuel": "Gas",         "icon": "🔥", "color": "#b07b46"},
    {"fuel": "Liquid Fuel", "icon": "🛢️", "color": "#c2683a"},
    {"fuel": "Hydro",       "icon": "🌊", "color": "#3f7da6"},
    {"fuel": "Wind",        "icon": "🌬️", "color": "#5a9e5a"},
    {"fuel": "Solar",       "icon": "☀️", "color": "#e0a82e"},
    {"fuel": "Battery",     "icon": "🔋", "color": "#8e7cc3"},
    {"fuel": "Biomass",     "icon": "🌿", "color": "#7a8b4a"},
    {"fuel": "Other",       "icon": "⚡", "color": "#9a9488"},
]
FUEL_ORDER = [m["fuel"] for m in FUEL_METADATA]

# ── Higher-level groups for the headline breakdown ───────────────────
# Every fuel maps to exactly one group, so there is no residual "Other":
#   - Biomass counts as renewable (organic generation).
#   - Battery is treated as storage, NOT renewable (it discharges stored energy).
#   - Liquid Fuel and the literal "Other" fuel fold into Gas (dispatchable fossil).
GROUP_DEFS = [
    {"key": "Coal",       "label": "Coal",            "color": "#2b2b2b",
     "fuels": ["Black coal", "Brown coal"]},
    {"key": "Gas",        "label": "Gas",             "color": "#b07b46",
     "fuels": ["Gas", "Liquid Fuel", "Other"]},
    {"key": "Renewables", "label": "Renewables",      "color": "#5a9e5a",
     "fuels": ["Wind", "Solar", "Hydro", "Biomass"]},
    {"key": "Storage",    "label": "Battery storage", "color": "#8e7cc3",
     "fuels": ["Battery"]},
]
GROUP_META = [{"key": g["key"], "label": g["label"], "color": g["color"]} for g in GROUP_DEFS]

# Display order for the region selector / auto-cycle.
STATE_ORDER = ["NSW", "QLD", "VIC", "SA", "TAS"]

# Classification for the renewable-vs-fossil line graph (battery/storage excluded).
RENEWABLE_FUELS = {"Wind", "Solar", "Hydro", "Biomass"}
FOSSIL_FUELS = {"Black coal", "Brown coal", "Gas", "Liquid Fuel", "Other"}

DAYS_MIX = 7      # the headline breakdown sums this many recent days
DAYS_TREND = 92   # the line graph spans roughly three months


def _fuel_mix(queryset, range_label):
    """Build a fuel-mix payload by summing supply across the given queryset."""
    aggregated = queryset.values("fuel_type").annotate(total=Sum("supply_mw"))
    lookup = {row["fuel_type"]: (row["total"] or 0.0) for row in aggregated}

    total = sum(max(v, 0.0) for v in lookup.values())
    pct = lambda mw: round(mw / total * 100, 1) if total else 0.0

    # Per-fuel values (nonzero only) keyed by fuel name.
    fuels = {}
    for fuel in FUEL_ORDER:
        mw = lookup.get(fuel, 0.0) or 0.0
        if mw > 0:
            fuels[fuel] = {"mw": round(mw, 1), "pct": pct(mw)}

    # Grouped breakdown — always include all groups so segments stay stable.
    groups = {}
    for g in GROUP_DEFS:
        mw = sum(max(lookup.get(f, 0.0) or 0.0, 0.0) for f in g["fuels"])
        groups[g["key"]] = {"mw": round(mw, 1), "pct": pct(mw)}

    return {
        "total_mw": round(total, 1),
        "range": range_label,
        "renewable_pct": groups["Renewables"]["pct"],
        "coal_pct": groups["Coal"]["pct"],
        "groups": groups,
        "fuels": fuels,
    }


def _build_trend(rows, regions):
    """Daily renewable vs non-renewable totals per region over the trend window."""
    # region -> date(str) -> [renewable_mw, fossil_mw]
    buckets = {r: defaultdict(lambda: [0.0, 0.0]) for r in regions}
    for row in rows:
        fuel = row["fuel_type"]
        if fuel in RENEWABLE_FUELS:
            idx = 0
        elif fuel in FOSSIL_FUELS:
            idx = 1
        else:
            continue  # battery / storage excluded
        mw = row["supply_mw"] or 0.0
        day = localtime(row["timestamp"]).strftime("%Y-%m-%d")
        buckets["NEM"][day][idx] += mw
        state = row["state"]
        if state in buckets:
            buckets[state][day][idx] += mw

    series = {}
    for region in regions:
        days = sorted(buckets[region].keys())
        labels = [_day_label(d) for d in days]
        series[region] = {
            "labels": labels,
            "renewable": [round(buckets[region][d][0]) for d in days],
            "nonrenewable": [round(buckets[region][d][1]) for d in days],
        }
    return series


def _day_label(iso_day):
    from datetime import datetime
    dt = datetime.strptime(iso_day, "%Y-%m-%d")
    return f"{dt.day} {dt.strftime('%b')}"


def dashboard(request):
    all_data = FuelGenerationData.objects.all()

    if not all_data.exists():
        return render(request, "nem_dashboard/dashboard.html", {
            "has_data": False,
            "region_order": ["NEM"],
            "regions_json": {},
            "trend_json": {},
            "default_region": "NEM",
        })

    latest = all_data.aggregate(m=Max("timestamp"))["m"]
    mix_start = latest - timedelta(days=DAYS_MIX)
    trend_start = latest - timedelta(days=DAYS_TREND)

    last7 = all_data.filter(timestamp__gt=mix_start)
    mix_label = "Last 7 days · to " + localtime(latest).strftime("%d %b %Y")

    available_states = [s for s in STATE_ORDER if all_data.filter(state=s).exists()]
    region_order = ["NEM"] + available_states

    # ── Headline mix: summed over the last 7 days ──
    regions = {"NEM": _fuel_mix(last7, mix_label)}
    for state in available_states:
        regions[state] = _fuel_mix(last7.filter(state=state), mix_label)

    # ── Trend: renewable vs fossil daily totals over ~3 months ──
    trend_rows = all_data.filter(timestamp__gt=trend_start).values(
        "timestamp", "state", "fuel_type", "supply_mw"
    )
    trend = _build_trend(list(trend_rows), region_order)

    # Canonical fuel list for the detailed bars: any fuel nonzero in any region.
    fuel_meta = [
        m for m in FUEL_METADATA
        if any(m["fuel"] in regions[r]["fuels"] for r in region_order)
    ]

    default_region = request.GET.get("state", "NEM")
    if default_region not in regions:
        default_region = "NEM"

    return render(request, "nem_dashboard/dashboard.html", {
        "has_data": True,
        "regions_json": regions,
        "trend_json": trend,
        "region_order": region_order,
        "group_meta": GROUP_META,
        "fuel_meta": fuel_meta,
        "default_region": default_region,
        "trend_label": "Last 3 months · daily generation",
    })
