from django.db import models


class GuidedMeditation(models.Model):
    """An audio-led session used by Stillpoint's 'Guide me' mode.

    Upload audio files through the Django admin — they appear automatically
    in the guided-session picker on the timer page.
    """
    title = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    audio = models.FileField(upload_to='stillpoint/')
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first.")

    class Meta:
        ordering = ['order', 'title']

    def __str__(self):
        return self.title
