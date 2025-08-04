from django.shortcuts import render
from .models import FuelGenerationData
from django.db.models import Sum
from collections import defaultdict, namedtuple

FUEL_METADATA = [
    {"fuel": "Black coal", "icon": "⬛", "color": "#333333", "order": 1},
    {"fuel": "Brown coal", "icon": "🟤", "color": "#8B5E3C", "order": 2},
    {"fuel": "Wind", "icon": "💨", "color": "#A8E6A3", "order": 3},
    {"fuel": "Solar", "icon": "🔆", "color": "#FFD54F", "order": 4},
    {"fuel": "Hydro", "icon": "💧", "color": "#B3E5FC", "order": 5},
    {"fuel": "Gas", "icon": "🔥", "color": "#4DD0E1", "order": 6},
    {"fuel": "Battery", "icon": "🔋", "color": "#AB47BC", "order": 7},
    {"fuel": "Biomass", "icon": "🧪", "color": "#D32F2F", "order": 8},
    {"fuel": "Liquid Fuel", "icon": "⛽", "color": "#FF7043", "order": 9},
    {"fuel": "Other", "icon": "⚡", "color": "#1565C0", "order": 10},
]



def dashboard(request):
    selected_state = request.GET.get('state', 'NSW')
    data = FuelGenerationData.objects.all()

    if selected_state != 'NEM':
        data = data.filter(state=selected_state)

    # Aggregate by fuel type
    raw_aggregated = (
        data.values('fuel_type')
            .annotate(total_gen=Sum('supply_mw'))
    )
    fuel_lookup = {row['fuel_type']: row['total_gen'] for row in raw_aggregated}

    # Build complete fuel_data with metadata
    fuel_data = []
    for meta in FUEL_METADATA:
        total = fuel_lookup.get(meta['fuel'], 0.0)
        fuel_data.append({
            'fuel': meta['fuel'],
            'icon': meta['icon'],
            'color': meta['color'],
            'order': meta['order'],
            'total_gen': total,
        })

    # Sort by total_gen descending (as in Excel screenshot)
    fuel_data.sort(key=lambda x: x['total_gen'], reverse=True)

    # Normalized width calc
    max_mw = max([row['total_gen'] for row in fuel_data] + [1])
    for row in fuel_data:
        row['normalized_width'] = round((row['total_gen'] / max_mw) * 100, 2)

    # Latest records
    if selected_state != 'NEM':
        latest = data.order_by('-timestamp')[:50]
        latest_timestamp = latest[0].timestamp if latest else None
    else:
        latest_timestamp = data.order_by('-timestamp').first().timestamp if data.exists() else None
        latest = [
            {
                'timestamp': latest_timestamp,
                'state': 'NEM',
                'fuel_type': row['fuel'],
                'supply_mw': row['total_gen']
            }
            for row in fuel_data
        ]

    # States dropdown
    state_order = ["NSW", "QLD", "VIC", "SA", "TAS", "NEM"]
    states = [state for state in state_order if FuelGenerationData.objects.filter(state=state).exists()]
    states.insert(0, 'NEM')

    return render(request, 'nem_dashboard/dashboard.html', {
        'fuel_data': fuel_data,
        'fuel_data_by_type': fuel_data,  # can be used elsewhere
        'latest_data': latest,
        'states': states,
        'selected_state': selected_state,
        'last_updated': latest_timestamp,
    })
