from datetime import date, datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max

from ...aemo_fuel import (
    DEFAULT_GENERATION_REGISTER_URL, FuelSourceError, NEM_TIME,
    aggregate_dispatch_scada, download_dispatch_scada,
    download_generation_register, load_generation_register,
)
from ...models import FuelGenerationData


class Command(BaseCommand):
    help = 'Refresh daily NEM fuel generation directly from AEMO dispatch SCADA.'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=date.fromisoformat, help='First operating date, YYYY-MM-DD.')
        parser.add_argument('--end', type=date.fromisoformat, help='Last operating date, YYYY-MM-DD.')
        parser.add_argument('--cache-dir', type=Path, default=Path('.nem_cache'))
        parser.add_argument('--registry-file', type=Path, help='Use a reviewed local AEMO generation workbook.')
        parser.add_argument(
            '--registry-url',
            default=getattr(settings, 'NEM_GENERATION_REGISTER_URL', DEFAULT_GENERATION_REGISTER_URL),
        )
        parser.add_argument('--refresh-registry', action='store_true')
        parser.add_argument('--minimum-coverage', type=float, default=0.95)

    def handle(self, *args, **options):
        cache_dir = options['cache_dir']
        try:
            register_path = options['registry_file'] or download_generation_register(
                options['registry_url'], cache_dir, refresh=options['refresh_registry']
            )
            registry = load_generation_register(register_path)
        except FuelSourceError as exc:
            raise CommandError(str(exc)) from exc

        latest = FuelGenerationData.objects.aggregate(value=Max('timestamp'))['value']
        default_start = latest.astimezone(NEM_TIME).date() + timedelta(days=1) if latest else None
        # The daily archive is not guaranteed to exist by 09:00 the next
        # morning. A two-day lag matches the suite's battery source boundary
        # and prevents an expected publication delay from failing the timer.
        end_date = options['end'] or (datetime.now(NEM_TIME).date() - timedelta(days=2))
        start_date = options['start'] or default_start or (end_date - timedelta(days=6))
        if end_date < start_date:
            self.stdout.write(self.style.SUCCESS('Fuel-mix data is already current.'))
            return
        if (end_date - start_date).days > 370:
            raise CommandError('Refusing an implicit backfill longer than 370 days; pass a narrower range.')

        completed = 0
        for operating_date in _date_range(start_date, end_date):
            try:
                archive = download_dispatch_scada(operating_date, cache_dir)
                report = aggregate_dispatch_scada(archive, operating_date, registry)
            except FuelSourceError as exc:
                raise CommandError(str(exc)) from exc
            if not report['totals']:
                raise CommandError(f'{operating_date}: dispatch SCADA produced no mapped generation.')
            if report['coverage'] < options['minimum_coverage']:
                unknown = ', '.join(
                    f'{duid} {mwh:.0f} MWh' for duid, mwh in report['unknown'][:8]
                )
                raise CommandError(
                    f'{operating_date}: DUID coverage {report["coverage"]:.1%} is below '
                    f'{options["minimum_coverage"]:.1%}. Largest unmapped: {unknown}'
                )

            timestamp = datetime.combine(operating_date, time(hour=12), tzinfo=NEM_TIME)
            with transaction.atomic():
                day_end = timestamp + timedelta(days=1)
                FuelGenerationData.objects.filter(
                    timestamp__gte=timestamp.replace(hour=0),
                    timestamp__lt=day_end.replace(hour=0),
                ).delete()
                FuelGenerationData.objects.bulk_create([
                    FuelGenerationData(
                        timestamp=timestamp,
                        state=state,
                        fuel_type=fuel,
                        supply_mw=round(mwh, 3),
                    )
                    for (state, fuel), mwh in sorted(report['totals'].items())
                ])
            completed += 1
            self.stdout.write(
                f'{operating_date}: {len(report["totals"])} state/fuel totals, '
                f'{report["mapped_mwh"]:,.0f} MWh, {report["coverage"]:.1%} DUID coverage.'
            )

        self.stdout.write(self.style.SUCCESS(
            f'Fuel mix refreshed for {completed} day(s), {start_date} to {end_date}.'
        ))


def _date_range(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
