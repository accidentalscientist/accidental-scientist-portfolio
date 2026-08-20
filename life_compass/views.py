import json
import re
from datetime import date as date_cls

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import (
    CalendarMark,
    DailyTask,
    DoneLedgerEntry,
    KanbanCard,
    LifeCompassMeta,
    Strategy,
    WeeklyFocus,
)

# Generous but bounded: a real strategy+execution export is a few KB; this
# just stops an abusive or corrupt payload from growing storage unbounded.
MAX_PAYLOAD_BYTES = 512_000

DAILY_TASK_KEY_RE = re.compile(r'^lifeCompass\.dailyTasks\.(\d{4}-\d{2}-\d{2})$')
WEEKLY_FOCUS_KEY_RE = re.compile(r'^lifeCompass\.weeklyFocus\.([0-9]{4}-[0-9]{2})$')

KANBAN_COLUMNS = ['Ideas', 'This Week', 'Complete', 'Parking Lot']


def home(request):
    return render(request, "life_compass/index.html")


def strategy(request):
    return render(request, "life_compass/strategy.html")


def execution(request):
    return render(request, "life_compass/execution.html")


def _as_str(value):
    return value if isinstance(value, str) else ('' if value is None else str(value))


# ── POST: decompose the frontend's flat namespaced dict into rows ──

def _save_strategy(user, payload):
    if not isinstance(payload, dict):
        return
    Strategy.objects.update_or_create(
        user=user,
        defaults={
            'title': _as_str(payload.get('title')),
            'principle': _as_str(payload.get('principle')),
            'north_star': _as_str(payload.get('northStar')),
            'current_season': _as_str(payload.get('currentSeason')),
            'career_compass': payload.get('careerCompass') or {},
            'season': payload.get('season') or {},
            'rules': payload.get('rules') or [],
            'career_story': payload.get('careerStory') or {},
            'long_term_direction': payload.get('longTermDirection') or [],
        },
    )


def _save_kanban_and_archive(user, kanban_payload, archive_payload):
    seen_client_ids = set()

    if isinstance(kanban_payload, dict):
        for column in KANBAN_COLUMNS:
            for item in kanban_payload.get(column) or []:
                client_id = item.get('id')
                if not client_id:
                    continue
                seen_client_ids.add(client_id)
                KanbanCard.objects.update_or_create(
                    user=user,
                    client_id=client_id,
                    defaults={
                        'title': _as_str(item.get('title')),
                        'date': _as_str(item.get('date')),
                        'description': _as_str(item.get('description')),
                        'priority': _as_str(item.get('priority')),
                        'subtasks': item.get('subtasks') or [],
                        'column': column,
                        'created_at': parse_datetime(item.get('createdAt')) if item.get('createdAt') else None,
                        'updated_at': parse_datetime(item.get('updatedAt')) if item.get('updatedAt') else None,
                        'entered_this_week_at': parse_datetime(item['enteredThisWeekAt']) if item.get('enteredThisWeekAt') else None,
                        'archived_at': None,
                        'archived_from_column': '',
                    },
                )

    if isinstance(archive_payload, list):
        for item in archive_payload:
            client_id = item.get('id')
            if not client_id:
                continue
            seen_client_ids.add(client_id)
            archived_from = _as_str(item.get('archivedFromColumn'))
            KanbanCard.objects.update_or_create(
                user=user,
                client_id=client_id,
                defaults={
                    'title': _as_str(item.get('title')),
                    'date': _as_str(item.get('date')),
                    'description': _as_str(item.get('description')),
                    'priority': _as_str(item.get('priority')),
                    'subtasks': item.get('subtasks') or [],
                    'column': archived_from or 'Parking Lot',
                    'created_at': parse_datetime(item.get('createdAt')) if item.get('createdAt') else None,
                    'updated_at': parse_datetime(item.get('updatedAt')) if item.get('updatedAt') else None,
                    'entered_this_week_at': parse_datetime(item['enteredThisWeekAt']) if item.get('enteredThisWeekAt') else None,
                    'archived_at': parse_datetime(item.get('archivedAt')) if item.get('archivedAt') else None,
                    'archived_from_column': archived_from,
                },
            )

    if isinstance(kanban_payload, dict) or isinstance(archive_payload, list):
        KanbanCard.objects.filter(user=user).exclude(client_id__in=seen_client_ids).delete()


