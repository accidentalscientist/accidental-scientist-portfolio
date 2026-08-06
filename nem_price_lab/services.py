"""Database-facing orchestration: storing observations and producing runs.

`forecasting.py` holds the maths and knows nothing about Django;
`ingest.py` holds the parsing and knows nothing about the ORM. This module
is where those two meet the database, and it is the only place that should
need both.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Sum

from . import forecasting as fc
from . import ingest
from .constants import DISPLAY_REGIONS, INTERVALS_PER_DAY, NEM_REGION, NEM_TZ, REGIONS
from .models import ForecastPoint, ForecastRun, RegionPrice, RegionWeather

WEEK = timedelta(days=7)


# ── Storing observations ──────────────────────────────────────────────

@transaction.atomic
def upsert_prices(rows):
    """Insert or refresh 30-minute price intervals.

    Conflicts are resolved on (region, interval_end) rather than deleted and
    re-inserted. A delete-then-insert keyed on timestamp alone would wipe
    other regions sharing that timestamp, which is a real hazard when a
    single-region file is uploaded.
    """
    if not rows:
        return 0

    RegionPrice.objects.bulk_create(
        [RegionPrice(**row) for row in rows],
        update_conflicts=True,
        update_fields=['rrp', 'total_demand'],
        unique_fields=['region', 'interval_end'],
        batch_size=2000,
    )
    return len(rows)


@transaction.atomic
def upsert_weather(region, kind, temperatures):
    """Insert or refresh temperatures for one region and one kind."""
    if not temperatures:
        return 0

    RegionWeather.objects.bulk_create(
        [
            RegionWeather(region=region, kind=kind, interval_end=interval_end, temperature_c=value)
            for interval_end, value in sorted(temperatures.items())
        ],
        update_conflicts=True,
        update_fields=['temperature_c'],
        unique_fields=['region', 'interval_end', 'kind'],
        batch_size=2000,
    )
    return len(temperatures)


# ── Reading observations back ─────────────────────────────────────────

def price_map(region, start=None, end=None):
    """{interval_end: rrp} for a region, optionally bounded."""
    queryset = RegionPrice.objects.filter(region=region)
    if start is not None:
        queryset = queryset.filter(interval_end__gt=start)
    if end is not None:
        queryset = queryset.filter(interval_end__lte=end)
    return dict(queryset.values_list('interval_end', 'rrp'))


def demand_map(region, start=None, end=None):
    queryset = RegionPrice.objects.filter(region=region)
    if start is not None:
        queryset = queryset.filter(interval_end__gt=start)
    if end is not None:
        queryset = queryset.filter(interval_end__lte=end)
    return dict(queryset.values_list('interval_end', 'total_demand'))


def weather_map(region, kind, start=None, end=None):
    queryset = RegionWeather.objects.filter(region=region, kind=kind)
    if start is not None:
        queryset = queryset.filter(interval_end__gt=start)
    if end is not None:
        queryset = queryset.filter(interval_end__lte=end)
    return dict(queryset.values_list('interval_end', 'temperature_c'))


def latest_interval(region=None):
    queryset = RegionPrice.objects.all()
    if region:
        queryset = queryset.filter(region=region)
    return queryset.order_by('-interval_end').values_list('interval_end', flat=True).first()


def available_regions():
    """Regions holding data, NEM first, then the settled regions in order."""
    present = set(RegionPrice.objects.values_list('region', flat=True).distinct())
    return [region for region in DISPLAY_REGIONS if region in present]


# ── The derived NEM-wide series ───────────────────────────────────────

def average_demand_shares():
    """Each region's long-run share of total NEM demand.

    Used to weight intervals that have no settled demand of their own, which
    is every interval in the forecast week. Without this the market-wide
    temperature forecast would be empty exactly when it is needed.
    """
    totals = dict(
        RegionPrice.objects.exclude(region=NEM_REGION)
        .values_list('region')
        .annotate(total=Sum('total_demand'))
        .values_list('region', 'total')
    )
    grand = sum(totals.values())
    if not grand:
        return {}
    return {region: total / grand for region, total in totals.items()}


@transaction.atomic
def rebuild_nem_aggregate():
    """Recompute the market-wide price and temperature series.

    Price is demand-weighted across whichever regions reported an interval,
    because the meaningful market-wide number is what was paid per MWh
    actually consumed. Demand is summed. Temperature is weighted the same
    way, so aggregate weather lines up with aggregate load rather than
    treating Hobart and Sydney as equally important.

    Intervals where only some regions reported are still aggregated over the
    regions present. Waiting for all five would leave gaps at the live edge,
    where regional files update at slightly different times.
    """
    RegionPrice.objects.filter(region=NEM_REGION).delete()
    RegionWeather.objects.filter(region=NEM_REGION).delete()

    # ── Price: weight by the demand actually settled in that interval ──
    interval_weights = {}
    prices = {}
    for region, interval_end, rrp, demand in (
        RegionPrice.objects.exclude(region=NEM_REGION)
        .values_list('region', 'interval_end', 'rrp', 'total_demand')
    ):
        interval_weights[(region, interval_end)] = demand
        weighted, total = prices.setdefault(interval_end, [0.0, 0.0])
        prices[interval_end] = [weighted + rrp * demand, total + demand]

    price_rows = [
        {
            'region': NEM_REGION,
            'interval_end': interval_end,
            'rrp': weighted / total,
            'total_demand': total,
        }
        for interval_end, (weighted, total) in prices.items()
        if total
    ]
    upsert_prices(price_rows)

    # ── Temperature: same weighting, falling back to long-run shares ──
    # Future intervals have no settled demand, so the forecast week would
    # otherwise aggregate to nothing.
    shares = average_demand_shares()
    stored_weather = 0

    for kind in (RegionWeather.OBSERVED, RegionWeather.FORECAST):
        buckets = {}
        for region, interval_end, temperature in (
            RegionWeather.objects.filter(kind=kind).exclude(region=NEM_REGION)
            .values_list('region', 'interval_end', 'temperature_c')
        ):
            weight = interval_weights.get((region, interval_end))
            if weight is None:
                weight = shares.get(region, 0.0)
            if not weight:
                continue
            weighted, total = buckets.setdefault(interval_end, [0.0, 0.0])
            buckets[interval_end] = [weighted + temperature * weight, total + weight]

        stored_weather += upsert_weather(NEM_REGION, kind, {
            interval_end: weighted / total
            for interval_end, (weighted, total) in buckets.items()
            if total
        })

    return len(price_rows), stored_weather


def most_recent_sunday(moment):
    """The most recent Sunday-midnight boundary at or before `moment`.

    Forecast origins are pinned to Sunday 00:00 NEM time so a run always
    covers whole calendar weeks. Monday is weekday 0, so Sunday is 6 and
    the offset lands on the Sunday that has already started.
    """
    local = moment.astimezone(NEM_TZ)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight - timedelta(days=(local.weekday() + 1) % 7)


# ── Producing forecasts ───────────────────────────────────────────────

def reference_temperatures(region, start, origin):
    """Temperature for intervals the forecaster could already look back on.

    Reanalysis is authoritative but lags real time by several days, which
    leaves the most recent week of history empty exactly when a week-on-week
    model needs it. Archived forecasts fill those gaps: for an interval that
    ended before the origin, the forecast issued for it was on the desk at
    the origin, so using it is conservative rather than leaky.

    Observed always wins where it exists. The fallback only ever covers the
    tail, and everything is bounded at the origin.
    """
    filled = weather_map(region, RegionWeather.FORECAST, start, origin)
    filled.update(weather_map(region, RegionWeather.OBSERVED, start, origin))
    return filled


def _resolve_target_temperatures(region, origin, horizon_days):
    """Temperatures for the week being predicted, plus how we got them.

    Prefers genuine forecast rows. Falls back to observed only when no
    forecast vintage was stored, and says so loudly in the returned source
    so the run is labelled as optimistic rather than passing as clean.
    """
    horizon_end = origin + timedelta(days=horizon_days)

    forecast = weather_map(region, RegionWeather.FORECAST, origin, horizon_end)
    if forecast:
        return forecast, ForecastRun.SOURCE_FORECAST

    observed = weather_map(region, RegionWeather.OBSERVED, origin, horizon_end)
    if observed:
        return observed, ForecastRun.SOURCE_OBSERVED_FALLBACK

    return {}, ForecastRun.SOURCE_NONE


def build_forecasts(region, origin, horizon_days=7, training_weeks=52):
    """Run all three models for one region and origin.

    Every input is filtered to `interval_end <= origin` before it reaches a
    model. That single rule is the whole leakage story at this horizon, and
    it is enforced here rather than trusted to each model.
    """
    training_start = origin - timedelta(weeks=training_weeks)

    history = price_map(region, training_start, origin)
    observed_temps = reference_temperatures(region, training_start, origin)
    target_temps, temp_source = _resolve_target_temperatures(region, origin, horizon_days)

    betas, diagnostics = fit_or_empty(history, observed_temps)

    results = {
        fc.SEASONAL_NAIVE: {
            'predictions': fc.seasonal_naive(history, origin, horizon_days),
            'temperature_source': ForecastRun.SOURCE_NONE,
            'parameters': {},
        },
        fc.ROLLING_MEDIAN: {
            'predictions': fc.rolling_median(history, origin, horizon_days),
            'temperature_source': ForecastRun.SOURCE_NONE,
            'parameters': {'weeks': 4},
        },
        fc.TEMP_ADJUSTED: {
            'predictions': fc.temperature_adjusted(
                history, observed_temps, target_temps, betas, origin, horizon_days
            ),
            'temperature_source': temp_source,
            'parameters': {
                'betas': {
                    band: {
                        'cooling': round(value.get('cooling', 0.0), 3),
                        'heating': round(value.get('heating', 0.0), 3),
                    }
                    for band, value in betas.items()
                },
                'diagnostics': diagnostics,
                'training_weeks': training_weeks,
                'comfort_base_c': fc.COMFORT_BASE_C,
            },
        },
    }

    results.update(_tree_forecasts(
        region, origin, horizon_days, training_weeks,
        history, observed_temps, target_temps, temp_source, training_start,
    ))
    return results


def _tree_forecasts(region, origin, horizon_days, training_weeks,
                    history, observed_temps, target_temps, temp_source, training_start):
    """Random forest and gradient boosting, when scikit-learn is present.

    Absent scikit-learn these are skipped silently rather than raising: the
    web server never has the dependency installed, and the rest of the lab
    must keep working without it.
    """
    from . import tree_models

    if not tree_models.sklearn_available():
        return {}

    demands = demand_map(region, training_start, origin)
    targets = fc.target_intervals(origin, horizon_days)

    out = {}
    for model_key in tree_models.LEARNED_MODELS:
        predictions, diagnostics = tree_models.fit_and_predict(
            model_key, history, observed_temps, demands, targets, origin,
            target_temps, training_weeks,
        )
        out[model_key] = {
            'predictions': predictions,
            # These models consume forecast temperature as a feature, so they
            # inherit exactly the same caveat as the temperature model.
            'temperature_source': temp_source if predictions else ForecastRun.SOURCE_NONE,
            'parameters': diagnostics,
        }
    return out


def fit_or_empty(history, observed_temps):
    """Fit temperature coefficients, tolerating a cold start with no weather."""
    if not history or not observed_temps:
        return {}, {}
    return fc.fit_temperature_betas(history, observed_temps)


@transaction.atomic
def save_forecast_run(region, model_key, origin, result, horizon_days=7, notes=''):
    """Persist one model's run, replacing any earlier run for the same origin."""
    ForecastRun.objects.filter(region=region, model_key=model_key, issued_at=origin).delete()

    run = ForecastRun.objects.create(
        region=region,
        model_key=model_key,
        issued_at=origin,
        horizon_days=horizon_days,
        temperature_source=result['temperature_source'],
        parameters=result.get('parameters', {}),
        notes=notes,
    )
    ForecastPoint.objects.bulk_create(
        [
            ForecastPoint(run=run, interval_end=interval_end, predicted_rrp=value)
            for interval_end, value in sorted(result['predictions'].items())
        ],
        batch_size=2000,
    )
    return run


