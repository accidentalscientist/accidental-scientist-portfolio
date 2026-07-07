from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

MAX_CSV_MB = 5


def validate_csv_size(f):
    if f.size and f.size > MAX_CSV_MB * 1024 * 1024:
        raise ValidationError(f"CSV is too large (max {MAX_CSV_MB} MB).")


class PortfolioUploadForm(forms.Form):
    snapshot_file = forms.FileField(
        label="Portfolio Snapshot (required)",
        validators=[FileExtensionValidator(['csv']), validate_csv_size],
    )
    timeline_file = forms.FileField(
        label="Revenue Timeline (optional)",
        required=False,
        validators=[FileExtensionValidator(['csv']), validate_csv_size],
    )
