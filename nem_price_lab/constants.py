"""Shared constants for the Price Predictor Lab.

Kept free of Django imports so the forecasting layer stays unit-testable
without a database or settings module.
"""

from datetime import timedelta, timezone

# ── NEM market time ───────────────────────────────────────────────────
# Every AEMO timestamp is "market time": a FIXED UTC+10 offset that does
# not observe daylight saving. This is NOT Australia/Sydney, which shifts
# to UTC+11 in summer. Using the project's TIME_ZONE here would silently
# move half the year's data by an hour, so the offset is pinned instead.
NEM_TZ = timezone(timedelta(hours=10), name='AEST')

# Open-Meteo expresses the same fixed offset this way (POSIX sign flip).
OPEN_METEO_TZ = 'Etc/GMT-10'

# ── Market structure ──────────────────────────────────────────────────
# The five regions AEMO actually publishes and settles.
REGIONS = ['NSW1', 'QLD1', 'VIC1', 'SA1', 'TAS1']

# There is no such thing as a single NEM spot price: each region settles its
# own. The market-wide figure shown here is a DEMAND-WEIGHTED average of the
# five regional prices, which is the aggregate that means something
# economically (it is what the market paid per MWh actually consumed). A
# plain unweighted mean would let Tasmania move the headline as much as New
# South Wales. The derived nature of this series is stated on the page.
NEM_REGION = 'NEM'
DISPLAY_REGIONS = [NEM_REGION] + REGIONS

REGION_LABELS = {
    NEM_REGION: 'National Electricity Market',
    'NSW1': 'New South Wales',
    'QLD1': 'Queensland',
    'VIC1': 'Victoria',
    'SA1': 'South Australia',
    'TAS1': 'Tasmania',
}

# Short forms for the selector pills, matching the fuel-mix dashboard's
# compact NEM / NSW / QLD styling rather than repeating the AEMO suffix.
REGION_SHORT = {
    NEM_REGION: 'NEM',
    'NSW1': 'NSW',
    'QLD1': 'QLD',
    'VIC1': 'VIC',
    'SA1': 'SA',
    'TAS1': 'TAS',
}

# One representative weather point per region: the capital, because that is
# where the load is. A population-weighted multi-point average would be more
# faithful and is recorded as future work rather than guessed at here.
REGION_WEATHER_POINTS = {
    'NSW1': (-33.87, 151.21),   # Sydney
    'QLD1': (-27.47, 153.03),   # Brisbane
    'VIC1': (-37.81, 144.96),   # Melbourne
    'SA1': (-34.93, 138.60),    # Adelaide
    'TAS1': (-42.88, 147.33),   # Hobart
}

# ── Resolution ────────────────────────────────────────────────────────
# The lab works in 30-minute intervals. Five-minute dispatch data is
# averaged up on ingest, which is exactly how the trading price was defined
# before Five Minute Settlement, so the aggregation is principled rather
# than arbitrary. A seven-day-ahead forecast has no business at 5 minutes.
MINUTES_PER_INTERVAL = 30
INTERVALS_PER_DAY = 48
INTERVALS_PER_WEEK = INTERVALS_PER_DAY * 7  # 336

# ── Price bounds ──────────────────────────────────────────────────────
# The market price floor has been a stable -$1,000/MWh and is safe to pin.
# The market price CAP is indexed annually, so it is deliberately NOT
# hardcoded: read it from AEMO's MARKET_PRICE_THRESHOLDS table if a ceiling
# is ever needed. At a 7-day horizon these models never approach it.
MARKET_PRICE_FLOOR = -1000.0

# ── Time-of-day bands used by the temperature-adjusted model ──────────
# Six bands, chosen so each has a distinct physical story: overnight
# baseload, the morning ramp, the solar-suppressed middle of the day, the
# afternoon shoulder, the evening peak after solar drops out, and late night.
TIME_BANDS = [
    {'key': 'overnight', 'label': 'Overnight',     'hours': (0, 5),   'note': 'baseload, low demand'},
    {'key': 'morning',   'label': 'Morning ramp',  'hours': (6, 8),   'note': 'demand climbing'},
    {'key': 'midday',    'label': 'Midday',        'hours': (9, 14),  'note': 'rooftop solar suppresses price'},
    {'key': 'afternoon', 'label': 'Afternoon',     'hours': (15, 16), 'note': 'solar fading'},
    {'key': 'evening',   'label': 'Evening peak',  'hours': (17, 20), 'note': 'peak demand, solar gone'},
    {'key': 'late',      'label': 'Late evening',  'hours': (21, 23), 'note': 'demand unwinding'},
]

BAND_BY_HOUR = {}
for _band in TIME_BANDS:
    _start, _end = _band['hours']
    for _hour in range(_start, _end + 1):
        BAND_BY_HOUR[_hour] = _band['key']

BAND_LABELS = {b['key']: b['label'] for b in TIME_BANDS}
BAND_ORDER = [b['key'] for b in TIME_BANDS]
