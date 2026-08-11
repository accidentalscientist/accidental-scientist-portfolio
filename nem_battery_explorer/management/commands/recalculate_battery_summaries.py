from django.core.management.base import BaseCommand

from nem_battery_explorer.calculations import summarise_day
from nem_battery_explorer.insights import (
    BENCHMARK_VERSION,
    benchmark_rows_from_dispatch,
    opportunity_benchmark,
)
from nem_battery_explorer.models import (
    BatteryAsset,
    BatteryDailySummary,
    BatteryDispatchInterval,
)


class Command(BaseCommand):
    help = 'Recalculate stored ChargeTrace daily summaries without downloading AEMO files.'

    def handle(self, *args, **options):
        recalculated = 0
        assets = BatteryAsset.objects.prefetch_related('registrations').all()
        for asset in assets:
            operating_dates = list(
                BatteryDispatchInterval.objects.filter(registration__asset=asset)
                .values_list('operating_date', flat=True)
                .distinct()
                .order_by('operating_date')
            )
            registrations = list(asset.registrations.all())
            for operating_date in operating_dates:
                active = [
                    registration for registration in registrations
                    if registration.is_effective_on(operating_date)
                ]
                capacity_mwh = sum(float(item.storage_capacity_mwh) for item in active)
                capacity_mw = sum(float(item.power_capacity_mw) for item in active)
                rows = list(
                    BatteryDispatchInterval.objects.filter(
                        registration__asset=asset,
                        operating_date=operating_date,
                    ).select_related('regional_price')
                )
                summary = summarise_day(
                    rows,
                    capacity_mwh,
                    expected_intervals=288 * len(active),
                )
                benchmark = opportunity_benchmark(
                    benchmark_rows_from_dispatch(rows),
                    capacity_mw,
                    capacity_mwh,
                )
                summary.update({
                    'benchmark_energy_value': benchmark['benchmark_value'],
                    'opportunity_capture_ratio': benchmark['capture_ratio'],
                    'benchmark_version': BENCHMARK_VERSION,
                })
                BatteryDailySummary.objects.update_or_create(
                    asset=asset,
                    operating_date=operating_date,
                    defaults=summary,
                )
                recalculated += 1
        self.stdout.write(self.style.SUCCESS(f'Recalculated {recalculated} battery daily summaries.'))
