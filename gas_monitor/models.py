"""The static system model: what the east coast gas system is made of.

These tables describe the system rather than what flowed through it. AEMO
publishes the topology as reference data, so the network is ingested and
version-pinned rather than hand-drawn: facilities, the locations they sit
at, the connection points that join them, and the capacity each pipeline
is rated for.

Every table uses the Bulletin Board's own identifier as the primary key.
That is deliberate: these ids are stable, they are how the flow reports
will join back to this model, and making them the key means an upsert
cannot silently create a second row for the same facility.
"""

from django.db import models

from .constants import FACILITY_TYPES, LCA_FLAGS

FACILITY_TYPE_CHOICES = sorted(FACILITY_TYPES.items())
LCA_FLAG_CHOICES = sorted(LCA_FLAGS.items())

FLOW_DIRECTIONS = [
    ('RECEIPT', 'Receipt'),
    ('DELIVERY', 'Delivery'),
    ('NONE', 'Not directional'),
]


class Basin(models.Model):
    """A gas basin. Small, stable, and the anchor for production geography."""

    basin_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Location(models.Model):
    """A named point or hub in the system.

    `location_type` separates a HUB (Wallumbilla, Iona, Longford) from an
    ordinary STANDARD point. The hubs are where trade happens, so the
    distinction matters commercially and not just cartographically.
    """

    location_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=120)
    location_type = models.CharField(max_length=20, blank=True)
    state = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['state', 'name']

    def __str__(self):
        return f'{self.name} ({self.state})'

    @property
    def is_hub(self):
        return self.location_type == 'HUB'


class Facility(models.Model):
    """A registered Bulletin Board facility.

    Covers pipelines, production plants, storage, gas-powered generators,
    large users, compression and the LNG export trains. `operating_state`
    carries AEMO's own ACTIVE / INACTIVE marker, so a decommissioned
    facility stays in the model with its history rather than vanishing.
    """

    facility_id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=160)
    short_name = models.CharField(max_length=60, blank=True)
    facility_type = models.CharField(max_length=20, choices=FACILITY_TYPE_CHOICES)
    type_description = models.CharField(max_length=120, blank=True)
    operating_state = models.CharField(max_length=20, blank=True)
    operating_state_date = models.DateField(null=True, blank=True)
    operator_name = models.CharField(max_length=160, blank=True)
    operator_id = models.IntegerField(null=True, blank=True)
    source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['facility_type', 'name']
        verbose_name_plural = 'facilities'
        indexes = [models.Index(fields=['facility_type'])]

    def __str__(self):
        return f'{self.name} [{self.facility_type}]'

    @property
    def is_active(self):
        return self.operating_state == 'ACTIVE'


class ConnectionPoint(models.Model):
    """Where a facility joins the network.

    A facility reports at EVERY location it touches, not once overall: on
    6 August 2026 the Victorian Transmission System reported at nine
    separate locations, and MSP and EGP at five each. That is why the flow
    tables will key on (gas day, facility, location) rather than
    (gas day, facility) — the shorter key silently discards a fifth of the
    rows. This table is where that fan-out is recorded.
    """

    connection_point_id = models.IntegerField(primary_key=True)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='connection_points')
    location = models.ForeignKey(Location, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='connection_points')
    name = models.CharField(max_length=160)
    flow_direction = models.CharField(max_length=12, choices=FLOW_DIRECTIONS, blank=True)
    node_id = models.IntegerField(null=True, blank=True)
    state_name = models.CharField(max_length=40, blank=True)
    # Populated from a SEPARATE report keyed on (facility, connection point),
    # so it is blank until that second pass runs. Blank means "not yet
    # mapped", never "no demand zone".
    demand_zone = models.CharField(max_length=40, blank=True)
    source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['facility', 'name']
        indexes = [models.Index(fields=['demand_zone'])]

    def __str__(self):
        return f'{self.name} ({self.facility.name})'


