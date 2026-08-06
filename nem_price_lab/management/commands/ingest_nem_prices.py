"""Ingest AEMO aggregated price and demand data.

Manual today, automatable tomorrow: the source is an unauthenticated HTTP
GET, so scheduling this command is the entire difference between the weekly
ritual and an automated pipeline. Nothing about the code needs to change.

    # the weekly Sunday refresh: current month, every region
    python manage.py ingest_nem_prices

    # backfill two years for one region
    python manage.py ingest_nem_prices --region NSW1 --months 24

    # a file already downloaded by hand
    python manage.py ingest_nem_prices --file ~/PRICE_AND_DEMAND_202608_NSW1.csv
"""

from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...constants import REGIONS
from ...ingest import IngestError, month_range, parse_price_csv
from ...services import ingest_month, rebuild_nem_aggregate, upsert_prices


class Command(BaseCommand):
    help = 'Ingest AEMO aggregated price and demand CSVs into 30-minute intervals.'

    def add_arguments(self, parser):
        parser.add_argument('--region', choices=REGIONS, action='append',
                            help='Region to fetch. Repeatable. Defaults to all five.')
        parser.add_argument('--months', type=int, default=1,
                            help='How many months back to fetch, ending with the current month.')
        parser.add_argument('--month', help="A single month as YYYYMM. Overrides --months.")
        parser.add_argument('--file', help='Parse a local CSV instead of fetching.')

    def handle(self, *args, **options):
        if options['file']:
            return self._ingest_file(Path(options['file']).expanduser())

        regions = options['region'] or REGIONS
        months = [options['month']] if options['month'] else month_range(date.today(), options['months'])

        total = 0
        failures = 0
        for region in regions:
            for month in months:
                try:
                    report = ingest_month(region, month)
                except IngestError as exc:
                    failures += 1
                    self.stderr.write(self.style.WARNING(f'{region} {month}: {exc}'))
                    continue

                total += report['stored']
                if report['stored']:
                    self.stdout.write(
                        f"{region} {month}: {report['stored']} intervals, "
                        f"{report['first']:%Y-%m-%d} to {report['last']:%Y-%m-%d}"
                    )
                else:
                    self.stdout.write(self.style.WARNING(f'{region} {month}: no usable rows'))

        self.stdout.write(self.style.SUCCESS(f'Stored {total} intervals across {len(regions)} region(s).'))
        if failures:
            self.stdout.write(self.style.WARNING(f'{failures} region-month(s) could not be fetched.'))

        self._rebuild_aggregate()

    def _rebuild_aggregate(self):
        """Refresh the derived NEM-wide series after any regional change."""
        intervals, temperatures = rebuild_nem_aggregate()
        self.stdout.write(
            f'NEM aggregate rebuilt: {intervals} intervals, {temperatures} temperatures.'
        )

    def _ingest_file(self, path):
        if not path.exists():
            raise CommandError(f'no such file: {path}')
        try:
            rows, report = parse_price_csv(path.read_text(encoding='utf-8-sig', errors='replace'))
        except IngestError as exc:
            raise CommandError(str(exc)) from exc

        stored = upsert_prices(rows)
        self.stdout.write(self.style.SUCCESS(
            f"Stored {stored} intervals for {', '.join(report['regions'])} "
            f"({report['first']:%Y-%m-%d} to {report['last']:%Y-%m-%d}); skipped {report['skipped']}."
        ))
        self._rebuild_aggregate()
