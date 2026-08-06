"""Leakage-safe feature matrix for the tree-based models.

Everything in this module answers one question: what could a forecaster
have actually known at the moment the run was issued?

At a seven-day horizon that rules out a lot. On Sunday morning you do not
know Wednesday's demand, Wednesday's fuel mix, or what the price did on
Tuesday. You know the price history up to Sunday, the calendar, and a
*forecast* of the weather. That is all. Every feature below is derived from
one of those three, and the builder refuses to look past the origin.

The lag structure is the part that is easy to get wrong. A naive
`price_lag_1` (half an hour earlier) is a superb predictor and completely
unavailable: for a target on Friday, the previous half hour is also in the
future. Every price lag here is therefore at least a full seven days, so it
resolves to something settled before the origin no matter which day of the
horizon the target falls on.
"""

from datetime import timedelta

from .constants import BAND_BY_HOUR, BAND_ORDER
from .forecasting import (
    COMFORT_BASE_C,
    WEEK,
    cooling_degrees,
    heating_degrees,
    interval_start,
)

# Price lags, in whole weeks. One week is the minimum that stays settled
# across the entire horizon; four weeks gives the model the same information
# the rolling-median baseline uses.
PRICE_LAG_WEEKS = (1, 2, 3, 4)

FEATURE_NAMES = (
    # Calendar
    'hour_sin', 'hour_cos',          # time of day as a circle, so 23:30 and 00:00 are adjacent
    'dow_sin', 'dow_cos',            # day of week as a circle, same reason
    'is_weekend',
    'month_sin', 'month_cos',
    'horizon_days',                  # how far ahead of the origin this target sits
    # Band one-hot
    *[f'band_{key}' for key in BAND_ORDER],
    # Price history, all at least a week old
    *[f'price_lag_{w}w' for w in PRICE_LAG_WEEKS],
    'price_lag_mean_4w', 'price_lag_median_4w', 'price_lag_spread_4w',
    'demand_lag_1w',
    # Weather, forecast for the target and observed for the reference week
    'temp_forecast', 'cooling_degrees', 'heating_degrees',
    'temp_lag_1w', 'temp_delta_1w', 'cooling_delta_1w', 'heating_delta_1w',
)


def _circle(value, period):
    """Encode a cyclic value as a sine/cosine pair.

    A raw hour number tells a tree that 23 and 0 are 23 apart when they are
    adjacent. Splitting into two coordinates on a circle removes that.
    """
    import math
    angle = 2.0 * math.pi * (value / period)
    return math.sin(angle), math.cos(angle)


def build_row(target, origin, prices, observed_temps, target_temps, demands):
    """One feature row, or None when a required input is missing.

    Returns None rather than imputing. A silently filled-in lag would let the
    model train on a value nobody had, which is the exact failure this whole
    module exists to prevent.
    """
    start = interval_start(target)

    lags = []
    for weeks in PRICE_LAG_WEEKS:
        value = prices.get(target - WEEK * weeks)
        if value is None:
            return None
        lags.append(value)

    demand_lag = demands.get(target - WEEK)
    temp_then = observed_temps.get(target - WEEK)
    temp_ahead = target_temps.get(target)
    if demand_lag is None or temp_then is None or temp_ahead is None:
        return None

    hour_sin, hour_cos = _circle(start.hour * 2 + start.minute // 30, 48)
    dow_sin, dow_cos = _circle(start.weekday(), 7)
    month_sin, month_cos = _circle(start.month - 1, 12)

    band = BAND_BY_HOUR[start.hour]
    band_flags = [1.0 if key == band else 0.0 for key in BAND_ORDER]

    ordered = sorted(lags)
    mid = len(ordered) // 2
    median = (ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2.0)

    return [
        hour_sin, hour_cos,
        dow_sin, dow_cos,
        1.0 if start.weekday() >= 5 else 0.0,
        month_sin, month_cos,
        (target - origin).total_seconds() / 86400.0,
        *band_flags,
        *lags,
        sum(lags) / len(lags),
        median,
        max(lags) - min(lags),
        demand_lag,
        temp_ahead,
        cooling_degrees(temp_ahead),
        heating_degrees(temp_ahead),
        temp_then,
        temp_ahead - temp_then,
        cooling_degrees(temp_ahead) - cooling_degrees(temp_then),
        heating_degrees(temp_ahead) - heating_degrees(temp_then),
    ]


def build_training_set(prices, observed_temps, demands, origin, training_weeks=52):
    """Rows for every settled interval the model is allowed to learn from.

    Each historical interval is treated as though it were itself a forecast
    target, with its own pseudo-origin exactly seven days earlier. That keeps
    training and prediction the same shape: the model never sees a feature
    during training that it will not have at prediction time.

    Observed temperature stands in for forecast temperature during training,
    because no archived forecast exists for most historical intervals. This
    is a known optimism and is recorded rather than hidden: the model learns
    a slightly cleaner weather signal than it will get in production.
    """
    window_start = origin - timedelta(weeks=training_weeks)

    X, y, index = [], [], []
    for interval_end in sorted(prices):
        if not (window_start < interval_end <= origin):
            continue

        pseudo_origin = interval_end - WEEK
        row = build_row(
            interval_end, pseudo_origin,
            prices, observed_temps, observed_temps, demands,
        )
        if row is None:
            continue
        X.append(row)
        y.append(prices[interval_end])
        index.append(interval_end)

    return X, y, index


def build_prediction_set(targets, origin, prices, observed_temps, target_temps, demands):
    """Rows for the week being forecast, using genuine forecast temperature."""
    X, index = [], []
    for target in targets:
        row = build_row(target, origin, prices, observed_temps, target_temps, demands)
        if row is None:
            continue
        X.append(row)
        index.append(target)
    return X, index


__all__ = [
    'FEATURE_NAMES', 'PRICE_LAG_WEEKS',
    'build_row', 'build_training_set', 'build_prediction_set',
]
