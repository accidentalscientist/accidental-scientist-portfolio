import json
from pathlib import Path

from django.http import Http404
from django.shortcuts import render


DATA_PATH = Path(__file__).resolve().parent / 'data' / 'world_lens.json'


def dashboard(request):
    if not DATA_PATH.is_file():
        raise Http404('World Ledger data has not been prepared.')

    payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    return render(
        request,
        'world_lens/dashboard.html',
        {
            'dashboard_data': payload,
            'cohort_count': payload['meta']['cohort_count'],
            'dataset_version': payload['meta']['dataset'],
            'data_updated': payload['meta']['data_updated'],
            'score_start': payload['meta']['score_start'],
            'score_end': payload['meta']['score_end'],
        },
    )
