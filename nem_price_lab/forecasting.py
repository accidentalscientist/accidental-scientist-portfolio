"""Forecast models for the Price Predictor Lab.

This module is deliberately dependency-free: plain Python over dicts keyed
by interval-end datetime. No numpy, no scikit-learn, no Django. Two reasons:

1.  The site's dependency list was trimmed from 69 packages to 15 on
    purpose, and the web server must keep working without an ML stack.
2.  Every number these models publish should be hand-checkable. A model a
    reader can recompute in a spreadsheet is worth more here than a black
    box with a better score.

The three learned models (random forest, gradient boosting, neural network)
live in `tree_models.py` behind a soft scikit-learn import, and are trained
offline. This module owns the registry that names all six.

The ladder, cheapest first:

    seasonal_naive     what happened at this same half hour last week
    rolling_median     the median of the last four weeks at this half hour
    temp_adjusted      last week, nudged by the change in temperature
    random_forest      averaged trees over price, calendar and weather
    gradient_boosting  trees fitted in sequence on each other's residuals
    neural_network     a smooth surface over the same standardised features

Each rung must beat the ones below it to justify existing. If none of them
beat the two free baselines, that is a result worth publishing, not a
failure to hide.
"""

from datetime import timedelta
from statistics import median

from .constants import (
    BAND_BY_HOUR,
    INTERVALS_PER_DAY,
    INTERVALS_PER_WEEK,
    MARKET_PRICE_FLOOR,
    MINUTES_PER_INTERVAL,
    NEM_TZ,
)

WEEK = timedelta(days=7)
INTERVAL = timedelta(minutes=MINUTES_PER_INTERVAL)

# Below this many usable observations a band's coefficient is not fitted at
# all; it is pinned to zero so the model quietly degrades to seasonal naive
# rather than inventing a slope from noise.
MIN_SAMPLES_PER_BAND = 40

# Week-on-week price differences are violently heavy-tailed: a single $15,000
# spike would otherwise set the coefficient by itself. Fitting is done on the
# central 96% of differences within each band.
TRIM_PERCENTILE = 2.0

# The temperature at which a building needs neither heating nor cooling. 18C
# is the long-standing degree-day convention in Australia and internationally,
# used here rather than tuned so the split stays a stated assumption instead
# of another fitted parameter.
COMFORT_BASE_C = 18.0


# ── Time helpers ──────────────────────────────────────────────────────
# AEMO labels an interval by its END, so the half hour stamped 00:00 covers
# 23:30-00:00 of the *previous* day. Every calendar question below is
# therefore asked of the interval's start, never its end.

def interval_start(interval_end):
    """The start of an interval, expressed in NEM market time.

    The conversion is the important half of this function. Django stores and
    returns datetimes in UTC, so reading `.hour` off a value straight from
    the database gives the UTC hour: an interval that is 00:30 on Tuesday in
    the market is 14:30 on Monday in UTC. Every calendar-derived feature
    (time of day, day of week, month, and the time-of-day band) silently
    shifts by ten hours without this, which puts the evening peak's
    coefficients on pre-dawn data.
    """
    return (interval_end - INTERVAL).astimezone(NEM_TZ)


def week_slot(interval_end):
    """Position in the weekly cycle, 0-335, Monday 00:00-00:30 being 0."""
    start = interval_start(interval_end)
    return start.weekday() * INTERVALS_PER_DAY + start.hour * 2 + start.minute // MINUTES_PER_INTERVAL


def band_for(interval_end):
    """Which time-of-day band this interval belongs to."""
    return BAND_BY_HOUR[interval_start(interval_end).hour]


def target_intervals(origin, horizon_days):
    """The intervals a run issued at `origin` is responsible for predicting.

    The first target ends one interval after the origin, so nothing the run
    predicts overlaps data it was allowed to see.
    """
    count = horizon_days * INTERVALS_PER_DAY
    return [origin + INTERVAL * (i + 1) for i in range(count)]


def clamp(price):
    """Hold predictions at the market price floor.

    Only the floor is applied. The market price cap is indexed annually, so
    hardcoding a number here would rot; it belongs in AEMO's
    MARKET_PRICE_THRESHOLDS table. At a seven-day horizon these models never
    come close to it anyway.
    """
    return max(price, MARKET_PRICE_FLOOR)


# ── Small statistics helpers ──────────────────────────────────────────