def generate_and_save(region, origin, horizon_days=7, training_weeks=52):
    results = build_forecasts(region, origin, horizon_days, training_weeks)
    return [
        save_forecast_run(region, model_key, origin, result, horizon_days)
        for model_key, result in results.items()
    ]


# ── Scoring past runs ─────────────────────────────────────────────────

def score_run(run):
    """Compare a stored run against what actually cleared.

    Returns None while the target week is still in the future, which is the
    honest answer rather than a partial score dressed up as a final one.
    """
    predictions = dict(run.points.values_list('interval_end', 'predicted_rrp'))
    if not predictions:
        return None
    actuals = price_map(run.region, min(predictions) - fc.INTERVAL, max(predictions))
    return fc.score(predictions, actuals)


def completed_origins(region, limit=None):
    """Origins whose whole forecast week has settled, newest first.

    A week still in progress is excluded. Scoring a partial week produces a
    number that changes every day and flatters whichever model happens to
    suit the first few days of it.
    """
    latest = latest_interval(region)
    if latest is None:
        return []

    origins = []
    seen = (
        ForecastRun.objects.filter(region=region)
        .order_by('-issued_at')
        .values_list('issued_at', 'horizon_days')
        .distinct()
    )
    for issued_at, horizon_days in seen:
        if issued_at + timedelta(days=horizon_days) <= latest:
            origins.append(issued_at)
            if limit and len(origins) >= limit:
                break
    return origins


