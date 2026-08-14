import json
from pathlib import Path

from django.http import Http404
from django.shortcuts import render


DATA_DIR = Path(__file__).resolve().parent / 'data'
DATA_PATH = DATA_DIR / 'world_lens.json'
DATA_PATH_V2 = DATA_DIR / 'world_lens_v2.json'


def dashboard(request):
    if not DATA_PATH.is_file():
        raise Http404('World Ledger data has not been prepared.')

    payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))
    payload_v2 = json.loads(DATA_PATH_V2.read_text(encoding='utf-8')) if DATA_PATH_V2.is_file() else None
    return render(
        request,
        'world_lens/dashboard.html',
        {
            'dashboard_data': payload,
            'dashboard_data_v2': payload_v2,
            'cohort_count': payload['meta']['cohort_count'],
            'dataset_version': payload['meta']['dataset'],
            'data_updated': payload['meta']['data_updated'],
            'score_start': payload['meta']['score_start'],
            'score_end': payload['meta']['score_end'],
        },
    )
