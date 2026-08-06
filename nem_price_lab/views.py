from datetime import timedelta

from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncDate
from django.shortcuts import render

from . import forecasting as fc
from . import services
from .constants import (
    BAND_LABELS, NEM_REGION, NEM_TZ, REGION_LABELS, REGION_SHORT, TIME_BANDS,
)
from .models import ForecastRun, RegionPrice

# A round ninety days, stated as ninety. The fuel-mix page's ~92-day window
# is described as "three months"; here the number itself is on the label, so
# it should be the number a reader would expect.
DAYS_HISTORY = 90
DAYS_RECENT = 7

# How long each region stays on screen while auto-cycling. Slower than the
# fuel-mix dashboard's 6 seconds because this page carries more to read per
# region. Published to the template so the control can state its own speed
# rather than leaving the reader to time it.
CYCLE_SECONDS = 8

MODEL_COLORS = {
    fc.SEASONAL_NAIVE: '#b84a1a',     # terracotta: the baseline to beat
    fc.ROLLING_MEDIAN: '#3f7da6',     # cool blue: the free improvement
    fc.TEMP_ADJUSTED: '#2d6a2d',      # forest green: the hand-built model
    fc.RANDOM_FOREST: '#8e7cc3',      # violet: the first learned model
    fc.GRADIENT_BOOSTING: '#c2683a',  # burnt orange: the sharpest tree model
    fc.NEURAL_NETWORK: '#7a8b4a',     # olive: a different family entirely
}
ACTUAL_COLOR = '#1a2e1a'


def _headline_stats(region, latest):
    """Seven-day price character for one region.

    Average, range, and the share of intervals that cleared below zero.
    Negative prices are the single most counter-intuitive fact about the
    modern NEM, so they get their own number rather than being buried in
    an average that hides them.
    """
    window_start = latest - timedelta(days=DAYS_RECENT)
    aggregate = RegionPrice.objects.filter(
        region=region, interval_end__gt=window_start, interval_end__lte=latest
    ).aggregate(
        avg=Avg('rrp'),
        low=Min('rrp'),
        high=Max('rrp'),
        intervals=Count('id'),
        negative=Count('id', filter=Q(rrp__lt=0)),
        peak_demand=Max('total_demand'),
    )

    intervals = aggregate['intervals'] or 0
    return {
        'avg': round(aggregate['avg'], 2) if aggregate['avg'] is not None else None,
        'low': round(aggregate['low'], 2) if aggregate['low'] is not None else None,
        'high': round(aggregate['high'], 2) if aggregate['high'] is not None else None,
        'intervals': intervals,
        'negative_pct': round(aggregate['negative'] / intervals * 100, 1) if intervals else 0.0,
        'peak_demand': round(aggregate['peak_demand']) if aggregate['peak_demand'] is not None else None,
    }


def _history_series(region, latest):
    """Daily average, minimum and maximum price across the trend window."""
    start = latest - timedelta(days=DAYS_HISTORY)
    rows = (
        RegionPrice.objects
        .filter(region=region, interval_end__gt=start, interval_end__lte=latest)
        .annotate(day=TruncDate('interval_end', tzinfo=NEM_TZ))
        .values('day')
        .annotate(avg=Avg('rrp'), low=Min('rrp'), high=Max('rrp'))
        .order_by('day')
    )

    labels, avg, low, high = [], [], [], []
    for row in rows:
        labels.append(f"{row['day'].day} {row['day']:%b}")
        avg.append(round(row['avg'], 2))
        low.append(round(row['low'], 2))
        high.append(round(row['high'], 2))

    return {'labels': labels, 'avg': avg, 'low': low, 'high': high}


def _latest_origin(region):
    return (
        ForecastRun.objects
        .filter(region=region)
        .order_by('-issued_at')
        .values_list('issued_at', flat=True)
        .first()
    )


