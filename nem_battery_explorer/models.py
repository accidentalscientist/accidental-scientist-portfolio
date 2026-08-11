from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


REGION_CHOICES = [
    ('NSW1', 'New South Wales'),
    ('QLD1', 'Queensland'),
    ('SA1', 'South Australia'),
    ('TAS1', 'Tasmania'),
    ('VIC1', 'Victoria'),
]


class BatteryAsset(models.Model):
    """A physical battery site, independent of its market registrations.

    A site can have multiple DUIDs and a DUID can replace an older identity.
    Keeping the physical asset separate stops registration changes from
    rewriting the site's history.
    """

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=180)
    region = models.CharField(max_length=4, choices=REGION_CHOICES)
    owner = models.CharField(max_length=240, blank=True)
    custodian = models.CharField(max_length=80, blank=True)
    aemo_survey_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    commitment_status = models.CharField(max_length=40, blank=True)
    is_spike_cohort = models.BooleanField(
        default=False,
        help_text='Included in the initial three-asset, 30-day validation cohort.',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['region', 'name']

    def __str__(self):
        return f'{self.name} ({self.region})'


class BatteryRegistration(models.Model):
    """An effective-dated DUID and capacity record for a battery asset."""

    BIDIRECTIONAL = 'bidirectional'
    GENERATION = 'generation'
    LOAD = 'load'
    DIRECTION_CHOICES = [
        (BIDIRECTIONAL, 'Bidirectional unit'),
        (GENERATION, 'Legacy generation unit'),
        (LOAD, 'Legacy load unit'),
    ]

    asset = models.ForeignKey(
        BatteryAsset,
        on_delete=models.CASCADE,
        related_name='registrations',
    )
    duid = models.CharField(max_length=20)
    direction_model = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        default=BIDIRECTIONAL,
    )
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    power_capacity_mw = models.DecimalField(max_digits=10, decimal_places=3)
    storage_capacity_mwh = models.DecimalField(max_digits=11, decimal_places=3)
    aemo_generation_info_unit_id = models.PositiveBigIntegerField(null=True, blank=True)
    unit_name = models.CharField(max_length=160, blank=True)
    connection_point_id = models.CharField(max_length=40, blank=True)
    source_name = models.CharField(max_length=120)
    source_url = models.URLField(max_length=600)
    source_published_on = models.DateField()
    source_registry_version = models.CharField(max_length=80)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['asset', 'effective_from', 'duid']
        constraints = [
            models.UniqueConstraint(
                fields=['asset', 'duid', 'effective_from'],
                name='uniq_battery_registration_start',
            ),
            models.CheckConstraint(
                condition=Q(power_capacity_mw__gt=Decimal('0')),
                name='battery_power_capacity_positive',
            ),
            models.CheckConstraint(
                condition=Q(storage_capacity_mwh__gt=Decimal('0')),
                name='battery_storage_capacity_positive',
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=models.F('effective_from')),
                name='battery_registration_dates_ordered',
            ),
        ]
        indexes = [
            models.Index(fields=['duid', 'effective_from', 'effective_to']),
            models.Index(fields=['asset', 'effective_from']),
        ]

    def __str__(self):
        end = self.effective_to.isoformat() if self.effective_to else 'present'
        return f'{self.asset.name}: {self.duid} ({self.effective_from} to {end})'

    def clean(self):
        super().clean()
        errors = {}
        if self.effective_to and self.effective_to < self.effective_from:
            errors['effective_to'] = 'Effective end cannot precede effective start.'

        if self.duid and self.effective_from:
            candidate_end = self.effective_to or date.max
            overlaps = type(self).objects.filter(
                duid=self.duid,
                effective_from__lte=candidate_end,
            ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=self.effective_from))
            if self.pk:
                overlaps = overlaps.exclude(pk=self.pk)
            if overlaps.exists():
                errors['duid'] = 'This DUID already has an overlapping effective-dated registration.'

        if errors:
            raise ValidationError(errors)

    def is_effective_on(self, operating_date):
        return self.effective_from <= operating_date and (
            self.effective_to is None or operating_date <= self.effective_to
        )


class BatteryDataRefresh(models.Model):
    """Audit record for one manual or scheduled AEMO refresh."""

    RUNNING = 'running'
    COMPLETE = 'complete'
    PARTIAL = 'partial'
    FAILED = 'failed'
    STATUS_CHOICES = [
        (RUNNING, 'Running'),
        (COMPLETE, 'Complete'),
        (PARTIAL, 'Partial'),
        (FAILED, 'Failed'),
    ]

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    requested_start = models.DateField()
    requested_end = models.DateField()
    completed_through = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=RUNNING)
    calculation_version = models.CharField(max_length=30, default='mvp-v1')
    source_receipts = models.JSONField(default=list, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.requested_start} to {self.requested_end}: {self.status}'