def percentile(values, pct):
    """Linear-interpolated percentile. Safe on tiny and single-value inputs."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def slope_through_origin(pairs):
    """Least-squares slope with the intercept pinned at zero.

    No intercept is the whole point: when next week's temperature matches
    last week's, the model must return exactly the seasonal-naive answer.
    An intercept would let it drift away from that baseline for free.
    """
    sxx = sum(x * x for x, _ in pairs)
    if sxx == 0:
        return 0.0
    sxy = sum(x * y for x, y in pairs)
    return sxy / sxx


def two_slopes_through_origin(triples):
    """Two-variable least squares, both intercepts pinned at zero.

    Solves the 2x2 normal equations directly. With only two predictors that
    is a handful of sums and a determinant, which keeps the whole fit
    something a reader can reproduce in a spreadsheet.

    `triples` are (x1, x2, y). Returns (a, b) for y ~ a*x1 + b*x2.
    """
    s11 = sum(x1 * x1 for x1, _, _ in triples)
    s22 = sum(x2 * x2 for _, x2, _ in triples)
    s12 = sum(x1 * x2 for x1, x2, _ in triples)
    s1y = sum(x1 * y for x1, _, y in triples)
    s2y = sum(x2 * y for _, x2, y in triples)

    determinant = s11 * s22 - s12 * s12
    if determinant == 0:
        # The two predictors are collinear here, which happens when a band
        # only ever saw one side of the comfort band. Fall back to whichever
        # predictor actually varies rather than inventing a joint fit.
        if s11:
            return s1y / s11, 0.0
        if s22:
            return 0.0, s2y / s22
        return 0.0, 0.0

    return (
        (s1y * s22 - s2y * s12) / determinant,
        (s2y * s11 - s1y * s12) / determinant,
    )


# ── Baseline 1: seasonal naive ────────────────────────────────────────

def seasonal_naive(prices, origin, horizon_days=7):
    """Whatever the price was at this same half hour, one week ago.

    Strong despite its simplicity, because the weekday/weekend and
    working-hours cycle is the dominant structure in electricity prices.
    """
    out = {}
    for target in target_intervals(origin, horizon_days):
        reference = prices.get(target - WEEK)
        if reference is not None:
            out[target] = clamp(reference)
    return out


# ── Baseline 2: rolling median ────────────────────────────────────────

def rolling_median(prices, origin, horizon_days=7, weeks=4):
    """Median of this half hour across the last `weeks` weeks.

    Costs no extra data over seasonal naive and is usually better, because
    the median discards the spike weeks that a mean would smear across the
    whole forecast.
    """
    out = {}
    for target in target_intervals(origin, horizon_days):
        samples = [
            prices[target - WEEK * w]
            for w in range(1, weeks + 1)
            if (target - WEEK * w) in prices
        ]
        if samples:
            out[target] = clamp(median(samples))
    return out


# ── Model: seasonal naive adjusted for the change in temperature ──────

def cooling_degrees(temperature):
    """Degrees above the comfort base: the air-conditioning driver."""
    return max(temperature - COMFORT_BASE_C, 0.0)


def heating_degrees(temperature):
    """Degrees below the comfort base: the heating driver."""
    return max(COMFORT_BASE_C - temperature, 0.0)


def build_temperature_pairs(prices, observed_temps):
    """Week-on-week (cooling change, heating change, price change) by band.

    Differencing against the same half hour a week earlier is what makes
    this honest: the weekly cycle, the seasonal level and most of the
    region's structural character all cancel out, leaving something close
    to the marginal effect of weather.

    Temperature enters as two separate degree measures rather than as a raw
    reading, because demand responds to it in a V, not a line. In summer a
    hotter week is a dearer week; in winter a COLDER week is a dearer week.
    A single linear coefficient fitted across both regimes averages two
    opposite effects and collapses toward zero: measured on real NSW data,
    the morning-ramp response was +$11.57/degree in summer and -$12.74 in
    winter, which a one-slope fit reported as +$1.47. Splitting the driver
    lets each side keep its own sign.
    """
    by_band = {}
    for interval_end, price in prices.items():
        previous = interval_end - WEEK
        if previous not in prices:
            continue
        temp_now = observed_temps.get(interval_end)
        temp_prev = observed_temps.get(previous)
        if temp_now is None or temp_prev is None:
            continue

        by_band.setdefault(band_for(interval_end), []).append((
            cooling_degrees(temp_now) - cooling_degrees(temp_prev),
            heating_degrees(temp_now) - heating_degrees(temp_prev),
            price - prices[previous],
        ))
    return by_band


def fit_temperature_betas(prices, observed_temps):
    """Fit cooling and heating coefficients per time-of-day band.

    Returns (betas, diagnostics) where each band maps to
    {'cooling': $/MWh per degree above base, 'heating': per degree below}.
    Diagnostics carry the sample count and the trimming actually applied, so
    the published page can show how much evidence sits behind each number
    instead of just asserting it.
    """
    betas = {}
    diagnostics = {}

    for band, triples in build_temperature_pairs(prices, observed_temps).items():
        if len(triples) < MIN_SAMPLES_PER_BAND:
            betas[band] = {'cooling': 0.0, 'heating': 0.0}
            diagnostics[band] = {
                'samples': len(triples),
                'used': 0,
                'fitted': False,
                'reason': f'fewer than {MIN_SAMPLES_PER_BAND} usable week-on-week pairs',
            }
            continue

        price_deltas = [y for _, _, y in triples]
        low = percentile(price_deltas, TRIM_PERCENTILE)
        high = percentile(price_deltas, 100 - TRIM_PERCENTILE)
        kept = [t for t in triples if low <= t[2] <= high]

        if not kept:
            betas[band] = {'cooling': 0.0, 'heating': 0.0}
            diagnostics[band] = {
                'samples': len(triples), 'used': 0, 'fitted': False,
                'reason': 'no pairs survived spike trimming',
            }
            continue

        cooling, heating = two_slopes_through_origin(kept)
        betas[band] = {'cooling': cooling, 'heating': heating}
        diagnostics[band] = {
            'samples': len(triples),
            'used': len(kept),
            'fitted': True,
            'trimmed_below': round(low, 2),
            'trimmed_above': round(high, 2),
        }

    return betas, diagnostics


def temperature_adjusted(prices, observed_temps, target_temps, betas, origin, horizon_days=7):
    """Seasonal naive plus a temperature nudge.

        predicted = last_week_price
                  + cooling_beta(band) x change in cooling degrees
                  + heating_beta(band) x change in heating degrees

    Worked example: last Tuesday 18:00 cleared at $95 and was 14C, three
    degrees below the 18C base. Next Tuesday is forecast at 8C, ten degrees
    below. Heating degrees rise by seven; at an evening heating coefficient
    of $3.05 the model predicts $95 + 7 x 3.05 = $116.35.

    `target_temps` must be temperatures *forecast* for the coming week, not
    what actually happened. Passing observed future temperature here inflates
    every score and produces a model that cannot be run live; the caller is
    responsible for recording which it used.
    """
    out = {}
    for target in target_intervals(origin, horizon_days):
        reference = prices.get(target - WEEK)
        if reference is None:
            continue

        adjustment = 0.0
        temp_then = observed_temps.get(target - WEEK)
        temp_ahead = target_temps.get(target)
        if temp_then is not None and temp_ahead is not None:
            band = betas.get(band_for(target)) or {}
            adjustment = (
                band.get('cooling', 0.0) * (cooling_degrees(temp_ahead) - cooling_degrees(temp_then))
                + band.get('heating', 0.0) * (heating_degrees(temp_ahead) - heating_degrees(temp_then))
            )

        out[target] = clamp(reference + adjustment)
    return out


# ── Evaluation ────────────────────────────────────────────────────────

def score(predictions, actuals):
    """Compare a forecast against what actually cleared.

    Both MAE and median absolute error are reported. MAE alone is close to
    useless on NEM prices: a handful of spike intervals dominate it, so a
    model can look terrible for one bad evening. The median says how the
    forecast behaves on a normal interval; the mean says what the spikes
    cost. Publishing only one of them would be a choice about which story
    to tell.
    """
    errors = [
        abs(value - actuals[interval])
        for interval, value in predictions.items()
        if interval in actuals
    ]
    if not errors:
        return None

    return {
        'intervals': len(errors),
        'mae': sum(errors) / len(errors),
        'medae': median(errors),
        'max_error': max(errors),
    }


def skill(model_score, baseline_score):
    """Fraction of the baseline's error removed. Negative means worse."""
    if not model_score or not baseline_score or not baseline_score['mae']:
        return None
    return 1.0 - (model_score['mae'] / baseline_score['mae'])


