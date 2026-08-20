from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


class GuidedMeditation(models.Model):
    """An audio-led session used by Stillpoint's 'Guide me' mode.

    Upload MP3 files through the Django admin: they appear automatically
    in the guided-session picker on the timer page. MP3 only, for fast
    web delivery (WAV and other heavy formats are rejected).
    """
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    audio = models.FileField(
        upload_to='stillpoint/',
        validators=[FileExtensionValidator(['mp3'])],
        help_text="MP3 only.",
    )
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title


class StillpointSession(models.Model):
    """A completed meditation session, logged server-side for signed-in
    users so it's queryable in Postgres (not just localStorage on one
    device). Anonymous visitors keep the existing localStorage-only demo
    behaviour — see timer.js.
    """
    MODE_CHOICES = [
        ('master', 'Master'),
        ('student', 'Guide me'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stillpoint_sessions')
    completed_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField()
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default='master')
    guided_session = models.ForeignKey(GuidedMeditation, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"{self.user} — {self.completed_at}"