class RegionPriceInterval(models.Model):
    """One public five-minute regional price interval in fixed NEM time."""

    operating_date = models.DateField()
    region = models.CharField(max_length=4, choices=REGION_CHOICES)
    interval_end = models.DateTimeField(help_text='Interval end stored as fixed NEM time (UTC+10).')
    rrp = models.FloatField(help_text='Regional reference price in $/MWh.')
    fcas_prices = models.JSONField(default=dict)
    source_file = models.CharField(max_length=180)

    class Meta:
        ordering = ['region', 'interval_end']
        constraints = [
            models.UniqueConstraint(
                fields=['region', 'interval_end'],
                name='uniq_battery_region_price_interval',
            ),
        ]
        indexes = [
            models.Index(fields=['operating_date', 'region']),
        ]

    def __str__(self):
        return f'{self.region} {self.interval_end}: ${self.rrp:.2f}/MWh'


class BatteryDispatchInterval(models.Model):
    """Observed and dispatched battery state for one five-minute interval."""

    registration = models.ForeignKey(
        BatteryRegistration,
        on_delete=models.PROTECT,
        related_name='intervals',
    )
    regional_price = models.ForeignKey(
        RegionPriceInterval,
        on_delete=models.PROTECT,
        related_name='battery_intervals',
    )
    operating_date = models.DateField()
    interval_end = models.DateTimeField(help_text='Interval end stored as fixed NEM time (UTC+10).')
    initial_mw = models.FloatField(null=True, blank=True)
    dispatch_target_mw = models.FloatField(null=True, blank=True)
    scada_mw = models.FloatField(null=True, blank=True)
    availability_mw = models.FloatField(null=True, blank=True)
    initial_energy_storage_mwh = models.FloatField(null=True, blank=True)
    energy_storage_mwh = models.FloatField(null=True, blank=True)
    fcas_enablement_mw = models.JSONField(default=dict)
    charge_mwh = models.FloatField(default=0.0)
    discharge_mwh = models.FloatField(default=0.0)
    charging_cost = models.FloatField(default=0.0)
    discharge_value = models.FloatField(default=0.0)
    energy_market_value = models.FloatField(default=0.0)
    gross_fcas_value = models.FloatField(default=0.0)
    observable_gross_value = models.FloatField(default=0.0)
    quality_flags = models.JSONField(default=list, blank=True)
    dispatch_source_file = models.CharField(max_length=180)
    scada_source_file = models.CharField(max_length=180)

    class Meta:
        ordering = ['registration', 'interval_end']
        constraints = [
            models.UniqueConstraint(
                fields=['registration', 'interval_end'],
                name='uniq_battery_dispatch_interval',
            ),
        ]
        indexes = [
            models.Index(fields=['operating_date', 'registration']),
            models.Index(fields=['registration', 'interval_end']),
        ]

    def __str__(self):
        return f'{self.registration.duid} {self.interval_end}'


class BatteryDailySummary(models.Model):
    """Precomputed daily metrics used by the public explorer."""

    COMPLETE = 'complete'
    PARTIAL = 'partial'
    QUALITY_CHOICES = [(COMPLETE, 'Complete'), (PARTIAL, 'Partial')]

    asset = models.ForeignKey(BatteryAsset, on_delete=models.CASCADE, related_name='daily_summaries')
    operating_date = models.DateField()
    interval_count = models.PositiveSmallIntegerField(default=0)
    scada_interval_count = models.PositiveSmallIntegerField(default=0)
    storage_interval_count = models.PositiveSmallIntegerField(default=0)
    charge_mwh = models.FloatField(default=0.0)
    discharge_mwh = models.FloatField(default=0.0)
    throughput_mwh = models.FloatField(default=0.0)
    equivalent_cycles = models.FloatField(default=0.0)
    charging_cost = models.FloatField(default=0.0)
    discharge_value = models.FloatField(default=0.0)
    energy_market_value = models.FloatField(default=0.0)
    gross_fcas_value = models.FloatField(default=0.0)
    observable_gross_value = models.FloatField(default=0.0)
    value_per_discharge_mwh = models.FloatField(null=True, blank=True)
    capture_price = models.FloatField(null=True, blank=True)
    peak_charge_mw = models.FloatField(default=0.0)
    peak_discharge_mw = models.FloatField(default=0.0)
    min_storage_mwh = models.FloatField(null=True, blank=True)
    max_storage_mwh = models.FloatField(null=True, blank=True)
    min_state_of_charge_pct = models.FloatField(null=True, blank=True)
    max_state_of_charge_pct = models.FloatField(null=True, blank=True)
    top_five_interval_value_share = models.FloatField(null=True, blank=True)
    benchmark_energy_value = models.FloatField(null=True, blank=True)
    opportunity_capture_ratio = models.FloatField(null=True, blank=True)
    benchmark_version = models.CharField(max_length=30, blank=True)
    quality_status = models.CharField(max_length=12, choices=QUALITY_CHOICES, default=PARTIAL)
    quality_notes = models.JSONField(default=list, blank=True)
    calculation_version = models.CharField(max_length=30, default='mvp-v1')
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-operating_date', 'asset']
        constraints = [
            models.UniqueConstraint(
                fields=['asset', 'operating_date'],
                name='uniq_battery_daily_summary',
            ),
        ]
        indexes = [models.Index(fields=['operating_date', 'quality_status'])]

    def __str__(self):
        return f'{self.asset.name} {self.operating_date}: {self.quality_status}'
