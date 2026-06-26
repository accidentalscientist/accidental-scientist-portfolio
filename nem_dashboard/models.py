from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

MAX_CSV_MB = 10


def validate_csv_size(f):
    if f.size and f.size > MAX_CSV_MB * 1024 * 1024:
        raise ValidationError(f"CSV is too large (max {MAX_CSV_MB} MB).")


class FuelDataUpload(models.Model):
    csv_file = models.FileField(
        upload_to='fuel_data_uploads/',
        validators=[FileExtensionValidator(['csv']), validate_csv_size],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    result = models.TextField(blank=True, default="", help_text="Import summary (filled automatically).")

    def __str__(self):
        return f"Upload on {self.uploaded_at}"


class FuelGenerationData(models.Model):
    timestamp = models.DateTimeField()
    state = models.CharField(max_length=10)
    fuel_type = models.CharField(max_length=50)
    supply_mw = models.FloatField()

    def __str__(self):
        return f"{self.timestamp} | {self.state} | {self.fuel_type} | {self.supply_mw} MW"
