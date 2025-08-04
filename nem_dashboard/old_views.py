from django.shortcuts import render
from .models import FuelGenerationData, FuelGenerationData
from django.db.models import Sum
from collections import defaultdict, namedtuple




# Define the list of all fuel types
ALL_FUEL_TYPES = [
    'Battery',
    'Biomass',
    'Black coal',
    'Brown coal',
    'Gas',
    'Hydro',
    'Liquid Fuel',
    'Other',
    'Solar',
    'Wind',
]



def dashboard(request):
    selected_state = request.GET.get('state', 'NSW')
    data = FuelGenerationData.objects.all()

    if selected_state != 'NEM':
        data = data.filter(state=selected_state)

    raw_aggregated = (
        data.values('fuel_type')
            .annotate(total_gen=Sum('supply_mw'))
    )

    fuel_lookup = {entry['fuel_type']: entry['total_gen'] for entry in raw_aggregated}

    # For consistent fuel display order
    aggregated = [
        {'fuel': fuel, 'total_gen': fuel_lookup.get(fuel, 0.0)}
        for fuel in ALL_FUEL_TYPES
    ]

    # Calculate max for normalized width
    max_mw = max((row['total_gen'] for row in aggregated), default=1)

    fuel_icons = {
        'Battery': '🔋', 'Biomass': '♻️', 'Black coal': '🪨',
        'Brown coal': '🥔', 'Gas': '🔥', 'Hydro': '💧',
        'Liquid Fuel': '⛽', 'Other': '❓', 'Solar': '☀️', 'Wind': '🌬️',
    }

    for row in aggregated:
        row['normalized_width'] = round((row['total_gen'] / max_mw) * 100, 2)
        max_mw = max((row['total_gen'] for row in aggregated if row['total_gen'] > 0), default=1)
        row['icon'] = fuel_icons.get(row['fuel'], '❓')

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
            for row in aggregated
        ]

    states = list(FuelGenerationData.objects.values_list('state', flat=True).distinct())
    states.insert(0, 'NEM')

    return render(request, 'nem_dashboard/dashboard.html', {
        'fuel_data': aggregated,
        'fuel_data_by_type': aggregated,
        'latest_data': latest,
        'states': states,
        'selected_state': selected_state,
        'last_updated': latest_timestamp,
    })
    