def _save_calendar(user, payload):
    if not isinstance(payload, dict):
        return
    true_dates = set()
    for key, value in payload.items():
        if not value:
            continue
        try:
            true_dates.add(date_cls.fromisoformat(key))
        except ValueError:
            continue

    CalendarMark.objects.filter(user=user).exclude(date__in=true_dates).delete()
    existing = set(CalendarMark.objects.filter(user=user).values_list('date', flat=True))
    CalendarMark.objects.bulk_create(
        [CalendarMark(user=user, date=d) for d in true_dates - existing]
    )


def _kanban_lookup(user):
    return {card.client_id: card for card in KanbanCard.objects.filter(user=user)}


def _save_daily_tasks(user, iso_date, items, cards_by_client_id):
    try:
        parsed_date = date_cls.fromisoformat(iso_date)
    except ValueError:
        return
    DailyTask.objects.filter(user=user, date=parsed_date).delete()
    if not isinstance(items, list):
        return
    DailyTask.objects.bulk_create([
        DailyTask(
            user=user,
            date=parsed_date,
            text=_as_str(item.get('text')),
            done=bool(item.get('done')),
            project=cards_by_client_id.get(item.get('projectId')),
            subtask_client_id=_as_str(item.get('subtaskId')),
        )
        for item in items if isinstance(item, dict)
    ])


def _save_weekly_focus(user, week_key, payload):
    if not isinstance(payload, dict):
        return
    WeeklyFocus.objects.update_or_create(
        user=user,
        week_key=week_key,
        defaults={
            'main': _as_str(payload.get('main')),
            'secondary': _as_str(payload.get('secondary')),
            'health': _as_str(payload.get('health')),
        },
    )


def _save_done_ledger(user, payload, cards_by_client_id):
    if not isinstance(payload, list):
        return
    for item in payload:
        if not isinstance(item, dict):
            continue
        text = _as_str(item.get('text'))
        source = _as_str(item.get('source'))
        parsed_date = parse_datetime(item.get('date')) if item.get('date') else None
        if not parsed_date:
            continue
        exists = DoneLedgerEntry.objects.filter(
            user=user, text=text, source=source, date=parsed_date,
        ).exists()
        if exists:
            continue
        DoneLedgerEntry.objects.create(
            user=user,
            text=text,
            source=source,
            date=parsed_date,
            project=cards_by_client_id.get(item.get('projectId')),
        )


def _save_meta(user, data):
    settings_payload = data.get('lifeCompass.settings')
    stats_payload = data.get('lifeCompass.stats')
    if settings_payload is None and stats_payload is None:
        return
    defaults = {}
    if isinstance(settings_payload, dict):
        defaults['settings_data'] = settings_payload
    if isinstance(stats_payload, dict):
        defaults['stats'] = stats_payload
    obj, created = LifeCompassMeta.objects.get_or_create(user=user, defaults=defaults)
    if not created and defaults:
        LifeCompassMeta.objects.filter(pk=obj.pk).update(**defaults)


@transaction.atomic
def _decompose_and_save(user, data):
    _save_strategy(user, data.get('lifeCompass.strategy'))
    _save_kanban_and_archive(user, data.get('lifeCompass.kanban'), data.get('lifeCompass.archive'))
    _save_calendar(user, data.get('lifeCompass.calendar'))

    cards_by_client_id = _kanban_lookup(user)
    for key, value in data.items():
        daily_match = DAILY_TASK_KEY_RE.match(key)
        if daily_match:
            _save_daily_tasks(user, daily_match.group(1), value, cards_by_client_id)
            continue
        weekly_match = WEEKLY_FOCUS_KEY_RE.match(key)
        if weekly_match:
            _save_weekly_focus(user, weekly_match.group(1), value)

    _save_done_ledger(user, data.get('lifeCompass.doneLedger'), cards_by_client_id)
    _save_meta(user, data)


# ── GET: reassemble the same flat namespaced dict from the tables ──

