from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from .scoring import DEFAULT_HEALTH_MODEL, HEALTH_MODELS

MAX_CSV_MB = 5


def validate_csv_size(f):
    if f.size and f.size > MAX_CSV_MB * 1024 * 1024:
        raise ValidationError(f"CSV is too large (max {MAX_CSV_MB} MB).")


class PortfolioUploadForm(forms.Form):
    health_model = forms.ChoiceField(
        label="Model Selector",
        choices=[(model_id, model["name"]) for model_id, model in HEALTH_MODELS.items()],
        initial=DEFAULT_HEALTH_MODEL,
        required=False,
    )
    snapshot_file = forms.FileField(
        label="Portfolio Snapshot (required)",
        validators=[FileExtensionValidator(['csv']), validate_csv_size],
    )
    timeline_file = forms.FileField(
        label="ARR Timeline (optional)",
        required=False,
        validators=[FileExtensionValidator(['csv']), validate_csv_size],
    )
