"""Data acquisition for the Price Predictor Lab.

Two sources, both public and both free of API keys:

1.  AEMO aggregated price and demand
    https://aemo.com.au/aemo/data/nem/priceanddemand/PRICE_AND_DEMAND_YYYYMM_REGION.csv
    One file per region-month, CUMULATIVE WITHIN THE MONTH: the current
    month's file grows through the month, so re-fetching it each week both
    refreshes and extends what is already stored. Carries RRP (the target)
    and TOTALDEMAND in the same file.

2.  Open-Meteo temperature
    Two separate endpoints on purpose. `forecast` is what is predicted for
    the days ahead. `historical-forecast` returns the forecast that WAS
    ISSUED for a past date, which is the only defensible way to backtest a
    model that will run on forecasts in production.

Everything here uses the standard library. Adding `requests` for four HTTP
GETs would reverse a deliberate dependency cull for no benefit.
"""

import csv
import io
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from .constants import (
    MINUTES_PER_INTERVAL,
    NEM_TZ,
    OPEN_METEO_TZ,
    REGION_WEATHER_POINTS,
    REGIONS,
)

AEMO_CSV_URL = (
    'https://aemo.com.au/aemo/data/nem/priceanddemand/PRICE_AND_DEMAND_{month}_{region}.csv'
)
OPEN_METEO_FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
OPEN_METEO_HISTORICAL_FORECAST_URL = 'https://historical-forecast-api.open-meteo.com/v1/forecast'

# NEMWeb and AEMO are public but not free infrastructure. Identify the client
# and keep the request rate low enough that a weekly refresh is invisible.
USER_AGENT = 'accidentalscientist.net price-lab (+https://accidentalscientist.net)'
HTTP_TIMEOUT = 60

REQUIRED_COLUMNS = {'REGION', 'SETTLEMENTDATE', 'TOTALDEMAND', 'RRP'}
AEMO_TIMESTAMP_FORMATS = ('%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M')

INTERVAL = timedelta(minutes=MINUTES_PER_INTERVAL)


class IngestError(Exception):
    """Raised when a source cannot be read or does not look like what we expect."""


# ── Time bucketing ────────────────────────────────────────────────────

def interval_end_for(dt):
    """Round a dispatch timestamp up to the half hour that contains it.

    AEMO stamps an interval with its END, so 00:05 belongs to the half hour
    ending 00:30 and 00:30 belongs to itself. Getting this backwards would
    shift every observation by half an hour, which is exactly the kind of
    silent unit error the site's own quality bar calls out.
    """
    floored = dt.replace(minute=(dt.minute // MINUTES_PER_INTERVAL) * MINUTES_PER_INTERVAL,
                         second=0, microsecond=0)
    return floored if floored == dt else floored + INTERVAL


def parse_aemo_timestamp(raw):
    for fmt in AEMO_TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=NEM_TZ)
        except ValueError:
            continue
    return None


# ── HTTP ──────────────────────────────────────────────────────────────

def _fetch(url, params=None):
    if params:
        url = f'{url}?{urllib.parse.urlencode(params)}'
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return response.read()
    except Exception as exc:  # urllib raises a wide family; the caller only needs the message
        raise IngestError(f'could not fetch {url}: {exc}') from exc


def fetch_price_csv(region, month):
    """Download one region-month of aggregated price and demand data.

    `month` is 'YYYYMM'. The current month is a partial but valid file.
    """
    if region not in REGIONS:
        raise IngestError(f'unknown region {region!r}; expected one of {", ".join(REGIONS)}')
    return _fetch(AEMO_CSV_URL.format(month=month, region=region)).decode('utf-8-sig', errors='replace')


# ── AEMO price parsing ────────────────────────────────────────────────