def _forecast_payload(region, origin):
    """The published week-ahead call, plus a week of context behind it.

    Actuals are included for any interval that has already cleared, so the
    chart shows the forecast being overtaken by reality in real time rather
    than waiting until the week is over.
    """
    runs = list(
        ForecastRun.objects.filter(region=region, issued_at=origin).prefetch_related('points')
    )
    if not runs:
        return None

    intervals = sorted({point.interval_end for run in runs for point in run.points.all()})
    if not intervals:
        return None

    context_start = origin - timedelta(days=DAYS_RECENT)
    actuals = services.price_map(region, context_start, intervals[-1])

    # A week of settled price before the origin gives the forecast somewhere
    # to start from visually, instead of a line beginning in mid-air.
    context = sorted(i for i in actuals if i <= origin)
    axis = context + intervals

    series = []
    for run in sorted(runs, key=lambda r: fc.MODEL_ORDER.index(r.model_key)
                      if r.model_key in fc.MODEL_ORDER else 99):
        predicted = dict(run.points.values_list('interval_end', 'predicted_rrp'))
        series.append({
            'key': run.model_key,
            'label': fc.MODEL_LABELS.get(run.model_key, run.model_key),
            'description': fc.MODEL_DESCRIPTIONS.get(run.model_key, ''),
            'color': MODEL_COLORS.get(run.model_key, '#5a6e52'),
            # None across the context window: these lines only exist ahead of the origin.
            'values': [None] * len(context) + [
                round(predicted[i], 2) if i in predicted else None for i in intervals
            ],
            'leakage_safe': run.is_leakage_safe,
            'temperature_source': run.temperature_source,
        })

    reference = runs[0]
    settled = [i for i in intervals if i in actuals]

    return {
        'issued_at': origin.astimezone(NEM_TZ).strftime('%d %b %Y'),
        'issued_at_iso': origin.isoformat(),
        'labels': [i.astimezone(NEM_TZ).strftime('%a %d %b %H:%M') for i in axis],
        'origin_index': len(context),
        'actual': [
            round(actuals[i], 2) if i in actuals else None for i in axis
        ],
        'actual_color': ACTUAL_COLOR,
        'series': series,
        'horizon_days': reference.horizon_days,
        'settled_intervals': len(settled),
        'total_intervals': len(intervals),
        'complete': len(settled) == len(intervals),
    }


def _performance_payload(region):
    """Last completed week and the running average across every week so far.

    Two horizons on purpose. One week can be won by luck; the running
    average is the number that carries weight as the archive grows, and it
    ships with the date it starts from so the reader can judge how much.
    """
    summary = services.performance_summary(region)
    if not summary:
        return None

    def pct(value):
        return round(value * 100, 1) if value is not None else None

    rows = []
    for row in summary['rows']:
        last = row['last_week']
        rows.append({
            'label': row['label'],
            'model_key': row['model_key'],
            'color': MODEL_COLORS.get(row['model_key'], '#5a6e52'),
            'is_baseline': row['model_key'] == fc.SEASONAL_NAIVE,
            'last_mae': round(last['mae'], 2) if last else None,
            'last_medae': round(last['medae'], 2) if last else None,
            'last_worst': round(last['max_error'], 2) if last else None,
            'last_skill': pct(row['last_week_skill']),
            'avg_mae': round(row['average_mae'], 2),
            'avg_medae': round(row['average_medae'], 2),
            'avg_skill': pct(row['average_skill']),
            'worst_ever': round(row['worst_ever'], 2),
            'weeks': row['weeks'],
            'leakage_safe': row['leakage_safe'],
        })

    latest = summary['latest_origin']
    horizon_end = latest + timedelta(days=7)
    return {
        'rows': rows,
        'last_week_from': latest.astimezone(NEM_TZ).strftime('%d %b %Y'),
        'last_week_to': horizon_end.astimezone(NEM_TZ).strftime('%d %b %Y'),
        'average_since': summary['first_origin'].astimezone(NEM_TZ).strftime('%d %b %Y'),
        'weeks': summary['weeks'],
    }


def _model_cards(region, performance):
    """One card per model: what it is, what it eats, how it is doing.

    Built per region because the ranking genuinely differs between them.
    A model that wins in South Australia can lose in Tasmania, and showing a
    single global ordering would hide exactly that.
    """
    scores = {row['model_key']: row for row in (performance['rows'] if performance else [])}

    ranked = sorted(
        (row for row in scores.values() if row['avg_skill'] is not None
         and row['model_key'] != fc.SEASONAL_NAIVE),
        key=lambda row: row['avg_skill'],
        reverse=True,
    )
    best = ranked[0]['model_key'] if ranked else None

    cards = []
    for key in fc.MODEL_ORDER:
        row = scores.get(key)
        cards.append({
            'key': key,
            'label': fc.MODEL_LABELS[key],
            'family': fc.MODEL_FAMILIES[key],
            'inputs': fc.MODEL_INPUTS[key],
            'fitted': fc.MODEL_FITTED[key],
            'description': fc.MODEL_DESCRIPTIONS[key],
            'color': MODEL_COLORS.get(key, '#5a6e52'),
            'is_baseline': key == fc.SEASONAL_NAIVE,
            'is_best': key == best,
            'needs_training': key in fc.TREE_MODELS,
            'avg_mae': row['avg_mae'] if row else None,
            'avg_skill': row['avg_skill'] if row else None,
            'weeks': row['weeks'] if row else 0,
        })
    return cards