def _reconstruct(user):
    has_any = (
        Strategy.objects.filter(user=user).exists()
        or KanbanCard.objects.filter(user=user).exists()
        or WeeklyFocus.objects.filter(user=user).exists()
        or CalendarMark.objects.filter(user=user).exists()
        or DailyTask.objects.filter(user=user).exists()
        or DoneLedgerEntry.objects.filter(user=user).exists()
        or LifeCompassMeta.objects.filter(user=user).exists()
    )
    if not has_any:
        return {}

    data = {}

    strat = Strategy.objects.filter(user=user).first()
    if strat:
        data['lifeCompass.strategy'] = {
            'title': strat.title,
            'principle': strat.principle,
            'northStar': strat.north_star,
            'currentSeason': strat.current_season,
            'careerCompass': strat.career_compass,
            'season': strat.season,
            'rules': strat.rules,
            'careerStory': strat.career_story,
            'longTermDirection': strat.long_term_direction,
        }

    def card_to_item(card):
        return {
            'id': card.client_id,
            'title': card.title,
            'date': card.date,
            'description': card.description,
            'priority': card.priority,
            'subtasks': card.subtasks,
            'createdAt': card.created_at.isoformat() if card.created_at else None,
            'updatedAt': card.updated_at.isoformat() if card.updated_at else None,
            'enteredThisWeekAt': card.entered_this_week_at.isoformat() if card.entered_this_week_at else None,
        }

    active_cards = list(KanbanCard.objects.filter(user=user, archived_at__isnull=True))
    kanban = {column: [] for column in KANBAN_COLUMNS}
    for card in active_cards:
        kanban.setdefault(card.column, []).append(card_to_item(card))
    data['lifeCompass.kanban'] = kanban
    data['lifeCompass.parkingLot'] = kanban.get('Parking Lot', [])

    archived_cards = KanbanCard.objects.filter(user=user, archived_at__isnull=False)
    data['lifeCompass.archive'] = [
        {
            **card_to_item(card),
            'archivedAt': card.archived_at.isoformat() if card.archived_at else None,
            'archivedFromColumn': card.archived_from_column,
        }
        for card in archived_cards
    ]

    calendar = {}
    for mark in CalendarMark.objects.filter(user=user):
        calendar[mark.date.isoformat()] = True
    data['lifeCompass.calendar'] = calendar

    for focus in WeeklyFocus.objects.filter(user=user):
        data[f'lifeCompass.weeklyFocus.{focus.week_key}'] = {
            'main': focus.main,
            'secondary': focus.secondary,
            'health': focus.health,
        }

    daily_dates = DailyTask.objects.filter(user=user).values_list('date', flat=True).distinct()
    for daily_date in daily_dates:
        tasks = DailyTask.objects.filter(user=user, date=daily_date)
        data[f'lifeCompass.dailyTasks.{daily_date.isoformat()}'] = [
            {
                'text': task.text,
                'done': task.done,
                'projectId': task.project.client_id if task.project_id else None,
                'subtaskId': task.subtask_client_id or None,
            }
            for task in tasks
        ]

    data['lifeCompass.doneLedger'] = [
        {
            'text': entry.text,
            'source': entry.source,
            'date': entry.date.isoformat(),
            **({'projectId': entry.project.client_id} if entry.project_id else {}),
        }
        for entry in DoneLedgerEntry.objects.filter(user=user).order_by('date')
    ]

    meta = LifeCompassMeta.objects.filter(user=user).first()
    data['lifeCompass.settings'] = meta.settings_data if meta else {}
    data['lifeCompass.stats'] = meta.stats if meta else {}

    return data


@login_required(login_url='life_compass:login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def sync_data(request):
    """The frontend's entire lifeCompass.* localStorage export, as one flat
    namespaced dict, scoped to the logged-in user only. Decomposed into
    normalized tables on save and reassembled into the same flat shape on
    read, so the frontend's contract never changes.
    """
    if request.method == "POST":
        if len(request.body) > MAX_PAYLOAD_BYTES:
            return JsonResponse({"error": "Payload too large."}, status=413)
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON."}, status=400)
        data = payload.get("data")
        if not isinstance(data, dict):
            return JsonResponse({"error": "Expected a 'data' object."}, status=400)
        _decompose_and_save(request.user, data)
        return JsonResponse({"status": "ok"})

    return JsonResponse({"data": _reconstruct(request.user)})