# ── Registry ──────────────────────────────────────────────────────────

SEASONAL_NAIVE = 'seasonal_naive'
ROLLING_MEDIAN = 'rolling_median_4w'
TEMP_ADJUSTED = 'temp_adjusted'
RANDOM_FOREST = 'random_forest'
GRADIENT_BOOSTING = 'gradient_boosting'
NEURAL_NETWORK = 'neural_network'

MODEL_LABELS = {
    SEASONAL_NAIVE: 'Same as last week',
    ROLLING_MEDIAN: 'Median of last 4 weeks',
    TEMP_ADJUSTED: 'Last week + temperature',
    RANDOM_FOREST: 'Random forest',
    GRADIENT_BOOSTING: 'Gradient boosting',
    NEURAL_NETWORK: 'Neural network',
}

# The family each model belongs to, shown on its card. Grouping by family
# makes the ladder legible: two models that share a family will fail in
# similar ways, which matters more than their individual scores.
MODEL_FAMILIES = {
    SEASONAL_NAIVE: 'Baseline',
    ROLLING_MEDIAN: 'Baseline',
    TEMP_ADJUSTED: 'Linear',
    RANDOM_FOREST: 'Tree ensemble',
    GRADIENT_BOOSTING: 'Tree ensemble',
    NEURAL_NETWORK: 'Neural',
}

