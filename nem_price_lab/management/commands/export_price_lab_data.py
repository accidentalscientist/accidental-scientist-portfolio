"""Export every input and output of the lab as CSV, for inspection.

The point of this command is auditability. A forecasting page that asks to
be believed should hand over the numbers behind it, in a format anyone can
open in a spreadsheet and check by hand.

Five files per run:

    prices_<REGION>.csv     every settled 30-minute interval: price and demand
    weather_<REGION>.csv    observed and forecast temperature, side by side
    features_<REGION>.csv   the exact training matrix the tree models saw
    forecasts_<REGION>.csv  every prediction ever published, by model and origin
    scores_<REGION>.csv     each completed week scored against what cleared

    python manage.py export_price_lab_data
    python manage.py export_price_lab_data --region NSW1 --out ./audit
"""

import csv
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand

from ...constants import DISPLAY_REGIONS, NEM_TZ
from ...features import FEATURE_NAMES, build_training_set
from ...forecasting import MODEL_LABELS
from ...models import ForecastPoint, ForecastRun, RegionPrice, RegionWeather
from ...services import (
    available_regions,
    completed_origins,
    demand_map,
    most_recent_sunday,
    price_map,
    reference_temperatures,
    review_origin,
)

DEFAULT_OUT = 'price_lab_export'


def _stamp(value):
    """ISO-8601 in NEM market time, so exported timestamps are unambiguous."""
    return value.astimezone(NEM_TZ).isoformat() if value else ''


class Command(BaseCommand):
    help = 'Export prices, weather, features, forecasts and scores as CSV.'

    def add_arguments(self, parser):
        parser.add_argument('--region', choices=DISPLAY_REGIONS, action='append',
                            help='Region to export. Repeatable. Defaults to all with data.')
        parser.add_argument('--out', default=DEFAULT_OUT, help='Output directory.')
        parser.add_argument('--training-weeks', type=int, default=52,
                            help='History window used when rebuilding the feature matrix.')

    def handle(self, *args, **options):
        regions = options['region'] or available_regions()
        out = Path(options['out']).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)

        written = []
        for region in regions:
            written.append(self._prices(out, region))
            written.append(self._weather(out, region))
            written.append(self._features(out, region, options['training_weeks']))
            written.append(self._forecasts(out, region))
            written.append(self._scores(out, region))

        self.stdout.write(self.style.SUCCESS(f'Wrote {len(written)} files to {out}'))
        for path, rows in written:
            self.stdout.write(f'  {path.name:34} {rows:>8,} rows')

    # ── Files ─────────────────────────────────────────────────────────

    def _write(self, path, header, rows):
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            count = 0
            for row in rows:
                writer.writerow(row)
                count += 1
        return path, count

    def _prices(self, out, region):
        queryset = (
            RegionPrice.objects.filter(region=region)
            .order_by('interval_end')
            .values_list('interval_end', 'rrp', 'total_demand')
        )
        return self._write(
            out / f'prices_{region}.csv',
            ['interval_end_nem', 'region', 'rrp_aud_per_mwh', 'total_demand_mw'],
            ([_stamp(i), region, f'{p:.2f}', f'{d:.2f}'] for i, p, d in queryset.iterator()),
        )

    def _weather(self, out, region):
        """Observed and forecast in one file so the two are directly comparable.

        Where both exist for the same interval, the difference between them
        is the forecast error the weather provider made, which is a large
        part of why a price forecast built on it misses.
        """
        merged = {}
        for kind in (RegionWeather.OBSERVED, RegionWeather.FORECAST):
            for interval, temperature in (
                RegionWeather.objects.filter(region=region, kind=kind)
                .values_list('interval_end', 'temperature_c')
            ):
                merged.setdefault(interval, {})[kind] = temperature

        def rows():
            for interval in sorted(merged):
                entry = merged[interval]
                observed = entry.get(RegionWeather.OBSERVED)
                forecast = entry.get(RegionWeather.FORECAST)
                error = ('' if observed is None or forecast is None
                         else f'{forecast - observed:.2f}')
                yield [
                    _stamp(interval), region,
                    '' if observed is None else f'{observed:.2f}',
                    '' if forecast is None else f'{forecast:.2f}',
                    error,
                ]

        return self._write(
            out / f'weather_{region}.csv',
            ['interval_end_nem', 'region', 'observed_c', 'forecast_c', 'forecast_minus_observed_c'],
            rows(),
        )

    def _features(self, out, region, training_weeks):
        """The tree models' training matrix, rebuilt exactly as they saw it."""
        origin = most_recent_sunday(
            RegionPrice.objects.filter(region=region)
            .order_by('-interval_end').values_list('interval_end', flat=True).first()
            or most_recent_sunday(timezone_now())
        )
        start = origin - timedelta(weeks=training_weeks)
        prices = price_map(region, start - timedelta(weeks=5), origin)
        temps = reference_temperatures(region, start - timedelta(weeks=5), origin)
        demands = demand_map(region, start - timedelta(weeks=5), origin)

        X, y, index = build_training_set(prices, temps, demands, origin, training_weeks)

        return self._write(
            out / f'features_{region}.csv',
            ['interval_end_nem', 'region', *FEATURE_NAMES, 'target_rrp'],
            (
                [_stamp(interval), region, *[f'{v:.6g}' for v in row], f'{target:.2f}']
                for interval, row, target in zip(index, X, y)
            ),
        )

    def _forecasts(self, out, region):
        queryset = (
            ForecastPoint.objects.filter(run__region=region)
            .select_related('run')
            .order_by('run__issued_at', 'run__model_key', 'interval_end')
            .values_list(
                'run__issued_at', 'run__model_key', 'run__temperature_source',
                'interval_end', 'predicted_rrp',
            )
        )

        actuals = price_map(region)

        def rows():
            for issued_at, model_key, temp_source, interval, predicted in queryset.iterator():
                actual = actuals.get(interval)
                yield [
                    _stamp(issued_at), region, model_key,
                    MODEL_LABELS.get(model_key, model_key),
                    _stamp(interval),
                    f'{(interval - issued_at).total_seconds() / 86400.0:.4f}',
                    f'{predicted:.2f}',
                    '' if actual is None else f'{actual:.2f}',
                    '' if actual is None else f'{predicted - actual:.2f}',
                    temp_source,
                ]

        return self._write(
            out / f'forecasts_{region}.csv',
            ['issued_at_nem', 'region', 'model_key', 'model_label', 'target_interval_end_nem',
             'horizon_days', 'predicted_rrp', 'actual_rrp', 'predicted_minus_actual',
             'temperature_source'],
            rows(),
        )

    def _scores(self, out, region):
        def rows():
            for origin in completed_origins(region):
                for entry in review_origin(region, origin):
                    result = entry['score']
                    if not result:
                        continue
                    yield [
                        _stamp(origin), region, entry['model_key'], entry['label'],
                        result['intervals'],
                        f"{result['mae']:.2f}",
                        f"{result['medae']:.2f}",
                        f"{result['max_error']:.2f}",
                        '' if entry['skill'] is None else f"{entry['skill'] * 100:.2f}",
                        'yes' if entry['leakage_safe'] else 'no',
                    ]

        return self._write(
            out / f'scores_{region}.csv',
            ['issued_at_nem', 'region', 'model_key', 'model_label', 'intervals_scored',
             'mae', 'median_ae', 'worst_interval', 'skill_pct_vs_baseline', 'leakage_safe'],
            rows(),
        )


def timezone_now():
    from django.utils import timezone
    return timezone.now()