def performance_summary(region):
    """Last completed week, plus the running average over every week so far.

    The running average is the number that actually matters as the archive
    grows: one week can be won by luck, a season cannot. It carries the date
    it runs from and the number of weeks behind it, so the reader can judge
    how much weight it deserves.
    """
    origins = completed_origins(region)
    if not origins:
        return None

    # model_key -> accumulated errors across every completed origin
    totals = {}
    latest_scores = {}

    for index, origin in enumerate(origins):
        for entry in review_origin(region, origin):
            result = entry['score']
            if not result:
                continue
            bucket = totals.setdefault(entry['model_key'], {
                'label': entry['label'],
                'mae_sum': 0.0, 'medae_sum': 0.0, 'worst': 0.0,
                'weeks': 0, 'leakage_safe': True,
            })
            bucket['mae_sum'] += result['mae']
            bucket['medae_sum'] += result['medae']
            bucket['worst'] = max(bucket['worst'], result['max_error'])
            bucket['weeks'] += 1
            bucket['leakage_safe'] = bucket['leakage_safe'] and entry['leakage_safe']

            if index == 0:
                latest_scores[entry['model_key']] = entry

    baseline_average = totals.get(fc.SEASONAL_NAIVE)
    rows = []
    for model_key in fc.MODEL_ORDER:
        bucket = totals.get(model_key)
        if not bucket or not bucket['weeks']:
            continue

        average_mae = bucket['mae_sum'] / bucket['weeks']
        average_skill = None
        if baseline_average and baseline_average['weeks']:
            baseline_mae = baseline_average['mae_sum'] / baseline_average['weeks']
            if baseline_mae:
                average_skill = 1.0 - (average_mae / baseline_mae)

        latest = latest_scores.get(model_key)
        rows.append({
            'model_key': model_key,
            'label': bucket['label'],
            'last_week': latest['score'] if latest else None,
            'last_week_skill': latest['skill'] if latest else None,
            'average_mae': average_mae,
            'average_medae': bucket['medae_sum'] / bucket['weeks'],
            'average_skill': average_skill,
            'worst_ever': bucket['worst'],
            'weeks': bucket['weeks'],
            'leakage_safe': bucket['leakage_safe'],
        })

    return {
        'rows': rows,
        'latest_origin': origins[0],
        'first_origin': origins[-1],
        'weeks': len(origins),
    }


