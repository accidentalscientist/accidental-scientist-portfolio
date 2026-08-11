from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = 'Refresh every data-backed view in the NEM Dashboard suite.'

    def add_arguments(self, parser):
        parser.add_argument('--skip-fuel', action='store_true')
        parser.add_argument('--skip-price', action='store_true')
        parser.add_argument('--skip-battery', action='store_true')
        parser.add_argument('--skip-gas', action='store_true')

    def handle(self, *args, **options):
        failures = []

        if not options['skip_fuel']:
            self._run(failures, 'Fuel mix', 'refresh_fuel_mix', cache_dir='.nem_cache')

        if not options['skip_price']:
            self._run(failures, 'Settled prices', 'ingest_nem_prices')
            self._run(
                failures, 'Observed weather', 'ingest_nem_weather',
                kind='observed', months=1,
            )
            # Reanalysis lags several days. Archived issue-time forecasts fill
            # that tail so a Monday run can build every leakage-safe weekly
            # feature instead of publishing a truncated learned-model horizon.
            self._run(
                failures, 'Recent archived weather forecasts', 'ingest_nem_weather',
                kind='forecast', months=1,
            )
            self._run(failures, 'Forward weather', 'ingest_nem_weather', forward=True)
            self._publish_missing_forecasts(failures)

        if not options['skip_battery']:
            self._run(
                failures, 'Battery dispatch', 'refresh_battery_data',
                cache_dir='.battery_cache',
            )

        if not options['skip_gas']:
            # Static system reference data changes slowly; refresh it on Monday.
            # The rolling flow and outlook files are ingested on every suite run.
            self._run(
                failures, 'Gas system', 'ingest_gbb_flows',
                weekly=timezone.localdate().weekday() == 0,
            )
            self._run(failures, 'Gas coverage audit', 'check_gas_coverage', quiet=True)

        if failures:
            raise CommandError('NEM suite refresh completed with failures: ' + '; '.join(failures))
        self.stdout.write(self.style.SUCCESS('NEM Dashboard suite refresh completed.'))

    def _publish_missing_forecasts(self, failures):
        try:
            from nem_price_lab.models import ForecastRun
            from nem_price_lab.services import available_regions, most_recent_sunday

            origin = most_recent_sunday(timezone.now())
            missing = [
                region for region in available_regions()
                if not ForecastRun.objects.filter(region=region, issued_at=origin).exists()
            ]
            if missing:
                self._run(
                    failures, 'Weekly price forecast', 'run_price_forecast', region=missing
                )
            else:
                self.stdout.write(f'Weekly price forecast: origin {origin:%Y-%m-%d} already published.')
        except Exception as exc:
            failures.append(f'Weekly price forecast ({exc})')
            self.stderr.write(self.style.ERROR(f'Weekly price forecast: {exc}'))

    def _run(self, failures, label, command, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING(label))
        try:
            call_command(command, **kwargs)
        except (Exception, SystemExit) as exc:
            failures.append(f'{label} ({exc})')
            self.stderr.write(self.style.ERROR(f'{label}: {exc}'))
