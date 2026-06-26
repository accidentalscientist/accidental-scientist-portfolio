from django.core.validators import FileExtensionValidator
from django.db import models


class GuidedMeditation(models.Model):
    """An audio-led session used by Stillpoint's 'Guide me' mode.

    Upload MP3 files through the Django admin — they appear automatically
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
