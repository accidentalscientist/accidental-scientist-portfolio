import re
from datetime import date as date_cls

from django.db import migrations
from django.utils.dateparse import parse_datetime

DAILY_TASK_KEY_RE = re.compile(r'^lifeCompass\.dailyTasks\.(\d{4}-\d{2}-\d{2})$')
WEEKLY_FOCUS_KEY_RE = re.compile(r'^lifeCompass\.weeklyFocus\.([0-9]{4}-[0-9]{2})$')
KANBAN_COLUMNS = ['Ideas', 'This Week', 'Complete', 'Parking Lot']


def _as_str(value):
    return value if isinstance(value, str) else ('' if value is None else str(value))


def migrate_blob_data(apps, schema_editor):
    """One-off: parse each user's existing LifeCompassData JSON blob into
    the new normalized tables. Current state only — this becomes the first
    row in each table's history from here on, no attempt to reconstruct
    history the blob never had.
    """
    LifeCompassData = apps.get_model('life_compass', 'LifeCompassData')
    Strategy = apps.get_model('life_compass', 'Strategy')
    KanbanCard = apps.get_model('life_compass', 'KanbanCard')
    WeeklyFocus = apps.get_model('life_compass', 'WeeklyFocus')
    CalendarMark = apps.get_model('life_compass', 'CalendarMark')
    DailyTask = apps.get_model('life_compass', 'DailyTask')
    DoneLedgerEntry = apps.get_model('life_compass', 'DoneLedgerEntry')
    LifeCompassMeta = apps.get_model('life_compass', 'LifeCompassMeta')

    for blob in LifeCompassData.objects.all():
        user = blob.user
        data = blob.data or {}

        strategy_payload = data.get('lifeCompass.strategy')
        if isinstance(strategy_payload, dict):
            Strategy.objects.update_or_create(
                user=user,
                defaults={
                    'title': _as_str(strategy_payload.get('title')),
                    'principle': _as_str(strategy_payload.get('principle')),
                    'north_star': _as_str(strategy_payload.get('northStar')),
                    'current_season': _as_str(strategy_payload.get('currentSeason')),
                    'career_compass': strategy_payload.get('careerCompass') or {},
                    'season': strategy_payload.get('season') or {},
                    'rules': strategy_payload.get('rules') or [],
                    'career_story': strategy_payload.get('careerStory') or {},
                    'long_term_direction': strategy_payload.get('longTermDirection') or [],
                },
            )

        cards_by_client_id = {}

        def upsert_card(item, column, archived_at=None, archived_from_column=''):
            client_id = item.get('id')
            if not client_id:
                return
            card, _ = KanbanCard.objects.update_or_create(
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
                    'archived_at': archived_at,
                    'archived_from_column': archived_from_column,
                },
            )
            cards_by_client_id[client_id] = card

        kanban_payload = data.get('lifeCompass.kanban')
        if isinstance(kanban_payload, dict):
            for column in KANBAN_COLUMNS:
                for item in kanban_payload.get(column) or []:
                    upsert_card(item, column)

        archive_payload = data.get('lifeCompass.archive')
        if isinstance(archive_payload, list):
            for item in archive_payload:
                archived_from = _as_str(item.get('archivedFromColumn'))
                upsert_card(
                    item,
                    archived_from or 'Parking Lot',
                    archived_at=parse_datetime(item.get('archivedAt')) if item.get('archivedAt') else None,
                    archived_from_column=archived_from,
                )

        calendar_payload = data.get('lifeCompass.calendar')
        if isinstance(calendar_payload, dict):
            for key, value in calendar_payload.items():
                if not value:
                    continue
                try:
                    CalendarMark.objects.get_or_create(user=user, date=date_cls.fromisoformat(key))
                except ValueError:
                    continue

        for key, value in data.items():
            daily_match = DAILY_TASK_KEY_RE.match(key)
            if daily_match and isinstance(value, list):
                try:
                    parsed_date = date_cls.fromisoformat(daily_match.group(1))
                except ValueError:
                    continue
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    DailyTask.objects.create(
                        user=user,
                        date=parsed_date,
                        text=_as_str(item.get('text')),
                        done=bool(item.get('done')),
                        project=cards_by_client_id.get(item.get('projectId')),
                        subtask_client_id=_as_str(item.get('subtaskId')),
                    )
                continue

            weekly_match = WEEKLY_FOCUS_KEY_RE.match(key)
            if weekly_match and isinstance(value, dict):
                WeeklyFocus.objects.update_or_create(
                    user=user,
                    week_key=weekly_match.group(1),
                    defaults={
                        'main': _as_str(value.get('main')),
                        'secondary': _as_str(value.get('secondary')),
                        'health': _as_str(value.get('health')),
                    },
                )

        ledger_payload = data.get('lifeCompass.doneLedger')
        if isinstance(ledger_payload, list):
            for item in ledger_payload:
                if not isinstance(item, dict):
                    continue
                parsed_date = parse_datetime(item.get('date')) if item.get('date') else None
                if not parsed_date:
                    continue
                DoneLedgerEntry.objects.create(
                    user=user,
                    text=_as_str(item.get('text')),
                    source=_as_str(item.get('source')),
                    date=parsed_date,
                    project=cards_by_client_id.get(item.get('projectId')),
                )

        settings_payload = data.get('lifeCompass.settings')
        stats_payload = data.get('lifeCompass.stats')
        if isinstance(settings_payload, dict) or isinstance(stats_payload, dict):
            LifeCompassMeta.objects.update_or_create(
                user=user,
                defaults={
                    'settings_data': settings_payload if isinstance(settings_payload, dict) else {},
                    'stats': stats_payload if isinstance(stats_payload, dict) else {},
                },
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('life_compass', '0002_calendarmark_historicalcalendarmark_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_blob_data, noop_reverse),
    ]
