from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import urlencode

from django.db.models import Max, Min
from django.shortcuts import render

from .aemo import FCAS_DISPATCH_FIELDS, NEM_TIME
from .insights import (
    FLEET_POINTS,
    FLEET_TOTAL_MW,
    FLEET_TOTAL_MWH,
    FLEET_TOTALS,
    MARKET_TREND,
    opportunity_benchmark,
)
from .models import BatteryAsset, BatteryDailySummary, BatteryDataRefresh, BatteryDispatchInterval


FCAS_LABELS = {
    'raise_1s': 'Raise 1 second',
    'raise_6s': 'Raise 6 second',
    'raise_60s': 'Raise 60 second',
    'raise_5m': 'Raise 5 minute',
    'raise_reg': 'Raise regulation',
    'lower_1s': 'Lower 1 second',
    'lower_6s': 'Lower 6 second',
    'lower_60s': 'Lower 60 second',
    'lower_5m': 'Lower 5 minute',
    'lower_reg': 'Lower regulation',
}

PERIOD_LABELS = {
    'week': 'Week',
    'quarter': '3 Months',
}


def _requested_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _period_options(period, summaries):
    chronological = sorted(summaries, key=lambda item: item.operating_date)
    if period == 'week':
        dates = [item.operating_date for item in chronological if item.operating_date.weekday() == 5]
        if chronological and chronological[-1].operating_date not in dates:
            dates.append(chronological[-1].operating_date)
        return [{'date': day, 'label': f'Week ending {day.day} {day:%b %Y}'} for day in dates]
    month_ends = {}
    for item in chronological:
        month_ends[(item.operating_date.year, item.operating_date.month)] = item.operating_date
    return [
        {'date': day, 'label': f'3 months to {day.day} {day:%b %Y}'}
        for day in month_ends.values()
    ]


def _period_bounds(period, anchor):
    if period == 'week':
        return anchor - timedelta(days=6), anchor
    return anchor - timedelta(days=90), anchor


def _period_summary(rows, start, end):
    benchmark_rows = [row for row in rows if row.benchmark_energy_value is not None]
    benchmark_value = sum(row.benchmark_energy_value for row in benchmark_rows) if benchmark_rows else None
    actual_energy_value = sum(row.energy_market_value for row in benchmark_rows)
    best_day = max(rows, key=lambda row: row.observable_gross_value, default=None)
    expected_days = (end - start).days + 1
    return {
        'start': start,
        'end': end,
        'days': len(rows),
        'expected_days': expected_days,
        'coverage_pct': len(rows) / expected_days * 100 if expected_days else 0,
        'complete_days': sum(row.quality_status == BatteryDailySummary.COMPLETE for row in rows),
        'benchmark_days': len(benchmark_rows),
        'observable_value': sum(row.observable_gross_value for row in rows),
        'energy_market_value': sum(row.energy_market_value for row in rows),
        'gross_fcas_value': sum(row.gross_fcas_value for row in rows),
        'charging_cost': sum(row.charging_cost for row in rows),
        'discharge_value': sum(row.discharge_value for row in rows),
        'charge_mwh': sum(row.charge_mwh for row in rows),
        'discharge_mwh': sum(row.discharge_mwh for row in rows),
        'equivalent_cycles': sum(row.equivalent_cycles for row in rows),
        'benchmark_value': benchmark_value,
        'capture_ratio': actual_energy_value / benchmark_value if benchmark_value and benchmark_value > 0 else None,
        'capture_pct': actual_energy_value / benchmark_value * 100 if benchmark_value and benchmark_value > 0 else None,
        'best_day': best_day,
    }


