"""Public-data research layers used by the ChargeTrace interface.

The benchmark is deliberately simple and reproducible. It is not intended to
reconstruct a participant's optimiser, contracts or battery degradation model.
"""

from math import sqrt


INTERVAL_HOURS = 1 / 12
ROUND_TRIP_EFFICIENCY = 0.90
SOC_STEPS = 200
BENCHMARK_VERSION = 'energy-dp-v1'


FLEET_TOTALS = {
    'NSW1': {'label': 'New South Wales', 'mw': 979.27, 'mwh': 2961.54},
    'QLD1': {'label': 'Queensland', 'mw': 2147.78, 'mwh': 4331.78},
    'SA1': {'label': 'South Australia', 'mw': 1076.65, 'mwh': 1752.97},
    'VIC1': {'label': 'Victoria', 'mw': 1743.48, 'mwh': 3337.37},
    'TAS1': {'label': 'Tasmania', 'mw': 0.0, 'mwh': 0.0},
}
FLEET_TOTAL_MW = 5947.18
FLEET_TOTAL_MWH = 12383.66


FLEET_POINTS = [
    {'slug': 'melbourne-renewable-energy-hub', 'name': 'Melbourne Renewable Energy Hub', 'region': 'VIC1', 'mw': 647.92, 'mwh': 1600.48},
    {'slug': 'western-downs-battery', 'name': 'Western Downs Battery', 'region': 'QLD1', 'mw': 509.60, 'mwh': 1019.20},
    {'slug': 'eraring-big-battery', 'name': 'Eraring Big Battery', 'region': 'NSW1', 'mw': 460.00, 'mwh': 1773.00},
    {'slug': 'tarong-bess', 'name': 'Tarong BESS', 'region': 'QLD1', 'mw': 300.00, 'mwh': 600.00},
    {'slug': 'victorian-big-battery', 'name': 'Victorian Big Battery', 'region': 'VIC1', 'mw': 300.00, 'mwh': 470.00},
    {'slug': 'swanbank-bess', 'name': 'Swanbank BESS', 'region': 'QLD1', 'mw': 266.34, 'mwh': 531.30},
    {'slug': 'supernode-bess', 'name': 'Supernode BESS', 'region': 'QLD1', 'mw': 259.92, 'mwh': 619.40},
    {'slug': 'torrens-island-bess', 'name': 'Torrens Island BESS', 'region': 'SA1', 'mw': 250.70, 'mwh': 249.61},
    {'slug': 'rangebank-bess', 'name': 'Rangebank BESS', 'region': 'VIC1', 'mw': 224.00, 'mwh': 400.00},
    {'slug': 'brendale-bess', 'name': 'Brendale BESS', 'region': 'QLD1', 'mw': 204.96, 'mwh': 409.92},
    {'slug': 'blyth-bess', 'name': 'Blyth BESS', 'region': 'SA1', 'mw': 200.32, 'mwh': 400.00},
    {'slug': 'hazelwood-bess', 'name': 'Hazelwood BESS', 'region': 'VIC1', 'mw': 200.07, 'mwh': 162.00},
    {'slug': 'greenbank-bess', 'name': 'Greenbank BESS', 'region': 'QLD1', 'mw': 200.00, 'mwh': 400.00},
    {'slug': 'koorangie-energy-storage-system', 'name': 'Koorangie Energy Storage System', 'region': 'VIC1', 'mw': 193.00, 'mwh': 385.00},
    {'slug': 'bungama-bess', 'name': 'Bungama BESS', 'region': 'SA1', 'mw': 150.00, 'mwh': 300.00},
    {'slug': 'hornsdale-power-reserve', 'name': 'Hornsdale Power Reserve', 'region': 'SA1', 'mw': 150.00, 'mwh': 178.30},
    {'slug': 'capital-battery', 'name': 'Capital Battery', 'region': 'NSW1', 'mw': 99.99, 'mwh': 199.98},
    {'slug': 'limondale-bess', 'name': 'Limondale BESS', 'region': 'NSW1', 'mw': 50.00, 'mwh': 400.00},
]


MARKET_TREND = [
    {'quarter': 'Q3 2025', 'average_discharge_mw': 215, 'price_spread': 123, 'revenue_m': 111.9},
    {'quarter': 'Q4 2025', 'average_discharge_mw': 268, 'price_spread': 104, 'revenue_m': 70.4},
    {'quarter': 'Q1 2026', 'average_discharge_mw': 359, 'price_spread': 121, 'revenue_m': 96.9},
    {'quarter': 'Q2 2026', 'average_discharge_mw': 476, 'price_spread': 51, 'revenue_m': 57.5},
]