def review_origin(region, origin):
    """The weekly review: every model's run for one origin, scored and ranked.

    This is what makes the Sunday cycle self-documenting. Each week's runs
    stay in the database, so the following week the same call returns how
    they actually did without anyone having to record it by hand.
    """
    runs = ForecastRun.objects.filter(region=region, issued_at=origin).prefetch_related('points')
    scored = []
    baseline = None

    for run in runs:
        result = score_run(run)
        entry = {
            'run': run,
            'model_key': run.model_key,
            'label': fc.MODEL_LABELS.get(run.model_key, run.model_key),
            'score': result,
            'leakage_safe': run.is_leakage_safe,
        }
        if run.model_key == fc.SEASONAL_NAIVE:
            baseline = result
        scored.append(entry)

    for entry in scored:
        entry['skill'] = fc.skill(entry['score'], baseline)

    order = {key: index for index, key in enumerate(fc.MODEL_ORDER)}
    scored.sort(key=lambda e: order.get(e['model_key'], 99))
    return scored


# ── Convenience used by the management commands ───────────────────────

def ingest_month(region, month):
    text = ingest.fetch_price_csv(region, month)
    rows, report = ingest.parse_price_csv(text)
    stored = upsert_prices(rows)
    report['stored'] = stored
    return report


def ingest_weather_window(region, start, end, kind):
    if kind == RegionWeather.OBSERVED:
        temperatures = ingest.fetch_observed_temperature(region, start, end)
    else:
        temperatures = ingest.fetch_historical_forecast_temperature(region, start, end)
    return upsert_weather(region, kind, temperatures)


def ingest_forward_weather(region, days=7):
    temperatures = ingest.fetch_forecast_temperature(region, days=days)
    return upsert_weather(region, RegionWeather.FORECAST, temperatures)


__all__ = [
    'upsert_prices', 'upsert_weather',
    'price_map', 'demand_map', 'weather_map', 'latest_interval', 'available_regions',
    'rebuild_nem_aggregate', 'average_demand_shares',
    'most_recent_sunday', 'build_forecasts', 'save_forecast_run', 'generate_and_save',
    'score_run', 'review_origin', 'completed_origins', 'performance_summary',
    'reference_temperatures',
    'ingest_month', 'ingest_weather_window', 'ingest_forward_weather',
    'INTERVALS_PER_DAY',
]