def _period_payload(rows, period):
    if period == 'week':
        return [
            {
                'key': row.operating_date.isoformat(),
                'label': f'{row.operating_date.day} {row.operating_date:%b}',
                'charge_mwh': row.charge_mwh,
                'discharge_mwh': row.discharge_mwh,
                'observable_value': row.observable_gross_value,
                'energy_value': row.energy_market_value,
                'fcas_value': row.gross_fcas_value,
                'cycles': row.equivalent_cycles,
                'benchmark_value': row.benchmark_energy_value,
                'capture_pct': row.opportunity_capture_ratio * 100 if row.opportunity_capture_ratio is not None else None,
                'quality': row.quality_status,
            }
            for row in rows
        ]

    weeks = {}
    for row in rows:
        natural_week_end = row.operating_date + timedelta(
            days=(5 - row.operating_date.weekday()) % 7
        )
        week_end = min(natural_week_end, rows[-1].operating_date)
        key = week_end.isoformat()
        item = weeks.setdefault(key, {
            'key': key,
            'label': f'W/E {week_end.day} {week_end:%b}',
            'charge_mwh': 0.0,
            'discharge_mwh': 0.0,
            'observable_value': 0.0,
            'energy_value': 0.0,
            'fcas_value': 0.0,
            'cycles': 0.0,
            'benchmark_value': 0.0,
            'benchmark_days': 0,
            'benchmark_actual_value': 0.0,
            'quality': BatteryDailySummary.COMPLETE,
        })
        item['charge_mwh'] += row.charge_mwh
        item['discharge_mwh'] += row.discharge_mwh
        item['observable_value'] += row.observable_gross_value
        item['energy_value'] += row.energy_market_value
        item['fcas_value'] += row.gross_fcas_value
        item['cycles'] += row.equivalent_cycles
        if row.benchmark_energy_value is not None:
            item['benchmark_value'] += row.benchmark_energy_value
            item['benchmark_actual_value'] += row.energy_market_value
            item['benchmark_days'] += 1
        if row.quality_status == BatteryDailySummary.PARTIAL:
            item['quality'] = BatteryDailySummary.PARTIAL
    payload = []
    for item in weeks.values():
        benchmark = item['benchmark_value'] if item['benchmark_days'] else None
        item['benchmark_value'] = benchmark
        item['capture_pct'] = item['benchmark_actual_value'] / benchmark * 100 if benchmark and benchmark > 0 else None
        item.pop('benchmark_days')
        item.pop('benchmark_actual_value')
        payload.append(item)
    return payload


def _comparison_payload(start, end, selected_asset):
    rows = BatteryDailySummary.objects.filter(
        operating_date__range=(start, end),
    ).select_related('asset').order_by('asset__name', 'operating_date')
    grouped = {}
    for row in rows:
        item = grouped.setdefault(row.asset_id, {
            'asset': row.asset.name,
            'slug': row.asset.slug,
            'region': row.asset.region,
            'value': 0.0,
            'discharge_mwh': 0.0,
            'cycles': 0.0,
            'selected': row.asset_id == selected_asset.id,
        })
        item['value'] += row.observable_gross_value
        item['discharge_mwh'] += row.discharge_mwh
        item['cycles'] += row.equivalent_cycles
    for item in grouped.values():
        item['value_per_mwh'] = (
            item['value'] / item['discharge_mwh'] if item['discharge_mwh'] else None
        )
    return sorted(grouped.values(), key=lambda item: item['value'], reverse=True)


def _interval_payload(rows, capacity_mwh):
    buckets = {}
    fcas_totals = defaultdict(float)
    for row in rows:
        bucket = buckets.setdefault(row.interval_end, {
            'scada': [],
            'target': [],
            'storage': [],
            'rrp': row.regional_price.rrp,
            'energy_value': 0.0,
            'fcas_value': 0.0,
            'observable_value': 0.0,
            'flags': set(),
        })
        if row.scada_mw is not None:
            bucket['scada'].append(row.scada_mw)
        if row.dispatch_target_mw is not None:
            bucket['target'].append(row.dispatch_target_mw)
        if row.energy_storage_mwh is not None:
            bucket['storage'].append(row.energy_storage_mwh)
        bucket['energy_value'] += row.energy_market_value
        bucket['fcas_value'] += row.gross_fcas_value
        bucket['observable_value'] += row.observable_gross_value
        bucket['flags'].update(row.quality_flags)
        for service in FCAS_DISPATCH_FIELDS:
            enabled = max(float(row.fcas_enablement_mw.get(service, 0.0) or 0.0), 0.0)
            price = float(row.regional_price.fcas_prices.get(service, 0.0) or 0.0)
            fcas_totals[service] += enabled * price / 12

    payload = []
    for when, bucket in sorted(buckets.items()):
        nem_when = when.astimezone(NEM_TIME)
        label = '24:00' if nem_when.hour == 0 and nem_when.minute == 0 else nem_when.strftime('%H:%M')
        storage = sum(bucket['storage']) if bucket['storage'] else None
        payload.append({
            'time': label,
            'scada_mw': sum(bucket['scada']) if bucket['scada'] else None,
            'target_mw': sum(bucket['target']) if bucket['target'] else None,
            'rrp': bucket['rrp'],
            'storage_mwh': storage,
            'storage_pct': storage / capacity_mwh * 100 if storage is not None and capacity_mwh else None,
            'energy_value': bucket['energy_value'],
            'fcas_value': bucket['fcas_value'],
            'observable_value': bucket['observable_value'],
            'flags': sorted(bucket['flags']),
        })
    return payload, fcas_totals