def parse_price_csv(text):
    """Aggregate an AEMO price CSV into 30-minute intervals per region.

    Post-2021 files are 5-minute and six rows collapse into each half hour;
    pre-2021 files are already 30-minute and pass through one-to-one.
    Averaging the six 5-minute prices reproduces how the trading price was
    defined before Five Minute Settlement, so mixing the two eras stays
    coherent.

    Returns (rows, report) where rows is a list of dicts ready for the ORM.
    """
    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_COLUMNS - headers
    if missing:
        raise IngestError(f'missing columns: {", ".join(sorted(missing))}')

    buckets = {}
    skipped = 0
    issues = []

    for line_no, row in enumerate(reader, start=2):
        region = (row.get('REGION') or '').strip()
        timestamp = parse_aemo_timestamp((row.get('SETTLEMENTDATE') or '').strip())
        if not region or timestamp is None:
            skipped += 1
            if len(issues) < 10:
                issues.append(f'line {line_no}: unreadable region or timestamp')
            continue

        try:
            rrp = float(row['RRP'])
            demand = float(row['TOTALDEMAND'])
        except (TypeError, ValueError):
            skipped += 1
            if len(issues) < 10:
                issues.append(f'line {line_no}: non-numeric RRP or demand')
            continue

        key = (region, interval_end_for(timestamp))
        prices, demands = buckets.setdefault(key, ([], []))
        prices.append(rrp)
        demands.append(demand)

    rows = [
        {
            'region': region,
            'interval_end': interval_end,
            'rrp': sum(prices) / len(prices),
            'total_demand': sum(demands) / len(demands),
        }
        for (region, interval_end), (prices, demands) in sorted(buckets.items())
    ]

    regions_seen = sorted({r['region'] for r in rows})
    report = {
        'intervals': len(rows),
        'skipped': skipped,
        'issues': issues,
        'regions': regions_seen,
        'first': rows[0]['interval_end'] if rows else None,
        'last': rows[-1]['interval_end'] if rows else None,
    }
    return rows, report


# ── Open-Meteo temperature ────────────────────────────────────────────

def _interpolate_to_intervals(hourly):
    """Turn hourly temperatures into 30-minute values.

    The half hours land exactly midway between two hourly readings, so a
    straight linear interpolation is all that is warranted. Anything more
    elaborate would be inventing precision the source does not have.
    """
    if not hourly:
        return {}

    ordered = sorted(hourly.items())
    out = {}
    for index, (stamp, value) in enumerate(ordered):
        out[stamp] = value
        if index + 1 < len(ordered):
            next_stamp, next_value = ordered[index + 1]
            if next_stamp - stamp == timedelta(hours=1):
                out[stamp + INTERVAL] = (value + next_value) / 2.0
    return out


def _parse_open_meteo(payload):
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise IngestError(f'Open-Meteo returned unparseable JSON: {exc}') from exc

    if 'error' in data:
        raise IngestError(f"Open-Meteo error: {data.get('reason', 'unknown')}")

    hourly = data.get('hourly') or {}
    times = hourly.get('time') or []
    temps = hourly.get('temperature_2m') or []
    if not times:
        raise IngestError('Open-Meteo returned no hourly data')

    parsed = {}
    for stamp, temp in zip(times, temps):
        if temp is None:
            continue
        parsed[datetime.fromisoformat(stamp).replace(tzinfo=NEM_TZ)] = float(temp)

    return _interpolate_to_intervals(parsed)


def fetch_forecast_temperature(region, days=7):
    """Temperature predicted for the days ahead. Used to make a live run."""
    lat, lon = REGION_WEATHER_POINTS[region]
    payload = _fetch(OPEN_METEO_FORECAST_URL, {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m',
        'timezone': OPEN_METEO_TZ,
        'forecast_days': days,
    })
    return _parse_open_meteo(payload)


def fetch_historical_forecast_temperature(region, start_date, end_date):
    """The temperature that WAS FORECAST for a past window.

    This is the endpoint that makes an honest backtest possible. Scoring a
    model against reanalysis temperature it could never have had on the day
    produces a flattering number and a model that underperforms the moment
    it goes live.
    """
    lat, lon = REGION_WEATHER_POINTS[region]
    payload = _fetch(OPEN_METEO_HISTORICAL_FORECAST_URL, {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m',
        'timezone': OPEN_METEO_TZ,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    })
    return _parse_open_meteo(payload)


def fetch_observed_temperature(region, start_date, end_date):
    """What the temperature actually was.

    Safe as an input for *past* intervals, which is how the model reads last
    week's weather. Never safe for the week being predicted.
    """
    lat, lon = REGION_WEATHER_POINTS[region]
    payload = _fetch('https://archive-api.open-meteo.com/v1/archive', {
        'latitude': lat,
        'longitude': lon,
        'hourly': 'temperature_2m',
        'timezone': OPEN_METEO_TZ,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
    })
    return _parse_open_meteo(payload)


def month_range(end_month, count):
    """The last `count` 'YYYYMM' strings ending at `end_month` (a date)."""
    months = []
    year, month = end_month.year, end_month.month
    for _ in range(count):
        months.append(f'{year:04d}{month:02d}')
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(months))
