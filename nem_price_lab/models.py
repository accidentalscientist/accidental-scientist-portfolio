from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from .constants import DISPLAY_REGIONS

MAX_CSV_MB = 25

# Includes the derived NEM-wide series alongside the five settled regions.
REGION_CHOICES = [(r, r) for r in DISPLAY_REGIONS]


def validate_csv_size(f):
    if f.size and f.size > MAX_CSV_MB * 1024 * 1024:
        raise ValidationError(f"CSV is too large (max {MAX_CSV_MB} MB).")


class PriceDataUpload(models.Model):
    """Admin-side weekly upload of an AEMO aggregated price and demand CSV.

    The monthly file at
    aemo.com.au/aemo/data/nem/priceanddemand/PRICE_AND_DEMAND_YYYYMM_REGION.csv
    is cumulative within the month, so re-uploading the same month simply
    refreshes and extends it. The region is read from the file itself.
    """

    csv_file = models.FileField(
        upload_to='nem_price_uploads/',
        validators=[FileExtensionValidator(['csv']), validate_csv_size],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    result = models.TextField(blank=True, default='', help_text='Import summary (filled automatically).')

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Price data upload'

    def __str__(self):
        return f'Price upload on {self.uploaded_at:%Y-%m-%d %H:%M}'


class RegionPrice(models.Model):
    """One 30-minute settled interval for one region.

    `interval_end` follows AEMO's own convention: SETTLEMENTDATE marks the
    END of the interval, so the half hour labelled 00:30 covers 00:05-00:30.
    Naming it `interval_end` keeps that explicit rather than leaving a
    silent off-by-one for a later reader to trip over.
    """

    region = models.CharField(max_length=8, choices=REGION_CHOICES)
    interval_end = models.DateTimeField(help_text='End of the 30-minute interval, NEM time (UTC+10).')
    rrp = models.FloatField(help_text='Regional reference price, $/MWh, mean of the 5-minute prices.')
    total_demand = models.FloatField(help_text='Total demand, MW, mean across the interval.')

    class Meta:
        ordering = ['region', 'interval_end']
        constraints = [
            models.UniqueConstraint(fields=['region', 'interval_end'], name='uniq_region_interval'),
        ]
        indexes = [models.Index(fields=['region', 'interval_end'])]

    def __str__(self):
        return f'{self.region} | {self.interval_end:%Y-%m-%d %H:%M} | ${self.rrp:.2f}/MWh'


class RegionWeather(models.Model):
    """Temperature for a region's representative point, at 30-minute resolution.

    `kind` is the single most important field in this table. `observed` is
    what actually happened; `forecast` is what was predicted ahead of time.
    Training or evaluating a forward model on `observed` future temperature
    is leakage, because on the day you make the call you only ever have a
    forecast. Keeping them in separate rows makes that mistake visible
    rather than silent.
    """

    OBSERVED = 'observed'
    FORECAST = 'forecast'
    KIND_CHOICES = [
        (OBSERVED, 'Observed (reanalysis)'),
        (FORECAST, 'Forecast (as issued ahead of time)'),
    ]

    region = models.CharField(max_length=8, choices=REGION_CHOICES)
    interval_end = models.DateTimeField(help_text='End of the 30-minute interval, NEM time (UTC+10).')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    temperature_c = models.FloatField()

    class Meta:
        ordering = ['region', 'interval_end']
        constraints = [
            models.UniqueConstraint(fields=['region', 'interval_end', 'kind'], name='uniq_region_interval_kind'),
        ]
        indexes = [models.Index(fields=['region', 'kind', 'interval_end'])]

    def __str__(self):
        return f'{self.region} | {self.interval_end:%Y-%m-%d %H:%M} | {self.kind} | {self.temperature_c:.1f}C'


class ForecastRun(models.Model):
    """One published forecast: a model, a region, an origin, a horizon.

    Runs are never overwritten. Each Sunday adds a new row, so the archive of
    what was predicted (and when) accumulates on its own. That archive is
    what makes the weekly "here is how last week's call actually performed"
    review possible without any extra bookkeeping.
    """

    SOURCE_FORECAST = 'forecast'
    SOURCE_OBSERVED_FALLBACK = 'observed-fallback'
    SOURCE_NONE = 'none'
    TEMP_SOURCE_CHOICES = [
        (SOURCE_FORECAST, 'Forecast temperature (leakage-safe)'),
        (SOURCE_OBSERVED_FALLBACK, 'Observed temperature (backfilled: optimistic)'),
        (SOURCE_NONE, 'No temperature used'),
    ]

    region = models.CharField(max_length=8, choices=REGION_CHOICES)
    model_key = models.CharField(max_length=40)
    issued_at = models.DateTimeField(help_text='Forecast origin. Nothing after this instant may inform the run.')
    horizon_days = models.PositiveSmallIntegerField(default=7)
    temperature_source = models.CharField(max_length=20, choices=TEMP_SOURCE_CHOICES, default=SOURCE_NONE)
    parameters = models.JSONField(default=dict, blank=True, help_text='Fitted coefficients, for display and audit.')
    notes = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issued_at', 'region', 'model_key']
        constraints = [
            models.UniqueConstraint(
                fields=['region', 'model_key', 'issued_at'], name='uniq_region_model_issued'
            ),
        ]
        indexes = [models.Index(fields=['region', 'issued_at'])]

    def __str__(self):
        return f'{self.region} | {self.model_key} | issued {self.issued_at:%Y-%m-%d}'

    @property
    def is_leakage_safe(self):
        """False when the run leaned on temperature it could not have known."""
        return self.temperature_source != self.SOURCE_OBSERVED_FALLBACK


class ForecastPoint(models.Model):
    """A single predicted interval belonging to a run."""

    run = models.ForeignKey(ForecastRun, on_delete=models.CASCADE, related_name='points')
    interval_end = models.DateTimeField()
    predicted_rrp = models.FloatField()

    class Meta:
        ordering = ['interval_end']
        constraints = [
            models.UniqueConstraint(fields=['run', 'interval_end'], name='uniq_run_interval'),
        ]
        indexes = [models.Index(fields=['run', 'interval_end'])]

    def __str__(self):
        return f'{self.run_id} | {self.interval_end:%Y-%m-%d %H:%M} | ${self.predicted_rrp:.2f}'