def _percentile(values, fraction):
    ordered = sorted(value for value in values if value is not None)
    if not ordered:
        return None
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def benchmark_rows_from_dispatch(rows):
    """Aggregate one or more DUID rows to one physical-asset series."""

    buckets = {}
    for row in rows:
        bucket = buckets.setdefault(row.interval_end, {
            'time': row.interval_end.strftime('%H:%M'),
            'rrp': row.regional_price.rrp,
            'storage': [],
            'scada': [],
            'energy_value': 0.0,
        })
        if row.energy_storage_mwh is not None:
            bucket['storage'].append(row.energy_storage_mwh)
        if row.scada_mw is not None:
            bucket['scada'].append(row.scada_mw)
        bucket['energy_value'] += row.energy_market_value
    return [
        {
            'time': bucket['time'],
            'rrp': bucket['rrp'],
            'storage_mwh': sum(bucket['storage']) if bucket['storage'] else None,
            'scada_mw': sum(bucket['scada']) if bucket['scada'] else None,
            'energy_value': bucket['energy_value'],
        }
        for _, bucket in sorted(buckets.items())
    ]


def opportunity_benchmark(intervals, power_mw, capacity_mwh):
    """Return a price-only feasible hindsight schedule.

    A 201-level dynamic programme respects five-minute power, public storage
    capacity, a 90% round-trip efficiency assumption and the observed start and
    end storage levels. FCAS, bids, contracts, outages and degradation are not
    modelled, so the result is a public-data comparison rather than profit.
    """

    intervals = list(intervals)
    if not intervals or power_mw <= 0 or capacity_mwh <= 0:
        return {'rows': [], 'actual_value': 0.0, 'benchmark_value': None, 'capture_ratio': None}

    prices = [float(row.get('rrp') or 0.0) for row in intervals]
    storage = [row.get('storage_mwh') for row in intervals]
    observed = [float(value) for value in storage if value is not None]
    start_mwh = observed[0] if observed else capacity_mwh / 2
    end_mwh = observed[-1] if observed else start_mwh
    step_mwh = capacity_mwh / SOC_STEPS
    start_level = round(max(0.0, min(capacity_mwh, start_mwh)) / step_mwh)
    end_level = round(max(0.0, min(capacity_mwh, end_mwh)) / step_mwh)
    eta = sqrt(ROUND_TRIP_EFFICIENCY)
    interval_limit_mwh = power_mw * INTERVAL_HOURS
    max_charge_levels = max(0, int(interval_limit_mwh * eta / step_mwh + 1e-9))
    max_discharge_levels = max(0, int(interval_limit_mwh / eta / step_mwh + 1e-9))

    negative_infinity = float('-inf')
    values = [negative_infinity] * (SOC_STEPS + 1)
    values[start_level] = 0.0
    parents = []
    actions = []

    for price in prices:
        next_values = [negative_infinity] * (SOC_STEPS + 1)
        next_parent = [-1] * (SOC_STEPS + 1)
        next_action = [0.0] * (SOC_STEPS + 1)
        for level, value in enumerate(values):
            if value == negative_infinity:
                continue
            low = max(0, level - max_discharge_levels)
            high = min(SOC_STEPS, level + max_charge_levels)
            for next_level in range(low, high + 1):
                delta_storage = (next_level - level) * step_mwh
                if delta_storage > 0:
                    grid_mwh = delta_storage / eta
                    dispatch_mw = -grid_mwh / INTERVAL_HOURS
                    reward = -grid_mwh * price
                elif delta_storage < 0:
                    grid_mwh = -delta_storage * eta
                    dispatch_mw = grid_mwh / INTERVAL_HOURS
                    reward = grid_mwh * price
                else:
                    dispatch_mw = 0.0
                    reward = 0.0
                candidate = value + reward
                if candidate > next_values[next_level]:
                    next_values[next_level] = candidate
                    next_parent[next_level] = level
                    next_action[next_level] = dispatch_mw
        values = next_values
        parents.append(next_parent)
        actions.append(next_action)

    terminal_level = end_level
    if values[terminal_level] == negative_infinity:
        reachable = [level for level, value in enumerate(values) if value != negative_infinity]
        terminal_level = min(reachable, key=lambda level: abs(level - end_level))

    schedule = [0.0] * len(intervals)
    level = terminal_level
    for index in range(len(intervals) - 1, -1, -1):
        schedule[index] = actions[index][level]
        level = parents[index][level]

    low_price = _percentile(prices, 0.15)
    high_price = _percentile(prices, 0.85)
    rows = []
    for row, benchmark_mw, price in zip(intervals, schedule, prices):
        if low_price is not None and price <= low_price:
            window = 'charge'
        elif high_price is not None and price >= high_price:
            window = 'discharge'
        else:
            window = 'hold'
        rows.append({
            'time': row.get('time'),
            'actual_mw': row.get('scada_mw'),
            'benchmark_mw': benchmark_mw,
            'rrp': price,
            'window': window,
        })

    actual_value = sum(float(row.get('energy_value') or 0.0) for row in intervals)
    benchmark_value = values[terminal_level]
    capture_ratio = actual_value / benchmark_value if benchmark_value > 0 else None
    return {
        'rows': rows,
        'actual_value': actual_value,
        'benchmark_value': benchmark_value,
        'capture_ratio': capture_ratio,
        'capture_pct': capture_ratio * 100 if capture_ratio is not None else None,
        'start_storage_mwh': start_mwh,
        'end_storage_mwh': end_mwh,
        'low_price': low_price,
        'high_price': high_price,
        'round_trip_efficiency': ROUND_TRIP_EFFICIENCY,
        'benchmark_version': BENCHMARK_VERSION,
    }