def _fleet_context(assets, published_through):
    covered_slugs = {asset.slug for asset in assets}
    region_covered = defaultdict(lambda: {'mw': 0.0, 'mwh': 0.0, 'assets': 0})
    covered_mw = 0.0
    covered_mwh = 0.0
    for asset in assets:
        registrations = [
            registration for registration in asset.registrations.all()
            if registration.is_effective_on(published_through)
        ]
        asset_mw = sum(float(registration.power_capacity_mw) for registration in registrations)
        asset_mwh = sum(float(registration.storage_capacity_mwh) for registration in registrations)
        covered_mw += asset_mw
        covered_mwh += asset_mwh
        region_covered[asset.region]['mw'] += asset_mw
        region_covered[asset.region]['mwh'] += asset_mwh
        region_covered[asset.region]['assets'] += 1

    regions = []
    for region, totals in FLEET_TOTALS.items():
        covered = region_covered[region]
        regions.append({
            'region': region,
            'label': totals['label'],
            'total_mw': totals['mw'],
            'total_mwh': totals['mwh'],
            'covered_mw': covered['mw'],
            'covered_mwh': covered['mwh'],
            'covered_assets': covered['assets'],
            'coverage_pct': covered['mw'] / totals['mw'] * 100 if totals['mw'] else 0.0,
        })

    points = []
    for point in FLEET_POINTS:
        covered = point['slug'] in covered_slugs
        if point['slug'] == 'melbourne-renewable-energy-hub':
            covered = {'mreh-a1', 'mreh-a2', 'mreh-a3'}.issubset(covered_slugs)
        points.append({**point, 'duration': point['mwh'] / point['mw'], 'covered': covered})
    return {
        'regions': regions,
        'points': points,
        'covered_mw': covered_mw,
        'covered_mwh': covered_mwh,
        'total_mw': FLEET_TOTAL_MW,
        'total_mwh': FLEET_TOTAL_MWH,
        'power_coverage_pct': covered_mw / FLEET_TOTAL_MW * 100,
        'energy_coverage_pct': covered_mwh / FLEET_TOTAL_MWH * 100,
    }