class NameplateRating(models.Model):
    """Rated capacity for one directed leg of one facility.

    This is the denominator for every utilisation figure, and it is
    EFFECTIVE-DATED. Utilisation must be computed against the rating in
    force on the gas day being shown, not against today's rating, or the
    chart quietly rewrites history every time a pipeline is re-rated.

    Bidirectional pipelines appear as two rows. The Port Campbell
    Interconnect publishes a separate 400 TJ West-to-East and East-to-West
    entry, which is how reverse-haul capability is discoverable at all.
    """

    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='nameplate_ratings')
    capacity_type = models.CharField(max_length=20, help_text='MDQ and similar AEMO capacity codes.')
    flow_direction = models.CharField(max_length=12, blank=True)
    receipt_location_id = models.IntegerField(null=True, blank=True)
    receipt_location_name = models.CharField(max_length=160, blank=True)
    delivery_location_id = models.IntegerField(null=True, blank=True)
    delivery_location_name = models.CharField(max_length=160, blank=True)
    capacity_tj = models.FloatField(help_text='Rated capacity in terajoules per day.')
    effective_date = models.DateField()
    capacity_description = models.TextField(blank=True)
    description = models.TextField(blank=True)
    source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['facility', '-effective_date']
        constraints = [
            models.UniqueConstraint(
                fields=['facility', 'capacity_type', 'receipt_location_id',
                        'delivery_location_id', 'effective_date'],
                name='uniq_nameplate_leg',
            ),
        ]

    def __str__(self):
        return f'{self.facility.name}: {self.capacity_tj} TJ from {self.effective_date}'

    @property
    def is_directed(self):
        """True when the rating describes a specific receipt-to-delivery leg."""
        return bool(self.receipt_location_id and self.delivery_location_id
                    and self.receipt_location_id > 0 and self.delivery_location_id > 0)


class LinepackZone(models.Model):
    """A pipeline section over which linepack adequacy is assessed."""

    code = models.CharField(max_length=40, primary_key=True)
    operator = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.code


class FlowObservation(models.Model):
    """What one facility actually did at one location on one gas day.

    The core fact table. Quantities are terajoules.

    The natural key is (gas day, facility, location) and NOT (gas day,
    facility): a facility reports separately at every location it touches,
    so on 6 August 2026 the 153 reporting facilities produced 194 rows. The
    shorter key discards a fifth of them with no error at all, which is why
    the constraint below names all three.

    `held_in_storage` is null for everything that is not a storage
    facility, which is most rows (5,663 of 5,843 in the 31-day window).
    Null means "does not store gas", never "stored nothing".

    Column meanings differ by facility type, and for pipelines they are
    not what the names suggest. Measured against MSP on 9 August 2026:

    * `demand` is gas DELIVERED OUT of the pipeline to consumers at that
      location — Sydney 127.4, Regional NSW 39.8, ACT 19.2.
    * `transfer_in` is gas RECEIVED from another facility — Moomba Hub
      180.1, Culcairn 30.3.
    * `transfer_out` is gas handed to another facility.
    * `supply` is gas injected at that location, mostly by production.

    So a pipeline's `demand` is consumption at its delivery points, which
    is why summing demand across facility types double counts: the WGP
    pipeline and the QCLNG plant each reported 1,517.150 TJ on 6 August
    2026, being one quantity of gas seen as a pipeline delivery and again
    as plant consumption. Use `constants.END_USE_TYPES`.

    Throughput, for utilisation, is what the pipeline RECEIVED:
    `supply + transfer_in`. MSP received 210.4 TJ that day against
    191.1 TJ delivered, the difference being fuel and linepack movement.
    """

    gas_date = models.DateField(help_text='Gas day, starting 06:00 AEST.')
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='flows')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='flows')
    demand_tj = models.FloatField(default=0.0)
    supply_tj = models.FloatField(default=0.0)
    transfer_in_tj = models.FloatField(default=0.0)
    transfer_out_tj = models.FloatField(default=0.0)
    held_in_storage_tj = models.FloatField(null=True, blank=True)
    cushion_gas_tj = models.FloatField(null=True, blank=True)
    state = models.CharField(max_length=10, blank=True)
    source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-gas_date', 'facility']
        constraints = [
            models.UniqueConstraint(fields=['gas_date', 'facility', 'location'],
                                    name='uniq_flow_day_facility_location'),
        ]
        indexes = [
            models.Index(fields=['-gas_date']),
            models.Index(fields=['gas_date', 'state']),
        ]

    def __str__(self):
        return f'{self.gas_date} {self.facility.name} @ {self.location.name}'

    @property
    def throughput_tj(self):
        """What this facility took in on this gas day.

        Receipts rather than deliveries, because that is the quantity a
        pipeline's rated capacity constrains.
        """
        return self.supply_tj + self.transfer_in_tj

    @property
    def net_storage_change_tj(self):
        """Positive when gas went in, negative when it came out.

        Storage facilities report injection as `demand` and withdrawal as
        `supply`, which reads backwards until you remember the reporting is
        from the pipeline's point of view.
        """
        return self.demand_tj - self.supply_tj