MODEL_INPUTS = {
    SEASONAL_NAIVE: 'Price history',
    ROLLING_MEDIAN: 'Price history',
    TEMP_ADJUSTED: 'Price, temperature',
    RANDOM_FOREST: 'Price, demand, calendar, temperature',
    GRADIENT_BOOSTING: 'Price, demand, calendar, temperature',
    NEURAL_NETWORK: 'Price, demand, calendar, temperature',
}

MODEL_FITTED = {
    SEASONAL_NAIVE: 'Nothing',
    ROLLING_MEDIAN: 'Nothing',
    TEMP_ADJUSTED: '12 coefficients',
    RANDOM_FOREST: '300 trees',
    GRADIENT_BOOSTING: '400 boosted trees',
    NEURAL_NETWORK: '64x32 hidden units',
}

MODEL_DESCRIPTIONS = {
    SEASONAL_NAIVE: 'Repeats the price from the same half hour seven days earlier. No fitting, no parameters.',
    ROLLING_MEDIAN: 'Takes the middle value of the same half hour across the last four weeks, so one spike week cannot dominate.',
    TEMP_ADJUSTED: 'Starts from last week, then adjusts for the forecast change in heating and cooling degrees, fitted separately because demand responds to temperature in a V, not a line.',
    RANDOM_FOREST: 'Averages 300 decision trees over calendar, lagged price and forecast weather. Stable, but it predicts a constant inside each region of the feature space, so it cannot go beyond the prices it was trained on.',
    GRADIENT_BOOSTING: 'Trees fitted in sequence, each correcting the errors of the ones before it. Sharper than the forest and easier to overfit, so it stops early.',
    NEURAL_NETWORK: 'Two hidden layers over standardised features. Unlike the trees it fits a smooth continuous surface and can extrapolate beyond its training range, which is both its advantage and its main way of going wrong.',
}

# Order matters: it drives the chart legend, the toggle strip, the comparison
# boxes and the performance table. Baselines first, so the ladder always
# reads cheapest to most elaborate.
MODEL_ORDER = [
    SEASONAL_NAIVE,
    ROLLING_MEDIAN,
    TEMP_ADJUSTED,
    RANDOM_FOREST,
    GRADIENT_BOOSTING,
    NEURAL_NETWORK,
]

# The models that need scikit-learn. Kept here so callers can skip them
# without importing the training module.
TREE_MODELS = {RANDOM_FOREST, GRADIENT_BOOSTING, NEURAL_NETWORK}

__all__ = [
    'INTERVALS_PER_WEEK', 'WEEK', 'INTERVAL',
    'interval_start', 'week_slot', 'band_for', 'target_intervals', 'clamp',
    'percentile', 'slope_through_origin', 'two_slopes_through_origin',
    'cooling_degrees', 'heating_degrees', 'COMFORT_BASE_C',
    'seasonal_naive', 'rolling_median', 'temperature_adjusted',
    'build_temperature_pairs', 'fit_temperature_betas',
    'score', 'skill',
    'SEASONAL_NAIVE', 'ROLLING_MEDIAN', 'TEMP_ADJUSTED',
    'RANDOM_FOREST', 'GRADIENT_BOOSTING', 'NEURAL_NETWORK', 'TREE_MODELS',
    'MODEL_LABELS', 'MODEL_DESCRIPTIONS', 'MODEL_ORDER',
    'MODEL_FAMILIES', 'MODEL_INPUTS', 'MODEL_FITTED',
    'MARKET_PRICE_FLOOR',
]
