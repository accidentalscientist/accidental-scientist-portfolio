from django.conf import settings
from django.db import models


class LifeCompassData(models.Model):
    """One row per user — the full lifeCompass.* localStorage export as a
    single JSON blob. Keeping it as one opaque blob (rather than modelling
    strategy/tasks/kanban as separate fields) means the frontend's storage
    format can keep evolving without needing a matching migration here.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='life_compass_data')
    data = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Life Compass data for {self.user}"