def _beta_payload(region, origin):
    """The fitted dollars-per-degree table, exactly as the model used it."""
    run = ForecastRun.objects.filter(
        region=region, model_key=fc.TEMP_ADJUSTED, issued_at=origin
    ).first()
    if not run:
        return None

    betas = (run.parameters or {}).get('betas') or {}
    diagnostics = (run.parameters or {}).get('diagnostics') or {}
    if not betas:
        return None

    rows = []
    for band in TIME_BANDS:
        key = band['key']
        diagnostic = diagnostics.get(key, {})
        coefficients = betas.get(key) or {}
        rows.append({
            'label': BAND_LABELS.get(key, key),
            'note': band['note'],
            'hours': f"{band['hours'][0]:02d}:00-{band['hours'][1]:02d}:59",
            'cooling': coefficients.get('cooling'),
            'heating': coefficients.get('heating'),
            'samples': diagnostic.get('samples', 0),
            'used': diagnostic.get('used', 0),
            'fitted': diagnostic.get('fitted', False),
            'reason': diagnostic.get('reason', ''),
        })
    # Paired series for the coefficient chart: the shape of the response
    # across the day is the point, and a table alone hides it.
    return {
        'rows': rows,
        'chart': {
            'labels': [row['label'] for row in rows],
            'cooling': [row['cooling'] if row['fitted'] else 0.0 for row in rows],
            'heating': [row['heating'] if row['fitted'] else 0.0 for row in rows],
            'cooling_color': '#b84a1a',
            'heating_color': '#3f7da6',
        },
        'training_weeks': (run.parameters or {}).get('training_weeks'),
        'comfort_base_c': (run.parameters or {}).get('comfort_base_c', fc.COMFORT_BASE_C),
        'temperature_source': run.temperature_source,
        'leakage_safe': run.is_leakage_safe,
    }


def lab(request):
    regions = services.available_regions()

    if not regions:
        return render(request, 'nem_price_lab/lab.html', {
            'has_data': False,
            'region_order': [],
            'region_pills': [],
            'regions_json': {},
            'default_region': '',
            'auto_cycle': False,
        })

    payload = {}
    for region in regions:
        latest = services.latest_interval(region)
        origin = _latest_origin(region)
        performance = _performance_payload(region)
        payload[region] = {
            'label': REGION_LABELS.get(region, region),
            'short': REGION_SHORT.get(region, region),
            'derived': region == NEM_REGION,
            'latest': latest.astimezone(NEM_TZ).strftime('%d %b %Y %H:%M') if latest else None,
            'stats': _headline_stats(region, latest) if latest else None,
            'history': _history_series(region, latest) if latest else None,
            'forecast': _forecast_payload(region, origin) if origin else None,
            'performance': performance,
            'models': _model_cards(region, performance),
            'betas': _beta_payload(region, origin) if origin else None,
        }

    # The market-wide view is the default, matching the fuel-mix dashboard.
    # An explicit ?region= pins that region and suppresses the auto-cycle.
    pinned = request.GET.get('region', '')
    default_region = pinned if pinned in payload else (
        NEM_REGION if NEM_REGION in payload else regions[0]
    )

    return render(request, 'nem_price_lab/lab.html', {
        'has_data': True,
        'has_forecast': any(entry['forecast'] for entry in payload.values()),
        'region_order': regions,
        'region_pills': [
            {
                'code': region,
                'short': REGION_SHORT.get(region, region),
                'label': REGION_LABELS.get(region, region),
            }
            for region in regions
        ],
        'cycle_seconds': CYCLE_SECONDS,
        'regions_json': payload,
        'default_region': default_region,
        'auto_cycle': not pinned,
        'model_order': [
            {
                'key': key,
                'label': fc.MODEL_LABELS[key],
                'description': fc.MODEL_DESCRIPTIONS[key],
                'color': MODEL_COLORS.get(key, '#5a6e52'),
                # The chart opens with the baseline and the temperature model
                # only. Three lines at once was unreadable; the rest are a
                # click away rather than always on.
                'default_on': key in (fc.SEASONAL_NAIVE, fc.TEMP_ADJUSTED),
                'is_baseline': key == fc.SEASONAL_NAIVE,
            }
            for key in fc.MODEL_ORDER
        ],
        'history_days': DAYS_HISTORY,
    })