def explorer(request):
    assets = list(
        BatteryAsset.objects.annotate(
            first_date=Min('daily_summaries__operating_date'),
            last_date=Max('daily_summaries__operating_date'),
        ).filter(last_date__isnull=False).prefetch_related('registrations')
    )
    if not assets:
        return render(request, 'nem_battery_explorer/explorer.html', {
            'has_data': False,
            'assets': [],
        })

    asset_lookup = {asset.slug: asset for asset in assets}
    published_through = max(asset.last_date for asset in assets)
    selected_asset = asset_lookup.get(request.GET.get('asset'))
    if selected_asset is None:
        selected_asset = asset_lookup.get('victorian-big-battery', assets[0])

    summaries = list(
        BatteryDailySummary.objects.filter(asset=selected_asset).order_by('-operating_date')
    )
    summary_lookup = {summary.operating_date: summary for summary in summaries}

    period = request.GET.get('period', 'week')
    if period not in PERIOD_LABELS:
        period = 'week'
    period_options = _period_options(period, summaries)
    requested_date = _requested_date(request.GET.get('date'))
    option_dates = {option['date'] for option in period_options}
    if requested_date not in option_dates:
        same_month = [
            option['date'] for option in period_options
            if requested_date
            and option['date'].year == requested_date.year
            and option['date'].month == requested_date.month
        ]
        if same_month:
            requested_date = same_month[-1]
        elif requested_date and period == 'week':
            requested_date = min(
                option_dates,
                key=lambda option_date: abs((option_date - requested_date).days),
            )
        else:
            requested_date = period_options[-1]['date']
    period_start, period_end = _period_bounds(period, requested_date)
    period_summaries = sorted(
        [
            summary for summary in summaries
            if period_start <= summary.operating_date <= period_end
        ],
        key=lambda summary: summary.operating_date,
    )
    period_overview = _period_summary(period_summaries, period_start, period_end)
    period_overview['value_per_discharge_mwh'] = (
        period_overview['observable_value'] / period_overview['discharge_mwh']
        if period_overview['discharge_mwh'] else None
    )
    period_payload = _period_payload(period_summaries, period)

    selected_date = max(
        (day for day in summary_lookup if day <= period_end),
        default=summaries[0].operating_date,
    )
    selected_summary = summary_lookup[selected_date]

    if period == 'week':
        period_heading = f'Week ending {period_end.day} {period_end:%B %Y}'
        period_selector_label = 'Week ending'
    else:
        period_heading = f'3 months to {period_end.day} {period_end:%B %Y}'
        period_selector_label = '3-month period ending'

    period_tabs = []
    for key, label in PERIOD_LABELS.items():
        period_tabs.append({
            'key': key,
            'label': label,
            'active': key == period,
            'url': '?' + urlencode({
                'asset': selected_asset.slug,
                'period': key,
                'date': period_end.isoformat(),
            }),
        })

    rows = list(
        BatteryDispatchInterval.objects.filter(
            registration__asset=selected_asset,
            operating_date=selected_date,
        ).select_related('registration', 'regional_price')
    )
    registrations = {row.registration_id: row.registration for row in rows}
    capacity_mw = sum(float(item.power_capacity_mw) for item in registrations.values())
    capacity_mwh = sum(float(item.storage_capacity_mwh) for item in registrations.values())
    interval_payload, fcas_totals = _interval_payload(rows, capacity_mwh)
    opportunity = opportunity_benchmark(interval_payload, capacity_mw, capacity_mwh)
    fleet = _fleet_context(assets, published_through)

    comparison_payload = _comparison_payload(period_start, period_end, selected_asset)

    fcas_breakdown = [
        {'key': service, 'label': FCAS_LABELS[service], 'value': fcas_totals.get(service, 0.0)}
        for service in FCAS_DISPATCH_FIELDS
        if abs(fcas_totals.get(service, 0.0)) >= 0.005
    ]
    refresh = BatteryDataRefresh.objects.filter(finished_at__isnull=False).first()
    return render(request, 'nem_battery_explorer/explorer.html', {
        'has_data': True,
        'assets': assets,
        'selected_asset': selected_asset,
        'selected_date': selected_date,
        'published_through': published_through,
        'period': period,
        'period_label': PERIOD_LABELS[period],
        'period_heading': period_heading,
        'period_selector_label': period_selector_label,
        'period_tabs': period_tabs,
        'period_options': period_options,
        'period_start': period_start,
        'period_end': period_end,
        'period_overview': period_overview,
        'period_payload': period_payload,
        'selected_summary': selected_summary,
        'capacity_mw': capacity_mw,
        'capacity_mwh': capacity_mwh,
        'registration_count': len(registrations),
        'duration_hours': capacity_mwh / capacity_mw if capacity_mw else None,
        'interval_payload': interval_payload,
        'opportunity': opportunity,
        'fleet': fleet,
        'market_trend': MARKET_TREND,
        'comparison_payload': comparison_payload,
        'fcas_breakdown': fcas_breakdown,
        'refresh': refresh,
    })


def guide(request):
    return render(request, 'nem_battery_explorer/guide.html')