class FlowForecast(models.Model):
    """What a facility expects to do on a future gas day.

    A SEPARATE table from FlowObservation on purpose. The two carry the
    same columns and it would be tempting to add a `kind` flag, but the
    site's third analytical principle is that actuals and forecasts must
    never be conflated, and one table with a flag is exactly how they get
    conflated in a careless query six months from now.
    """

    gas_date = models.DateField()
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='forecasts')
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='forecasts')
    demand_tj = models.FloatField(default=0.0)
    supply_tj = models.FloatField(default=0.0)
    transfer_in_tj = models.FloatField(default=0.0)
    transfer_out_tj = models.FloatField(default=0.0)
    state = models.CharField(max_length=10, blank=True)
    source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['gas_date', 'facility']
        constraints = [
            models.UniqueConstraint(fields=['gas_date', 'facility', 'location'],
                                    name='uniq_forecast_day_facility_location'),
        ]
        indexes = [models.Index(fields=['gas_date'])]

    def __str__(self):
        return f'forecast {self.gas_date} {self.facility.name}'


class LinepackAdequacy(models.Model):
    """AEMO's forward view of whether a pipeline can meet nominated flows.

    The most direct "becoming constrained" signal in the dataset, and the
    reason this app can talk about the future at all: it is published for
    gas days ahead of today, unlike utilisation, which can only ever be
    computed after the fact.

    The source stamps `GasDate` with a time (15:15) that is the assessment
    moment rather than part of the day's identity, so it is reduced to a
    date here. Keeping the time would create one row per assessment and
    silently break the one-flag-per-pipeline-per-day contract.
    """

    gas_date = models.DateField()
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='linepack_flags')
    flag = models.CharField(max_length=10, choices=LCA_FLAG_CHOICES)
    description = models.TextField(blank=True)
    source_last_updated = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['gas_date', 'facility']
        verbose_name_plural = 'linepack adequacy flags'
        constraints = [
            models.UniqueConstraint(fields=['gas_date', 'facility'], name='uniq_lca_day_facility'),
        ]
        indexes = [models.Index(fields=['gas_date', 'flag'])]

    def __str__(self):
        return f'{self.gas_date} {self.facility.name}: {self.flag}'


class MissingSubmission(models.Model):
    """A facility that had not reported for a gas day.

    AEMO publishes this list, so missingness is an observation rather than
    an inference. Ingesting it is what lets the page say "three facilities
    had not submitted" instead of rendering a hole and hoping nobody asks.

    `connection_point_id` is the source's own value and can be -1, meaning
    the whole facility rather than one point. It is stored as a plain
    integer rather than a foreign key because a submission can be missing
    for a point the registry does not know about.
    """

    gas_date = models.DateField()
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE, related_name='missing_submissions')
    connection_point_id = models.IntegerField(default=-1)

    class Meta:
        ordering = ['-gas_date', 'facility']
        constraints = [
            models.UniqueConstraint(fields=['gas_date', 'facility', 'connection_point_id'],
                                    name='uniq_missing_day_facility_point'),
        ]

    def __str__(self):
        return f'{self.gas_date} missing: {self.facility.name}'


class SourceCoverage(models.Model):
    """How current each source is, and whether the window is at risk.

    This exists so staleness is visible on the public page rather than
    only to whoever remembers to check a log. If the weekly refresh stops
    running, the page says so and the failure is noticed. That is the
    alerting: no monitoring stack, and it satisfies the site's requirement
    that stale states be honest.
    """

    source = models.CharField(max_length=32, unique=True)
    last_run_at = models.DateTimeField()
    earliest_gas_date = models.DateField(null=True, blank=True)
    latest_gas_date = models.DateField(null=True, blank=True)
    rows_stored = models.IntegerField(default=0)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['source']
        verbose_name_plural = 'source coverage'

    def __str__(self):
        return f'{self.source} to {self.latest_gas_date}'


class GasDataRefresh(models.Model):
    """An admin-triggered fetch.

    Deliberately NOT a file upload. Every Bulletin Board report is an
    unauthenticated HTTP GET, so the server can fetch them itself; asking
    an operator to download and upload twenty files a day would invent
    manual work the price lab already decided not to invent.

    The record is the ritual: create one, choose a source group, and the
    import summary is written back onto the row exactly as the fuel-mix
    upload does. Backfill does NOT belong here — a dozen sequential
    network fetches will outlast the gunicorn request timeout. That is a
    management command run over SSH.
    """

    class Sources(models.TextChoices):
        WEEKLY = 'weekly', 'Weekly refresh: everything (the Monday ritual)'
        TIME_SERIES = 'time_series', 'Flows, forecasts, linepack flags, missing submissions'
        REFERENCE = 'reference', 'Reference: facilities, locations, connection points, capacity'

    sources = models.CharField(max_length=20, choices=Sources.choices, default=Sources.WEEKLY)
    requested_at = models.DateTimeField(auto_now_add=True)
    result = models.TextField(blank=True, default='', help_text='Import summary (filled automatically).')

    class Meta:
        ordering = ['-requested_at']
        verbose_name = 'gas data refresh'
        verbose_name_plural = 'gas data refreshes'

    def __str__(self):
        return f'{self.get_sources_display()} on {self.requested_at:%Y-%m-%d %H:%M}'
