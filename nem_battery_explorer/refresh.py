from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .aemo import (
    AEMODataError,
    interval_belongs_to,
    parse_dispatch_prices,
    parse_dispatch_scada,
    parse_next_day_dispatch,
)
from .calculations import CALCULATION_VERSION, calculate_interval, summarise_day
from .insights import BENCHMARK_VERSION, benchmark_rows_from_dispatch, opportunity_benchmark
from .models import (
    BatteryDailySummary,
    BatteryDataRefresh,
    BatteryDispatchInterval,
    BatteryRegistration,
    RegionPriceInterval,
)


def _active_registrations(start_date, end_date):
    return list(
        BatteryRegistration.objects.select_related('asset')
        .filter(effective_from__lte=end_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=start_date))
        .order_by('asset_id', 'duid')
    )


def _validate_source_coverage(operating_date, registrations, prices, dispatch):
    errors = []
    regions = {registration.asset.region for registration in registrations}
    for region in regions:
        count = sum(
            1 for (row_region, when) in prices
            if row_region == region and interval_belongs_to(when, operating_date)
        )
        if count != 288:
            errors.append(f'{region} has {count} price intervals; expected 288.')
    for registration in registrations:
        count = sum(
            1 for (duid, when) in dispatch
            if duid == registration.duid and interval_belongs_to(when, operating_date)
        )
        if count != 288:
            errors.append(f'{registration.duid} has {count} dispatch intervals; expected 288.')
    if errors:
        raise AEMODataError(f'{operating_date}: ' + ' '.join(errors))


def refresh_range(
    start_date,
    end_date,
    source_paths,
    *,
    processed_days=None,
    warnings=None,
):
    # The command passes its audit lists in so progress survives an exception on
    # a later day. Each operating day is atomic, but the requested range is not.
    if processed_days is None:
        processed_days = []
    if warnings is None:
        warnings = []
    registrations = _active_registrations(start_date, end_date)
    if not registrations:
        raise AEMODataError('No effective battery registrations cover the requested dates.')

    duids = {registration.duid for registration in registrations}
    regions = {registration.asset.region for registration in registrations}
    dispatch = parse_next_day_dispatch(source_paths['next_day'].values(), duids)
    operating_date = start_date
    while operating_date <= end_date:
        day_registrations = [
            registration for registration in registrations
            if registration.is_effective_on(operating_date)
        ]
        prices = parse_dispatch_prices(source_paths['prices'][operating_date], regions)
        scada = parse_dispatch_scada(source_paths['scada'][operating_date], duids)
        _validate_source_coverage(operating_date, day_registrations, prices, dispatch)
        day_warnings = persist_operating_day(
            operating_date,
            day_registrations,
            prices,
            dispatch,
            scada,
        )
        warnings.extend(day_warnings)
        processed_days.append(operating_date)
        operating_date += timedelta(days=1)
    return processed_days, warnings


@transaction.atomic
def persist_operating_day(operating_date, registrations, prices, dispatch, scada):
    price_objects = []
    for (region, when), row in prices.items():
        if interval_belongs_to(when, operating_date):
            price_objects.append(RegionPriceInterval(
                operating_date=operating_date,
                region=region,
                interval_end=when,
                rrp=row['rrp'],
                fcas_prices=row['fcas_prices'],
                source_file=row['source_file'],
            ))
    RegionPriceInterval.objects.bulk_create(
        price_objects,
        update_conflicts=True,
        update_fields=['operating_date', 'rrp', 'fcas_prices', 'source_file'],
        unique_fields=['region', 'interval_end'],
    )
    stored_prices = {
        (row.region, row.interval_end): row
        for row in RegionPriceInterval.objects.filter(operating_date=operating_date)
    }

    interval_objects = []
    for registration in registrations:
        capacity_mwh = float(registration.storage_capacity_mwh)
        region_prices = sorted(
            (
                (when, row) for (region, when), row in stored_prices.items()
                if region == registration.asset.region
            ),
            key=lambda item: item[0],
        )
        for when, price_record in region_prices:
            dispatch_row = dispatch.get((registration.duid, when))
            if dispatch_row is None:
                continue
            scada_row = scada.get((registration.duid, when), {})
            scada_mw = scada_row.get('scada_mw')
            calculated = calculate_interval(
                scada_mw,
                price_record.rrp,
                dispatch_row['fcas_enablement_mw'],
                price_record.fcas_prices,
                dispatch_row['energy_storage_mwh'],
                capacity_mwh,
            )
            interval_objects.append(BatteryDispatchInterval(
                registration=registration,
                regional_price=price_record,
                operating_date=operating_date,
                interval_end=when,
                initial_mw=dispatch_row['initial_mw'],
                dispatch_target_mw=dispatch_row['dispatch_target_mw'],
                scada_mw=scada_mw,
                availability_mw=dispatch_row['availability_mw'],
                initial_energy_storage_mwh=dispatch_row['initial_energy_storage_mwh'],
                energy_storage_mwh=dispatch_row['energy_storage_mwh'],
                fcas_enablement_mw=dispatch_row['fcas_enablement_mw'],
                dispatch_source_file=dispatch_row['source_file'],
                scada_source_file=scada_row.get('source_file', ''),
                **calculated,
            ))
    BatteryDispatchInterval.objects.bulk_create(
        interval_objects,
        update_conflicts=True,
        update_fields=[
            'regional_price', 'operating_date', 'initial_mw', 'dispatch_target_mw',
            'scada_mw', 'availability_mw', 'initial_energy_storage_mwh',
            'energy_storage_mwh', 'fcas_enablement_mw', 'charge_mwh',
            'discharge_mwh', 'charging_cost', 'discharge_value',
            'energy_market_value', 'gross_fcas_value', 'observable_gross_value',
            'quality_flags', 'dispatch_source_file', 'scada_source_file',
        ],
        unique_fields=['registration', 'interval_end'],
    )

    warnings = []
    asset_ids = sorted({registration.asset_id for registration in registrations})
    for asset_id in asset_ids:
        asset_registrations = [item for item in registrations if item.asset_id == asset_id]
        capacity_mw = sum(float(item.power_capacity_mw) for item in asset_registrations)
        capacity_mwh = sum(float(item.storage_capacity_mwh) for item in asset_registrations)
        rows = list(
            BatteryDispatchInterval.objects.filter(
                registration__asset_id=asset_id,
                operating_date=operating_date,
            ).select_related('registration', 'regional_price')
        )
        summary = summarise_day(
            rows,
            capacity_mwh,
            expected_intervals=288 * len(asset_registrations),
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
        asset = asset_registrations[0].asset
        BatteryDailySummary.objects.update_or_create(
            asset=asset,
            operating_date=operating_date,
            defaults=summary,
        )
        if summary['quality_status'] == 'partial':
            warnings.extend(
                f'{asset.name} {operating_date}: {note}' for note in summary['quality_notes']
            )
    return warnings


def finish_refresh(run, processed_days, warnings, error=''):
    run.finished_at = timezone.now()
    run.completed_through = max(processed_days) if processed_days else None
    run.warnings = warnings
    run.error = error
    if error:
        run.status = BatteryDataRefresh.PARTIAL if processed_days else BatteryDataRefresh.FAILED
    elif warnings:
        run.status = BatteryDataRefresh.PARTIAL
    else:
        run.status = BatteryDataRefresh.COMPLETE
    run.calculation_version = CALCULATION_VERSION
    run.save(update_fields=[
        'finished_at', 'completed_through', 'warnings', 'error', 'status',
        'calculation_version',
    ])
