from django.shortcuts import render
from django.utils import timezone

from . import services
from .constants import FACILITY_TYPES, MAJOR_HUBS
from .models import Facility, Location

# Above this share of the rating in force, a pipeline is described as
# tight. Not an AEMO threshold: AEMO's own view is the linepack adequacy
# flag, which is shown separately and carries more authority than this.
TIGHT_PCT = 90

# Fixed per chart rather than a single page-wide range control. A page
# selector forced every chart to the same window regardless of what each
# one is actually for: the constraint strip and the demand mix both read
# best over a season (90 days), storage needs several YEARS before its
# seasonal median means anything, and the forward outlook is inherently
# short because that is genuinely all AEMO assesses system-wide (see
# `services.constraint_outlook`).
BALANCE_DAYS = 90
CONSTRAINT_DAYS = 90
DEMAND_DAYS = 90
STORAGE_DAYS = 1825
OUTLOOK_TRAILING_DAYS = 4


def monitor(request):
    """The system model, plus what it did on the most recent gas day.

    Flows, storage, constraint outlook and coverage are live. Prices and
    the stress components are specified but not built, and the page says
    so rather than implying otherwise.
    """
    summary = services.system_model_summary()
    headline = services.system_headline()
    balance = services.state_balance()
    network = services.flow_network()
    regions = services.location_state_regions(network['nodes']) if network else []
    picture = services.gas_day_picture()
    outlook = services.constraint_outlook(trailing_days=OUTLOOK_TRAILING_DAYS)
    coverage = services.coverage_report()
    gaps = services.gas_day_gaps()
    utilisation = services.pipeline_utilisation()

    demand = services.demand_composition(days=DEMAND_DAYS)
    system = services.system_balance_series(days=BALANCE_DAYS)
    constraints = services.constraint_history(days=CONSTRAINT_DAYS)
    storage = services.storage_history(days=STORAGE_DAYS)

    pipelines = []
    hubs = []
    storage_facilities = []

    if summary:
        pipes = list(Facility.objects.filter(facility_type='PIPE').order_by('name'))
        as_at = services.latest_gas_day() or timezone.localdate()
        # Legs IN FORCE on the latest gas day, never the count of stored
        # ratings: Amadeus holds 2,709 archived rows and exactly one live
        # leg. More than one leg in force is the reverse-haul signal.
        in_force = services.legs_in_force([p.facility_id for p in pipes], as_at)

        pipelines = []
        for pipe in pipes:
            legs = in_force.get(pipe.facility_id, [])
            pipelines.append({
                'name': pipe.name,
                'operator': pipe.operator_name,
                'legs': len(legs),
                'max_capacity': max((leg.capacity_tj for leg in legs), default=None),
                'effective': legs[0].effective_date if legs else None,
                'active': pipe.is_active,
                'connection_points': pipe.connection_points.count(),
            })

        hubs = list(Location.objects.filter(location_type='HUB').order_by('state', 'name'))
        storage_facilities = list(Facility.objects.filter(facility_type='STOR').order_by('name'))
        reverse_haul = sum(1 for p in pipelines if p['legs'] > 1)
        summary['ratings_in_force'] = sum(len(v) for v in in_force.values())
        summary['reverse_haul'] = reverse_haul
        summary['ratings_as_at'] = as_at

    if picture:
        for entry in picture['end_use']:
            entry['label'] = FACILITY_TYPES.get(entry['code'], entry['code'])

    # Sort the utilisation table so meaningful rows lead. Suspect
    # denominators used to sort to the top on their inflated percentage,
    # so the first two rows a reader met were the two we know are wrong.
    if utilisation:
        utilisation['meaningful'] = [r for r in utilisation['rated']
                                     if not r['denominator_suspect']][:10]

    if network:
        # Resolve endpoint labels here rather than in the template, which
        # cannot index a dict by a variable key.
        labels = {node['id']: node['label'] for node in network['nodes']}
        for edge in network['edges']:
            edge['source_label'] = labels.get(edge['source'], edge['source'])
            edge['target_label'] = labels.get(edge['target'], edge['target'])
        for node in network['nodes']:
            node['major'] = node['id'] in MAJOR_HUBS

    return render(request, 'gas_monitor/monitor.html', {
        'summary': summary,
        'headline': headline,
        'balance': balance,
        'network': network,
        'picture': picture,
        'outlook': outlook,
        'coverage': coverage,
        'gaps': gaps,
        'pipelines': pipelines,
        'hubs': hubs,
        # Named apart from `storage` (the history series) so the registry
        # list and the chart cannot collide again.
        'storage_facilities': storage_facilities,
        'demand': demand,
        'system': system,
        'constraints': constraints,
        'utilisation': utilisation,
        'storage': storage,
        'tight_pct': TIGHT_PCT,
        'network_json': {
            'gas_date': network['gas_date'].isoformat(),
            'nodes': network['nodes'],
            'edges': network['edges'],
            'domestic_peak_tj': network['domestic_peak_tj'],
            'export_peak_tj': network['export_peak_tj'],
            'legend_flows': network['legend_flows'],
            'legend_nodes': network['legend_nodes'],
            'regions': regions,
        } if network else None,
        'system_json': {
            'dates': system['dates'], 'supply': system['supply'],
            'demand': system['demand'], 'export': system['export'],
            'domestic': system['domestic'], 'export_share': system['export_share'],
        } if system else None,
        'utilisation_json': {
            'gas_date': utilisation['gas_date'].isoformat(),
            'rows': [
                {'name': row['name'], 'pct': row['utilisation_pct'],
                 'received': row['received_tj'], 'capacity': row['capacity_tj'],
                 'suspect': row['denominator_suspect']}
                for row in utilisation['rated'][:12]
            ],
        } if utilisation and utilisation['rated'] else None,
        'storage_json': {
            'dates': storage['dates'],
            'totals': storage['totals'],
            'reference': storage['reference'],
            'reporting': storage['reporting'],
            'latest_total': storage['latest_total'],
            'has_reference': storage['has_reference'],
        } if storage else None,
        # Only the drawing payloads cross into JavaScript. Everything a
        # reader needs is already rendered server-side, so the charts stay
        # an enhancement rather than the only way to get the numbers.
        'demand_json': {'dates': demand['dates'], 'series': demand['series']} if demand else None,
        'constraint_json': {
            'dates': constraints['dates'],
            'rows': constraints['rows'],
            'totals': constraints['totals'],
            'pipelines_assessed': constraints['pipelines_assessed'],
            'pipelines_flagged': constraints['pipelines_flagged'],
            'requested_days': constraints['requested_days'],
            'available_days': constraints['available_days'],
            'history_complete': constraints['history_complete'],
        } if constraints else None,
    })
