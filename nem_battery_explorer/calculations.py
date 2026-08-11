"""Transparent MVP calculations for operational battery value."""

INTERVAL_HOURS = 1 / 12
CALCULATION_VERSION = 'mvp-v1'


def calculate_interval(scada_mw, rrp, fcas_enablement, fcas_prices, storage_mwh, capacity_mwh):
    flags = []
    if scada_mw is None:
        charge_mwh = discharge_mwh = 0.0
        energy_value = 0.0
        charging_cost = discharge_value = 0.0
        flags.append('missing_scada')
    else:
        signed_mwh = scada_mw * INTERVAL_HOURS
        charge_mwh = max(-signed_mwh, 0.0)
        discharge_mwh = max(signed_mwh, 0.0)
        energy_value = signed_mwh * rrp
        charging_cost = charge_mwh * rrp
        discharge_value = discharge_mwh * rrp

    gross_fcas_value = sum(
        max(float(fcas_enablement.get(service, 0.0) or 0.0), 0.0)
        * float(fcas_prices.get(service, 0.0) or 0.0)
        * INTERVAL_HOURS
        for service in fcas_enablement
    )

    if storage_mwh is None:
        flags.append('missing_storage')
    else:
        if storage_mwh < 0:
            flags.append('storage_below_zero')
        if capacity_mwh and storage_mwh > capacity_mwh * 1.02:
            flags.append('storage_above_public_capacity')

    return {
        'charge_mwh': charge_mwh,
        'discharge_mwh': discharge_mwh,
        'charging_cost': charging_cost,
        'discharge_value': discharge_value,
        'energy_market_value': energy_value,
        'gross_fcas_value': gross_fcas_value,
        'observable_gross_value': energy_value + gross_fcas_value,
        'quality_flags': flags,
    }


def summarise_day(intervals, capacity_mwh, expected_intervals=288):
    intervals = list(intervals)
    scada_values = [row.scada_mw for row in intervals if row.scada_mw is not None]
    storage_values = [
        row.energy_storage_mwh for row in intervals if row.energy_storage_mwh is not None
    ]
    charge = sum(row.charge_mwh for row in intervals)
    discharge = sum(row.discharge_mwh for row in intervals)
    discharge_value = sum(row.discharge_value for row in intervals)
    observable_value = sum(row.observable_gross_value for row in intervals)
    coverage_notes = []
    if len(intervals) != expected_intervals:
        coverage_notes.append(
            f'Expected {expected_intervals} unit dispatch intervals; found {len(intervals)}.'
        )
    if len(scada_values) != expected_intervals:
        coverage_notes.append(
            f'SCADA coverage is {len(scada_values)} of {expected_intervals} unit intervals.'
        )
    if len(storage_values) != expected_intervals:
        coverage_notes.append(
            f'Storage coverage is {len(storage_values)} of {expected_intervals} unit intervals.'
        )
    flagged = sorted({flag for row in intervals for flag in row.quality_flags})
    advisory_notes = [
        flag.replace('_', ' ') for flag in flagged
        if flag not in {'missing_storage', 'missing_scada'}
    ]
    notes = coverage_notes + advisory_notes

    top_five = sorted((row.observable_gross_value for row in intervals), reverse=True)[:5]
    return {
        'interval_count': len(intervals),
        'scada_interval_count': len(scada_values),
        'storage_interval_count': len(storage_values),
        'charge_mwh': charge,
        'discharge_mwh': discharge,
        'throughput_mwh': charge + discharge,
        'equivalent_cycles': discharge / capacity_mwh if capacity_mwh else 0.0,
        'charging_cost': sum(row.charging_cost for row in intervals),
        'discharge_value': discharge_value,
        'energy_market_value': sum(row.energy_market_value for row in intervals),
        'gross_fcas_value': sum(row.gross_fcas_value for row in intervals),
        'observable_gross_value': observable_value,
        'value_per_discharge_mwh': observable_value / discharge if discharge else None,
        'capture_price': discharge_value / discharge if discharge else None,
        'peak_charge_mw': abs(min(scada_values)) if scada_values and min(scada_values) < 0 else 0.0,
        'peak_discharge_mw': max(scada_values) if scada_values else 0.0,
        'min_storage_mwh': min(storage_values) if storage_values else None,
        'max_storage_mwh': max(storage_values) if storage_values else None,
        'min_state_of_charge_pct': min(storage_values) / capacity_mwh * 100 if storage_values and capacity_mwh else None,
        'max_state_of_charge_pct': max(storage_values) / capacity_mwh * 100 if storage_values and capacity_mwh else None,
        'top_five_interval_value_share': sum(top_five) / observable_value if observable_value > 0 else None,
        'quality_status': 'complete' if not coverage_notes else 'partial',
        'quality_notes': notes,
        'calculation_version': CALCULATION_VERSION,
    }
