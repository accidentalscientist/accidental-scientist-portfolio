from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management.base import BaseCommand, CommandError

from ...aemo import AEMODataError, NEM_TIME, download_source_set
from ...models import BatteryDailySummary, BatteryDataRefresh
from ...refresh import finish_refresh, refresh_range
from ...registry import RegistryError, load_registry


class Command(BaseCommand):
    help = 'Download, validate, and ingest public AEMO battery data.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=date.fromisoformat, help='First calendar day, YYYY-MM-DD.')
        parser.add_argument('--end', type=date.fromisoformat, help='Last calendar day, YYYY-MM-DD.')
        parser.add_argument(
            '--cache-dir',
            type=Path,
            help='Keep and reuse downloaded ZIPs in this directory.',
        )

    def handle(self, *args, **options):
        try:
            load_registry()
        except RegistryError as exc:
            raise CommandError(f'Registry load failed: {exc}') from exc

        today_nem = datetime.now(NEM_TIME).date()
        end_date = options['end'] or today_nem - timedelta(days=2)
        latest = BatteryDailySummary.objects.order_by('-operating_date').first()
        start_date = options['start'] or (
            latest.operating_date + timedelta(days=1) if latest else end_date - timedelta(days=6)
        )
        if end_date < start_date:
            self.stdout.write(self.style.SUCCESS('Battery data is already current for the requested window.'))
            return

        run = BatteryDataRefresh.objects.create(
            requested_start=start_date,
            requested_end=end_date,
        )
        processed_days = []
        warnings = []

        try:
            if options['cache_dir']:
                self._run(start_date, end_date, options['cache_dir'], run, processed_days, warnings)
            else:
                with TemporaryDirectory(prefix='nem-battery-') as directory:
                    self._run(start_date, end_date, Path(directory), run, processed_days, warnings)
        except (AEMODataError, OSError, ValueError) as exc:
            finish_refresh(run, processed_days, warnings, str(exc))
            raise CommandError(str(exc)) from exc

        finish_refresh(run, processed_days, warnings)
        style = self.style.WARNING if warnings else self.style.SUCCESS
        self.stdout.write(style(
            f'Battery refresh {run.status}: {start_date} to {end_date}; '
            f'{len(processed_days)} day(s), {len(warnings)} warning(s).'
        ))

    def _run(self, start_date, end_date, cache_dir, run, processed_days, warnings):
        self.stdout.write(f'Downloading AEMO sources for {start_date} to {end_date}...')
        sources = download_source_set(start_date, end_date, cache_dir)
        run.source_receipts = sources['receipts']
        run.save(update_fields=['source_receipts'])
        self.stdout.write('Parsing, validating, and calculating interval values...')
        refresh_range(
            start_date,
            end_date,
            sources,
            processed_days=processed_days,
            warnings=warnings,
        )
