"""Ingest temperature from Open-Meteo.

Three kinds of pull, and the distinction between them is the whole point:

    --kind observed   what the temperature actually was (reanalysis).
                      Safe as history. Never safe for the week ahead.
    --kind forecast   the forecast that WAS ISSUED for a past window.
                      This is what an honest backtest has to score against.
    --forward         the live forecast for the next seven days, used to
                      make the run that gets published on Sunday.

    python manage.py ingest_nem_weather --forward
    python manage.py ingest_nem_weather --kind observed --months 24
    python manage.py ingest_nem_weather --kind forecast --months 12
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from ...constants import REGIONS
from ...ingest import IngestError
from ...models import RegionWeather
from ...services import ingest_forward_weather, ingest_weather_window, rebuild_nem_aggregate

# Open-Meteo serves long ranges happily, but chunking keeps any single
# failure cheap to retry and keeps us a polite client.
CHUNK_DAYS = 120


class Command(BaseCommand):
    help = 'Ingest observed or forecast temperature for each NEM region.'

    def add_arguments(self, parser):
        parser.add_argument('--region', choices=REGIONS, action='append',
                            help='Region to fetch. Repeatable. Defaults to all five.')
        parser.add_argument('--kind', choices=[RegionWeather.OBSERVED, RegionWeather.FORECAST],
                            default=RegionWeather.OBSERVED,
                            help='Historical pull: reanalysis (observed) or archived forecast.')
        parser.add_argument('--months', type=int, default=12,
                            help='How many months of history to pull.')
        parser.add_argument('--forward', action='store_true',
                            help='Pull the live 7-day forecast instead of history.')

    def handle(self, *args, **options):
        regions = options['region'] or REGIONS

        if options['forward']:
            return self._forward(regions)

        kind = options['kind']

        # Reanalysis lags real time by several days, so the observed pull
        # stops short of today rather than making a run of empty requests.
        # The archived-forecast pull has no such lag and must run right up to
        # today: stopping early leaves a hole between where history ends and
        # where the forward forecast begins, and any model needing both sides
        # of a week-on-week comparison loses the entire live edge to it.
        end = date.today() - timedelta(days=6) if kind == RegionWeather.OBSERVED else date.today()
        start = end - timedelta(days=30 * options['months'])

        total = 0
        for region in regions:
            stored = 0
            window_start = start
            while window_start < end:
                window_end = min(window_start + timedelta(days=CHUNK_DAYS), end)
                try:
                    stored += ingest_weather_window(region, window_start, window_end, kind)
                except IngestError as exc:
                    self.stderr.write(self.style.WARNING(
                        f'{region} {window_start}..{window_end}: {exc}'
                    ))
                window_start = window_end + timedelta(days=1)

            total += stored
            self.stdout.write(f'{region}: {stored} {kind} intervals')

        self.stdout.write(self.style.SUCCESS(f'Stored {total} temperature intervals.'))
        self._rebuild_aggregate()

    def _forward(self, regions):
        total = 0
        for region in regions:
            try:
                stored = ingest_forward_weather(region)
            except IngestError as exc:
                self.stderr.write(self.style.WARNING(f'{region}: {exc}'))
                continue
            total += stored
            self.stdout.write(f'{region}: {stored} forecast intervals')
        self.stdout.write(self.style.SUCCESS(f'Stored {total} forward forecast intervals.'))
        self._rebuild_aggregate()

    def _rebuild_aggregate(self):
        """The market-wide series is derived, so it follows every change."""
        intervals, temperatures = rebuild_nem_aggregate()
        self.stdout.write(
            f'NEM aggregate rebuilt: {intervals} intervals, {temperatures} temperatures.'
        )
