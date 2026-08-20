from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class Strategy(models.Model):
    """One row per user holding the whole Strategy document. Sub-sections
    stay as JSON columns rather than becoming their own tables since they're
    authored and read together as one document, not queried independently.
    `history` gives a full row-level changelog going forward.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='life_compass_strategy')
    title = models.CharField(max_length=200, blank=True)
    principle = models.CharField(max_length=300, blank=True)
    north_star = models.CharField(max_length=300, blank=True)
    current_season = models.CharField(max_length=300, blank=True)
    career_compass = models.JSONField(default=dict, blank=True)
    season = models.JSONField(default=dict, blank=True)
    rules = models.JSONField(default=list, blank=True)
    career_story = models.JSONField(default=dict, blank=True)
    long_term_direction = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    def __str__(self):
        return f"Strategy for {self.user}"


class KanbanCard(models.Model):
    """A project/task card. Also stands in for the frontend's separate
    'archived' list (`archived_at`/`archived_from_column`) since an archived
    item is structurally the same card, not a different kind of record.
    """
    COLUMN_CHOICES = [
        ('Ideas', 'Ideas'),
        ('This Week', 'This Week'),
        ('Complete', 'Complete'),
        ('Parking Lot', 'Parking Lot'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='kanban_cards')
    client_id = models.CharField(max_length=64)
    title = models.CharField(max_length=300, blank=True)
    date = models.CharField(max_length=32, blank=True)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=16, blank=True)
    subtasks = models.JSONField(default=list, blank=True)
    column = models.CharField(max_length=16, choices=COLUMN_CHOICES, default='Ideas')
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    entered_this_week_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_from_column = models.CharField(max_length=16, blank=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = [('user', 'client_id')]

    def __str__(self):
        return f"{self.title} ({self.column})"


class WeeklyFocus(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='weekly_focuses')
    week_key = models.CharField(max_length=16)
    main = models.CharField(max_length=300, blank=True)
    secondary = models.CharField(max_length=300, blank=True)
    health = models.CharField(max_length=300, blank=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = [('user', 'week_key')]

    def __str__(self):
        return f"{self.user} — {self.week_key}"


class CalendarMark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='calendar_marks')
    date = models.DateField()
    history = HistoricalRecords()

    class Meta:
        unique_together = [('user', 'date')]

    def __str__(self):
        return f"{self.user} — {self.date}"


class DailyTask(models.Model):
    """No stable frontend id for these — the sync view replaces the full
    set for (user, date) on each push rather than diffing, so no history."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_tasks')
    date = models.DateField()
    text = models.CharField(max_length=300, blank=True)
    done = models.BooleanField(default=False)
    project = models.ForeignKey(KanbanCard, on_delete=models.SET_NULL, null=True, blank=True, related_name='daily_task_refs')
    subtask_client_id = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return f"{self.user} — {self.date} — {self.text}"


class DoneLedgerEntry(models.Model):
    """Append-only completion log. The frontend already dedupes before
    pushing, so the sync view inserts anything not already present rather
    than replacing the set — the rows themselves are the history."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='done_ledger_entries')
    text = models.CharField(max_length=300)
    source = models.CharField(max_length=100, blank=True)
    date = models.DateTimeField()
    project = models.ForeignKey(KanbanCard, on_delete=models.SET_NULL, null=True, blank=True, related_name='done_ledger_entries')

    def __str__(self):
        return f"{self.user} — {self.text}"


class LifeCompassMeta(models.Model):
    """Catch-all for the two minor UI/counter keys (editMode, pomodoro
    counts) that aren't worth normalizing into their own tables."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='life_compass_meta')
    settings_data = models.JSONField(default=dict, blank=True)
    stats = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Life Compass meta for {self.user}"
