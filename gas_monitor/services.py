"""Storing the static system model.

Writes resolve conflicts on the source's own identifier rather than
deleting and re-inserting. The fuel-mix dashboard can get away with
delete-then-insert because its key covers the whole snapshot; here it
would be actively destructive, since a partial file would wipe every
facility sharing the deleted key. `nem_price_lab.services` documents the
same hazard for regions, and the fan-out is far wider in gas: on
6 August 2026 one gas day held 194 rows across 153 facilities.
"""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Max, Min, Q, Sum
from django.utils import timezone

from . import ingest
from .constants import (
    BACKWARD_WINDOW_SOURCES, END_USE_TYPES, FACILITY_TYPES, GBB_EXPANSION_DATE,
    LCA_CONSTRAINED_FLAGS, LOCATION_LAYOUT, SOURCE_WINDOW_DAYS, SUPPLY_TYPES,
)
from .models import (
    Basin, ConnectionPoint, Facility, FlowForecast, FlowObservation, GasDataRefresh,
    LinepackAdequacy, LinepackZone, Location, MissingSubmission, NameplateRating,
    SourceCoverage,
)  # noqa: F401  (NameplateRating is used by capacity_in_force)

BATCH = 1000


# ── Storing ───────────────────────────────────────────────────────────

@transaction.atomic
def upsert_basins(rows):
    if not rows:
        return 0
    Basin.objects.bulk_create(
        [Basin(**row) for row in rows],
        update_conflicts=True, update_fields=['name'],
        unique_fields=['basin_id'], batch_size=BATCH,
    )
    return len(rows)


@transaction.atomic
def upsert_locations(rows):
    if not rows:
        return 0
    Location.objects.bulk_create(
        [Location(**row) for row in rows],
        update_conflicts=True,
        update_fields=['name', 'location_type', 'state', 'description', 'source_last_updated'],
        unique_fields=['location_id'], batch_size=BATCH,
    )
    return len(rows)


@transaction.atomic
def upsert_facilities(rows):
    if not rows:
        return 0
    Facility.objects.bulk_create(
        [Facility(**row) for row in rows],
        update_conflicts=True,
        update_fields=['name', 'short_name', 'facility_type', 'type_description',
                       'operating_state', 'operating_state_date', 'operator_name',
                       'operator_id', 'source_last_updated'],
        unique_fields=['facility_id'], batch_size=BATCH,
    )
    return len(rows)


@transaction.atomic
def upsert_connection_points(rows):
    """Store connection points, skipping any whose facility we do not hold.

    Returns (stored, orphaned). An orphan is not dropped quietly: it means
    the facility registry is older than the connection point registry, and
    the caller reports the count so that shows up as a visible state rather
    than a missing row nobody notices.
    """
    if not rows:
        return 0, 0

    known_facilities = set(Facility.objects.values_list('facility_id', flat=True))
    known_locations = set(Location.objects.values_list('location_id', flat=True))

    keep = []
    orphaned = 0
    for row in rows:
        if row['facility_id'] not in known_facilities:
            orphaned += 1
            continue
        row = dict(row)
        if row.get('location_id') not in known_locations:
            row['location_id'] = None
        keep.append(row)

    ConnectionPoint.objects.bulk_create(
        [ConnectionPoint(**row) for row in keep],
        update_conflicts=True,
        update_fields=['facility_id', 'location_id', 'name', 'flow_direction',
                       'node_id', 'state_name', 'source_last_updated'],
        unique_fields=['connection_point_id'], batch_size=BATCH,
    )
    return len(keep), orphaned


@transaction.atomic
def apply_demand_zones(rows):
    """Second pass: attach demand zones to connection points already stored.

    Deliberately does not create connection points. A mapping row for a
    point we do not hold means the registry needs refreshing, which is
    information; inventing a half-populated point would hide it.
    """
    if not rows:
        return 0, 0

    by_id = {row['connection_point_id']: row['demand_zone'] for row in rows}
    points = list(ConnectionPoint.objects.filter(connection_point_id__in=by_id.keys()))
    for point in points:
        point.demand_zone = by_id[point.connection_point_id]
    ConnectionPoint.objects.bulk_update(points, ['demand_zone'], batch_size=BATCH)
    return len(points), len(by_id) - len(points)


@transaction.atomic
def upsert_linepack_zones(rows):
    if not rows:
        return 0
    # One row per zone: the source repeats a zone once per pipeline segment,
    # so collapse on the code before writing or the upsert conflicts with
    # itself inside a single batch.
    unique = {row['code']: row for row in rows}
    LinepackZone.objects.bulk_create(
        [LinepackZone(**row) for row in unique.values()],
        update_conflicts=True, update_fields=['operator', 'description'],
        unique_fields=['code'], batch_size=BATCH,
    )
    return len(unique)


@transaction.atomic
def upsert_nameplate(rows):
    """Store rated capacity legs, skipping any whose facility we do not hold."""
    if not rows:
        return 0, 0

    known_facilities = set(Facility.objects.values_list('facility_id', flat=True))
    keep = [row for row in rows if row['facility_id'] in known_facilities]
    orphaned = len(rows) - len(keep)

    # The source can publish the same leg twice within one file. Collapsing
    # on the unique key first keeps the batch from conflicting with itself.
    unique = {}
    for row in keep:
        key = (row['facility_id'], row['capacity_type'], row['receipt_location_id'],
               row['delivery_location_id'], row['effective_date'])
        unique[key] = row

    NameplateRating.objects.bulk_create(
        [NameplateRating(**row) for row in unique.values()],
        update_conflicts=True,
        update_fields=['flow_direction', 'receipt_location_name', 'delivery_location_name',
                       'capacity_tj', 'capacity_description', 'description',
                       'source_last_updated'],
        unique_fields=['facility', 'capacity_type', 'receipt_location_id',
                       'delivery_location_id', 'effective_date'],
        batch_size=BATCH,
    )
    return len(unique), orphaned


# ── Time series ───────────────────────────────────────────────────────

def _drop_stale(rows, model, key_fields):
    """Discard incoming rows the database already holds a NEWER version of.

    Bulletin Board rows revise: a facility can restate a gas day days
    later, and every row carries the source's own `LastUpdated`. Comparing
    it before overwriting makes ingestion ORDER-INDEPENDENT, which is what
    lets a backfill from the archive run after an incremental without
    clobbering fresher data with older data.

    A row we have never seen is always kept. A row whose stored timestamp
    is null (or whose incoming timestamp is null) is also kept, because
    "unknown" is not evidence of being newer, and refusing to write would
    strand the record permanently.

    Returns (keep, superseded).
    """
    if not rows:
        return [], 0

    # Look up only the gas days this batch touches. Scanning the whole table
    # is harmless at one week of data and ruinous at eight years of it: the
    # archive backfill holds 435,688 rows, and a full scan per chunk would
    # turn a linear job into a quadratic one.
    days = {row['gas_date'] for row in rows}
    stored = {}
    for values in (model.objects.filter(gas_date__in=days)
                   .values_list(*key_fields, 'source_last_updated')):
        stored[values[:-1]] = values[-1]

    keep, superseded = [], 0
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        existing = stored.get(key)
        incoming = row.get('source_last_updated')
        if existing is not None and incoming is not None and incoming < existing:
            superseded += 1
            continue
        keep.append(row)
    return keep, superseded


def _known_ids():
    return (set(Facility.objects.values_list('facility_id', flat=True)),
            set(Location.objects.values_list('location_id', flat=True)))


@transaction.atomic
def upsert_flows(rows):
    """Store actual flows. Returns (stored, orphaned, superseded)."""
    if not rows:
        return 0, 0, 0

    facilities, locations = _known_ids()
    keep = [r for r in rows
            if r['facility_id'] in facilities and r['location_id'] in locations]
    orphaned = len(rows) - len(keep)

    keep, superseded = _drop_stale(keep, FlowObservation,
                                   ['gas_date', 'facility_id', 'location_id'])

    # The source can repeat a key within one file when a facility restates.
    # Collapsing keeps the batch from conflicting with itself; the last
    # occurrence wins, which matches how the file is ordered.
    unique = {(r['gas_date'], r['facility_id'], r['location_id']): r for r in keep}

    FlowObservation.objects.bulk_create(
        [FlowObservation(**row) for row in unique.values()],
        update_conflicts=True,
        update_fields=['demand_tj', 'supply_tj', 'transfer_in_tj', 'transfer_out_tj',
                       'held_in_storage_tj', 'cushion_gas_tj', 'state', 'source_last_updated'],
        unique_fields=['gas_date', 'facility', 'location'], batch_size=BATCH,
    )
    return len(unique), orphaned, superseded


@transaction.atomic
def upsert_forecasts(rows):
    if not rows:
        return 0, 0, 0

    facilities, locations = _known_ids()
    keep = [r for r in rows
            if r['facility_id'] in facilities and r['location_id'] in locations]
    orphaned = len(rows) - len(keep)

    keep, superseded = _drop_stale(keep, FlowForecast,
                                   ['gas_date', 'facility_id', 'location_id'])
    unique = {(r['gas_date'], r['facility_id'], r['location_id']): r for r in keep}

    FlowForecast.objects.bulk_create(
        [FlowForecast(**row) for row in unique.values()],
        update_conflicts=True,
        update_fields=['demand_tj', 'supply_tj', 'transfer_in_tj', 'transfer_out_tj',
                       'state', 'source_last_updated'],
        unique_fields=['gas_date', 'facility', 'location'], batch_size=BATCH,
    )
    return len(unique), orphaned, superseded


@transaction.atomic
def upsert_linepack_adequacy(rows):
    if not rows:
        return 0, 0, 0

    facilities, _ = _known_ids()
    keep = [r for r in rows if r['facility_id'] in facilities]
    orphaned = len(rows) - len(keep)

    keep, superseded = _drop_stale(keep, LinepackAdequacy, ['gas_date', 'facility_id'])
    unique = {(r['gas_date'], r['facility_id']): r for r in keep}

    LinepackAdequacy.objects.bulk_create(
        [LinepackAdequacy(**row) for row in unique.values()],
        update_conflicts=True,
        update_fields=['flag', 'description', 'source_last_updated'],
        unique_fields=['gas_date', 'facility'], batch_size=BATCH,
    )
    return len(unique), orphaned, superseded


@transaction.atomic
def upsert_missing(rows):
    """Store AEMO's own list of non-submissions.

    No `LastUpdated` is published for this report, so there is nothing to
    compare and the key alone carries idempotency.
    """
    if not rows:
        return 0, 0, 0

    facilities, _ = _known_ids()
    keep = [r for r in rows if r['facility_id'] in facilities]
    orphaned = len(rows) - len(keep)

    unique = {(r['gas_date'], r['facility_id'], r['connection_point_id']): r for r in keep}
    MissingSubmission.objects.bulk_create(
        [MissingSubmission(**row) for row in unique.values()],
        update_conflicts=True, update_fields=['connection_point_id'],
        unique_fields=['gas_date', 'facility', 'connection_point_id'], batch_size=BATCH,
    )
    # No revision timestamp to compare, so nothing can be superseded.
    return len(unique), orphaned, 0


# ── Coverage ──────────────────────────────────────────────────────────

MODEL_FOR_SOURCE = {
    'flows': FlowObservation,
    'forecasts': FlowForecast,
    'linepack_adequacy': LinepackAdequacy,
    'missing': MissingSubmission,
}


def record_coverage(source, rows_stored=0, note=''):
    """Write down how current a source is, after ingesting it."""
    model = MODEL_FOR_SOURCE.get(source)
    earliest = latest = None
    if model is not None:
        dates = model.objects.order_by('gas_date').values_list('gas_date', flat=True)
        if dates.exists():
            earliest = dates.first()
            latest = model.objects.order_by('-gas_date').values_list('gas_date', flat=True).first()

    SourceCoverage.objects.update_or_create(
        source=source,
        defaults={'last_run_at': timezone.now(), 'earliest_gas_date': earliest,
                  'latest_gas_date': latest, 'rows_stored': rows_stored, 'note': note[:200]},
    )


def coverage_report(today=None):
    """How current every source is, and how long before the window bites.

    Only backward-looking sources can lose data when a refresh is skipped.
    A forward report simply publishes a fresh outlook, so a missed run
    costs nothing but currency.
    """
    today = today or timezone.localdate()
    rows = []
    for coverage in SourceCoverage.objects.all():
        window = SOURCE_WINDOW_DAYS.get(coverage.source)
        at_risk = coverage.source in BACKWARD_WINDOW_SOURCES
        offset = (today - coverage.latest_gas_date).days if coverage.latest_gas_date else None

        # A forward report's latest gas day is in the future, so the same
        # subtraction that measures lag for an actuals report measures
        # reach for an outlook. Reporting one as a negative of the other
        # reads as a bug on the page, so they are named separately.
        days_behind = offset if at_risk else None
        days_ahead = -offset if (not at_risk and offset is not None) else None

        days_until_loss = None
        if at_risk and window and offset is not None:
            days_until_loss = window - offset

        rows.append({
            'source': coverage.source,
            'last_run_at': coverage.last_run_at,
            'earliest_gas_date': coverage.earliest_gas_date,
            'latest_gas_date': coverage.latest_gas_date,
            'rows_stored': coverage.rows_stored,
            'days_behind': days_behind,
            'days_ahead': days_ahead,
            'window_days': window,
            'loses_data_if_skipped': at_risk,
            'days_until_loss': days_until_loss,
            'note': coverage.note,
        })
    return rows


def gas_day_gaps():
    """Gas days missing from the flow table between the first and last held.

    The failure mode this app is most exposed to is silent: a refresh that
    stops running loses days rather than raising. Only an active check
    finds that, which is why this is a first-class function rather than
    something to eyeball in the admin.
    """
    # Count first, enumerate only if the count says something is missing.
    # Materialising every distinct gas date across 432,000 rows cost a
    # second on every page load to answer a question that is almost always
    # "no gaps"; the aggregate answers it in milliseconds.
    bounds = FlowObservation.objects.aggregate(first=Min('gas_date'), last=Max('gas_date'))
    if not bounds['first']:
        return []

    span = (bounds['last'] - bounds['first']).days + 1
    held_count = FlowObservation.objects.values('gas_date').distinct().count()
    if held_count >= span:
        return []

    held = set(FlowObservation.objects.values_list('gas_date', flat=True).distinct())
    expected = {bounds['first'] + timedelta(days=n) for n in range(span)}
    return sorted(expected - held)


# ── Orchestration ─────────────────────────────────────────────────────

# Order matters: locations and facilities must exist before anything that
# references them, connection points before the demand-zone pass that
# annotates them, and the whole registry before any flow row can resolve
# its foreign keys.
REFERENCE_ORDER = [
    'basins', 'locations', 'facilities', 'connection_points',
    'demand_zones', 'linepack_zones', 'nameplate',
]

TIME_SERIES_ORDER = ['flows', 'forecasts', 'linepack_adequacy', 'missing']

# The Monday ritual: reference first so a facility registered during the
# week exists before the flows that reference it arrive.
WEEKLY_ORDER = REFERENCE_ORDER + TIME_SERIES_ORDER


def _store_simple(fn):
    """Adapt an upsert returning just a count."""
    return lambda rows: (fn(rows), 0, 0)


def _store_pair(fn):
    """Adapt an upsert returning (stored, orphaned)."""
    return lambda rows: (*fn(rows), 0)


# One storage rule per report. A dispatch table rather than a branch chain
# so adding a source is one line and cannot silently fall through.
STORAGE_RULES = {
    'basins': _store_simple(upsert_basins),
    'locations': _store_simple(upsert_locations),
    'facilities': _store_simple(upsert_facilities),
    'connection_points': _store_pair(upsert_connection_points),
    'demand_zones': _store_pair(apply_demand_zones),
    'linepack_zones': _store_simple(upsert_linepack_zones),
    'nameplate': _store_pair(upsert_nameplate),
    'flows': upsert_flows,
    'forecasts': upsert_forecasts,
    'linepack_adequacy': upsert_linepack_adequacy,
    'missing': upsert_missing,
}


def ingest_report(key, text=None):
    """Fetch (or parse supplied text for) one report and store it.

    Returns a report dict. `text` lets a caller replay a file downloaded by
    hand, which is the recovery path when the network is the problem.
    """
    try:
        parser = ingest.PARSERS[key]
        store = STORAGE_RULES[key]
    except KeyError:
        raise ingest.IngestError(f'no storage rule for report {key!r}')

    if text is None:
        text = ingest.fetch_report(key)

    rows, report = parser(text)
    report['stored'], report['orphaned'], report['superseded'] = store(rows)
    report['report'] = key

    if key in MODEL_FOR_SOURCE:
        record_coverage(key, rows_stored=report['stored'])

    return report


# Kept as the name the reference-only command and its tests already use.
ingest_reference_report = ingest_report


ARCHIVE_CHUNK = 20000

# Share of assessed days flagged, above which a pipeline is described as
# chronically tight rather than as having an event. Two thirds is a
# judgement, not a standard: it is high enough that an ordinary bad winter
# does not qualify, and the page states the raw count alongside it so the
# reader can disagree.
CHRONIC_THRESHOLD = 2 / 3


def ingest_archive(key, text=None, chunk_size=ARCHIVE_CHUNK, progress=None):
    """Backfill one report from its full-history archive.

    Parsed once, then stored in chunks. Chunking is what keeps memory flat
    and lets `_drop_stale` look up only the gas days in front of it rather
    than the whole table, which is the difference between a linear job and
    a quadratic one at 435,688 rows.

    Safe to re-run, and safe to run either side of an incremental: the
    newer-wins rule means an eight-year-old archive cannot overwrite a row
    the weekly refresh has already restated.
    """
    if text is None:
        text = ingest.fetch_archive(key)

    rows, report = ingest.PARSERS[key](text)
    store = STORAGE_RULES[key]

    stored = orphaned = superseded = 0
    for index, chunk in enumerate(ingest.iter_chunks(rows, chunk_size), start=1):
        chunk_stored, chunk_orphaned, chunk_superseded = store(chunk)
        stored += chunk_stored
        orphaned += chunk_orphaned
        superseded += chunk_superseded
        if progress:
            progress(index * chunk_size, len(rows), stored)

    report.update({'report': key, 'stored': stored, 'orphaned': orphaned,
                   'superseded': superseded, 'archive': True})

    if key in MODEL_FOR_SOURCE:
        record_coverage(key, rows_stored=stored, note='archive backfill')

    return report


def ingest_reports(keys):
    """Refresh a named set of reports, in the order given.

    One report failing does not abort the rest: a fetch failure on the
    nameplate file should not cost you a refreshed facility registry. Each
    failure is recorded in the returned list so the caller can surface it.
    """
    reports = []
    for key in keys:
        try:
            reports.append(ingest_report(key))
        except ingest.IngestError as exc:
            reports.append({'report': key, 'error': str(exc), 'stored': 0, 'parsed': 0,
                            'skipped': 0, 'orphaned': 0, 'superseded': 0, 'issues': []})
    return reports


def ingest_reference(keys=None):
    return ingest_reports(keys or REFERENCE_ORDER)


def ingest_time_series(keys=None):
    return ingest_reports(keys or TIME_SERIES_ORDER)


def ingest_weekly():
    """Everything, in dependency order. This is the Monday morning refresh."""
    return ingest_reports(WEEKLY_ORDER)


def summarise(reports):
    """One-line-per-report summary, for a command's stdout or an admin row."""
    lines = []
    for report in reports:
        if report.get('error'):
            lines.append(f"{report['report']}: FAILED — {report['error']}")
            continue
        line = f"{report['report']}: stored {report['stored']} of {report['parsed']} parsed"
        if report.get('skipped'):
            line += f", skipped {report['skipped']}"
        if report.get('orphaned'):
            line += f", {report['orphaned']} unmatched"
        if report.get('superseded'):
            line += f", {report['superseded']} already newer"
        lines.append(line)
    return '\n'.join(lines)


def record_refresh(refresh_id, text):
    """Write an import summary back onto a GasDataRefresh row.

    Uses update() so saving the summary does not re-trigger the post_save
    receiver that produced it.
    """
    GasDataRefresh.objects.filter(pk=refresh_id).update(result=text[:4000])


# ── Reading the model back ────────────────────────────────────────────

def system_model_summary():
    """Counts and groupings for the system model page.

    Returns None when nothing has been ingested, so the view can render an
    honest empty state rather than a page of zeroes that looks like a
    system with no facilities in it.
    """
    total = Facility.objects.count()
    if not total:
        return None

    by_type = {}
    for facility in Facility.objects.all():
        entry = by_type.setdefault(facility.facility_type, {
            'code': facility.facility_type,
            'label': facility.get_facility_type_display(),
            'total': 0, 'active': 0,
        })
        entry['total'] += 1
        if facility.is_active:
            entry['active'] += 1

    return {
        'facilities': total,
        'by_type': sorted(by_type.values(), key=lambda e: -e['total']),
        'locations': Location.objects.count(),
        'hubs': Location.objects.filter(location_type='HUB').count(),
        'connection_points': ConnectionPoint.objects.count(),
        'mapped_zones': ConnectionPoint.objects.exclude(demand_zone='').count(),
        'basins': Basin.objects.count(),
        'linepack_zones': LinepackZone.objects.count(),
        'ratings': NameplateRating.objects.count(),
    }


def latest_gas_day():
    """The most recent gas day with actual flows, or None."""
    return FlowObservation.objects.order_by('-gas_date').values_list('gas_date', flat=True).first()


def gas_day_picture(gas_date=None):
    """What the system did on one gas day.

    Deliberately splits end-use demand from pipeline receipts. Summing the
    two would double count, because a pipeline's "demand" is gas taken on
    for transport and reappears as consumption at the plant it feeds: on
    6 August 2026 the WGP pipeline and the QCLNG plant each reported
    1,517.150 TJ, one quantity of gas seen twice.

    Returns None when no flows are held, so the caller renders an honest
    empty state rather than a page of zeroes.
    """
    gas_date = gas_date or latest_gas_day()
    if gas_date is None:
        return None

    flows = (FlowObservation.objects
             .filter(gas_date=gas_date)
             .select_related('facility', 'location'))

    end_use = {}
    supply_total = 0.0
    pipeline_receipts = 0.0
    storage_rows = []

    for flow in flows:
        kind = flow.facility.facility_type
        if kind in END_USE_TYPES:
            entry = end_use.setdefault(kind, {'code': kind, 'demand_tj': 0.0, 'facilities': set()})
            entry['demand_tj'] += flow.demand_tj
            entry['facilities'].add(flow.facility_id)
        elif kind == 'PIPE':
            pipeline_receipts += flow.demand_tj
        if kind in ('PROD', 'STOR'):
            supply_total += flow.supply_tj
        if kind == 'STOR':
            storage_rows.append(flow)

    for entry in end_use.values():
        entry['facilities'] = len(entry['facilities'])

    end_use_total = sum(e['demand_tj'] for e in end_use.values())
    for entry in end_use.values():
        entry['share'] = (entry['demand_tj'] / end_use_total * 100) if end_use_total else 0.0

    storage = sorted(
        ({'name': f.facility.name,
          'held_tj': f.held_in_storage_tj or 0.0,
          'injected_tj': f.demand_tj,
          'withdrawn_tj': f.supply_tj,
          'net_tj': f.demand_tj - f.supply_tj}
         for f in storage_rows),
        key=lambda s: -s['held_tj'],
    )

    return {
        'gas_date': gas_date,
        'rows': flows.count(),
        'reporting_facilities': flows.values('facility_id').distinct().count(),
        'end_use': sorted(end_use.values(), key=lambda e: -e['demand_tj']),
        'end_use_total_tj': end_use_total,
        'pipeline_receipts_tj': pipeline_receipts,
        'supply_total_tj': supply_total,
        'storage': storage,
        'storage_held_tj': sum(s['held_tj'] for s in storage),
        'storage_net_tj': sum(s['net_tj'] for s in storage),
        'missing': list(MissingSubmission.objects
                        .filter(gas_date=gas_date)
                        .select_related('facility')),
    }


def capacity_in_force(facility_ids, gas_date):
    """Largest rated capacity in force on one gas day, per facility.

    "In force" means the most recent effective date at or before the gas
    day. Joining to today's rating instead would silently rewrite history
    every time a pipeline is re-rated, which is the trap this whole
    function exists to avoid. The Moomba to Sydney system makes it
    concrete: on 10 August 2026 every one of its current ratings carried
    an effective date of 2026-08-10, so gas day 2026-08-09 has no rating
    in force from the current-ratings file alone and must be answered from
    the archive.

    Returns {facility_id: (capacity_tj, effective_date)}, omitting any
    facility with no rating yet in force. Absent is not zero, and callers
    must render it as "not rated" rather than as an empty bar.

    The value is the LARGEST leg, not the sum. Legs are alternative
    receipt-to-delivery paths and a bidirectional pipeline publishes one
    each way, so adding them would invent capacity that cannot exist at
    once. Per-leg utilisation is not derivable, because flows are reported
    per location rather than per leg.
    """
    # Ask the database for the effective date in force per facility, then
    # fetch only those rows. Pulling every rating on or before the gas day
    # and reducing in Python meant scanning 124,000 rows to answer a
    # question about 45 pipelines.
    in_force = _effective_dates_in_force(facility_ids, gas_date)
    if not in_force:
        return {}

    condition = Q()
    for facility_id, effective in in_force.items():
        condition |= Q(facility_id=facility_id, effective_date=effective)

    latest = {}
    for facility_id, effective, capacity in (NameplateRating.objects
                                             .filter(condition)
                                             .values_list('facility_id', 'effective_date',
                                                          'capacity_tj')):
        current = latest.get(facility_id)
        if current is None or capacity > current[0]:
            latest[facility_id] = (capacity, effective)
    return latest


def _effective_dates_in_force(facility_ids, gas_date):
    """The most recent effective date at or before `gas_date`, per facility."""
    rows = (NameplateRating.objects
            .filter(facility_id__in=facility_ids, effective_date__lte=gas_date)
            .values('facility_id')
            .annotate(effective=Max('effective_date')))
    return {row['facility_id']: row['effective'] for row in rows}


def legs_in_force(facility_ids, gas_date):
    """Rated legs actually in force on one gas day, per facility.

    NOT a count of stored ratings. After the archive backfill the Amadeus
    Gas Pipeline holds 2,709 nameplate rows, each with its own effective
    date — that is how many times it has been re-rated since 2019, not how
    many legs it has. Exactly one is in force on any given gas day.

    A pipeline with more than one leg in force at the same effective date
    is bidirectional or serves several receipt-to-delivery paths, which is
    the only way reverse-haul capability is discoverable.

    Returns {facility_id: [rating, ...]} for the effective date in force.
    """
    latest_date = _effective_dates_in_force(facility_ids, gas_date)
    if not latest_date:
        return {}

    condition = Q()
    for facility_id, effective in latest_date.items():
        condition |= Q(facility_id=facility_id, effective_date=effective)

    in_force = {}
    for rating in NameplateRating.objects.filter(condition):
        in_force.setdefault(rating.facility_id, []).append(rating)
    return in_force


def pipeline_utilisation(gas_date=None, minimum_capacity_tj=1.0):
    """Throughput against rated capacity, per pipeline, for one gas day.

    Throughput is what the pipeline RECEIVED — supply plus transfers in —
    because that is the quantity its rating constrains. Deliveries differ
    by fuel burn and linepack movement.

    Pipelines with no rating in force, or a rating too small to divide by
    safely, are returned with `capacity_tj` of None so the caller can say
    "not rated" instead of drawing a misleading bar.
    """
    gas_date = gas_date or latest_gas_day()
    if gas_date is None:
        return None

    flows = (FlowObservation.objects
             .filter(gas_date=gas_date, facility__facility_type='PIPE')
             .values('facility_id', 'facility__name')
             .annotate(received=Sum('supply_tj') + Sum('transfer_in_tj'),
                       delivered=Sum('demand_tj') + Sum('transfer_out_tj')))

    flows = list(flows)
    capacities = capacity_in_force([f['facility_id'] for f in flows], gas_date)

    rows = []
    for flow in flows:
        capacity, effective = capacities.get(flow['facility_id'], (None, None))
        usable = capacity if capacity and capacity >= minimum_capacity_tj else None
        received = flow['received'] or 0.0
        rows.append({
            'facility_id': flow['facility_id'],
            'name': flow['facility__name'],
            'received_tj': received,
            'delivered_tj': flow['delivered'] or 0.0,
            'capacity_tj': usable,
            'capacity_effective': effective if usable else None,
            'utilisation_pct': (received / usable * 100) if usable else None,
        })

    # Receipts exceeding the largest rated leg do not mean the pipeline is
    # over capacity. MDQ is a POINT-TO-POINT rating, so a pipeline taking
    # gas in at several points can legitimately carry more than any single
    # leg allows. The South West Queensland Pipeline received 474.5 TJ at
    # Wallumbilla and 161.5 TJ at Moomba on 9 August 2026 — 636 TJ against
    # legs of 512 and 340 — which says the single-leg denominator does not
    # describe that pipeline, not that it was 124% utilised.
    for row in rows:
        row['denominator_suspect'] = (row['utilisation_pct'] is not None
                                      and row['utilisation_pct'] > 100)

    rated = [r for r in rows if r['utilisation_pct'] is not None]
    rated.sort(key=lambda r: -r['utilisation_pct'])
    unrated = sorted((r for r in rows if r['utilisation_pct'] is None),
                     key=lambda r: -r['received_tj'])

    # Scarcity counts exclude the suspect ones. Counting a pipeline whose
    # denominator we know to be wrong as "above 90%" would manufacture
    # tightness out of a modelling limitation.
    meaningful = [r for r in rated if not r['denominator_suspect']]

    return {
        'gas_date': gas_date,
        'rated': rated,
        'unrated': unrated,
        'suspect': [r for r in rated if r['denominator_suspect']],
        'above_90': sum(1 for r in meaningful if r['utilisation_pct'] >= 90),
        'above_70': sum(1 for r in meaningful if r['utilisation_pct'] >= 70),
        'meaningful_count': len(meaningful),
        'busiest': meaningful[0] if meaningful else None,
    }


def storage_history(days=1825, end=None):
    """Storage holdings per facility over time, with a seasonal reference.

    Storage has been reported since 2018, so unlike end-use demand this
    series can use the full record and is unaffected by the 2023
    expansion.

    The reference line is the median holding for that day-of-year across
    every prior year, which is what makes a level mean anything: 14,403 TJ
    in Iona is only informative next to what Iona usually holds in August.
    Years with no data for a day-of-year simply do not contribute.
    """
    end = end or latest_gas_day()
    if end is None:
        return None

    start = end - timedelta(days=days - 1)
    rows = (FlowObservation.objects
            .filter(gas_date__gte=start, gas_date__lte=end,
                    facility__facility_type='STOR',
                    held_in_storage_tj__isnull=False)
            .values('gas_date', 'facility_id', 'facility__name',
                    'held_in_storage_tj', 'demand_tj', 'supply_tj')
            .order_by('gas_date'))

    by_facility = {}
    for row in rows:
        entry = by_facility.setdefault(row['facility_id'], {
            'name': row['facility__name'], 'held': {}, 'moved': {},
        })
        entry['held'][row['gas_date']] = row['held_in_storage_tj']
        entry['moved'][row['gas_date']] = row['demand_tj'] + row['supply_tj']

    if not by_facility:
        return None

    suspect = _drop_implausible_holdings(by_facility)

    dates = sorted({d for entry in by_facility.values() for d in entry['held']})

    # The seasonal reference is built PER FACILITY and then summed only
    # over the facilities that actually reported on the day being drawn.
    #
    # Summing the system first and comparing totals across years is wrong
    # whenever coverage changes, and it does: Silver Springs reported on
    # 9 August in every year from 2021 to 2025 but not in 2026, so a
    # five-facility total was being measured against six-facility history
    # and showed a 39% shortfall that was pure artefact. Like-for-like is
    # the only comparison worth drawing.
    facility_reference = {}
    for facility_id, entry in by_facility.items():
        by_doy = {}
        for day, value in entry['held'].items():
            by_doy.setdefault((day.month, day.day), []).append((day.year, value))
        facility_reference[facility_id] = {
            day: _median([v for year, v in by_doy.get((day.month, day.day), [])
                          if year != day.year])
            for day in dates
        }

    totals, reference, reporting = [], [], []
    for day in dates:
        present = [fid for fid, entry in by_facility.items() if day in entry['held']]
        totals.append(sum(by_facility[fid]['held'][day] for fid in present))
        reporting.append(len(present))

        # Only facilities with BOTH a value today and a history for this
        # day-of-year contribute, so the two lines always cover the same set.
        parts = [facility_reference[fid][day] for fid in present
                 if facility_reference[fid][day] is not None]
        reference.append(sum(parts) if len(parts) == len(present) and parts else None)

    facilities = sorted(
        ({'facility_id': fid,
          'name': entry['name'],
          'values': [round(entry['held'][d], 1) if d in entry['held'] else None for d in dates],
          'latest': entry['held'].get(dates[-1]),
          'reference_latest': facility_reference[fid][dates[-1]]}
         for fid, entry in by_facility.items()),
        key=lambda f: -(f['latest'] or 0),
    )

    absent = [f['name'] for f in facilities if f['latest'] is None]

    return {
        'dates': [d.isoformat() for d in dates],
        'totals': [round(v, 1) for v in totals],
        'reference': [round(v, 1) if v is not None else None for v in reference],
        'reporting': reporting,
        'facilities': facilities,
        'absent_latest': absent,
        'suspect': suspect,
        'start': dates[0],
        'end': dates[-1],
        'latest_total': totals[-1],
        'reference_latest': reference[-1],
        'years': len({d.year for d in dates}),
    }


# A holding may not move by more than this share of the facility's own
# usual inventory between reports. Half is deliberately generous: real
# seasonal swings take months, so anything approaching this is a data
# error rather than a fast withdrawal.
HOLDING_SWING_SHARE = 0.5
HOLDING_FLOOR_TJ = 200.0


def _drop_implausible_holdings(by_facility):
    """Remove holdings a facility could not physically have reached.

    Silver Springs reported 108,904 TJ on 23 August 2025 against roughly
    10,900 TJ on the days either side, while every other facility sat
    still — a misplaced digit, and the single most visible feature of the
    chart until it was caught.

    The threshold is a share of the facility's OWN median holding rather
    than a cross-check against its reported injections. An earlier version
    compared the change in inventory to the gas moved that day, which
    sounds more physical but dropped 570 perfectly good observations:
    Moomba reports zero movement on days it merely drifts, so any drift at
    all looked infinite against a zero denominator. Comparing a facility
    to its own scale is blunter and right.

    Mutates `by_facility`, removing the offending day so it is treated as
    not reported — the like-for-like logic then excludes it from both the
    actual and the reference line. Returns the list of what was dropped,
    because a discarded observation must be reported, never disappeared.
    """
    dropped = []
    for entry in by_facility.values():
        days = sorted(entry['held'])
        if not days:
            continue

        typical = _median(list(entry['held'].values())) or 0.0
        allowed = max(typical * HOLDING_SWING_SHARE, HOLDING_FLOOR_TJ)

        # `last_good` rather than the previous day, so one bad value does
        # not also condemn the day after it for returning to normal.
        last_good = entry['held'][days[0]]
        suspect = []
        for day in days[1:]:
            current = entry['held'][day]
            if abs(current - last_good) > allowed:
                suspect.append(day)
                continue
            last_good = current

        for day in suspect:
            dropped.append({'name': entry['name'], 'gas_date': day,
                            'held_tj': entry['held'][day]})
            del entry['held'][day]

    dropped.sort(key=lambda record: record['gas_date'])
    return dropped


def _median(values):
    ordered = sorted(values)
    count = len(ordered)
    if not count:
        return None
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def flow_network(gas_date=None, minimum_tj=5.0):
    """Where gas moved between locations on one gas day.

    The answer to "how do the parts interact" without a map. Nodes are
    locations, edges are pipelines, edge weight is terajoules per day
    (AEMO's own convention: a gas day's quantity is reported this way
    throughout the Bulletin Board, matching the "TJ/day" already used for
    rated capacity elsewhere in this app).

    **The edges are an inference and the page must say so.** The Bulletin
    Board reports, per pipeline, what it received at each location and
    what it delivered at each location. It does NOT report which receipt
    fed which delivery. Where a pipeline has one receipt and one delivery
    the edge is a measurement; where it has several, the flow is allocated
    across deliveries in proportion to their size. That is the standard
    assumption and it is usually right, but it is an assumption, and a
    pipeline receiving at both ends — the South West Queensland Pipeline
    takes gas at Wallumbilla and Moomba simultaneously — is exactly where
    it is weakest.

    Self-loops are dropped: a pipeline reporting a receipt and a delivery
    at the same location has moved gas within a region, which the node
    already accounts for and an edge would only clutter.

    **Node value is NOT derived from the edges.** `supply_tj` comes from
    production and storage withdrawal at that location; `demand_tj` from
    LNG export, generation, large industrial and distribution facilities
    there. Both are separately published quantities from a different set
    of facilities than the pipelines that create the edges, so a node's
    net position cannot be reconstructed by summing the flows touching it
    — the two measurements do not reconcile by construction, and a caller
    must not imply they do.

    **The LNG export edge is deliberately identified apart from the rest.**
    On 9 August 2026 it ran 3,827 TJ/day against a next-largest domestic
    flow of 472 TJ/day — roughly 8x. Scaling every edge off that one
    number would flatten the entire domestic network to hairlines, so
    `domestic_peak_tj` and `export_peak_tj` are returned separately and a
    caller must use the one that applies.

    **Opposing edges between the same two locations are netted.** Where
    the allocation above produces both A→B and B→A, only the larger
    survives, redrawn as A→B or B→A as appropriate, with `tj` equal to the
    difference and `gross_forward`/`gross_reverse` kept for the record.
    This is a fair simplification for one gas day's net movement between
    two points; both raw figures remain available to a tooltip rather
    than being discarded.
    """
    gas_date = gas_date or latest_gas_day()
    if gas_date is None:
        return None

    rows = (FlowObservation.objects
            .filter(gas_date=gas_date)
            .select_related('facility', 'location'))

    receipts = {}       # facility -> [(location_id, tj)]
    deliveries = {}
    node_supply = {}    # location_id -> production + storage withdrawal
    node_demand = {}    # location_id -> end use only
    node_names = {}
    export_locations = set()   # locations where an LNGEXPORT facility reports

    for row in rows:
        kind = row.facility.facility_type
        node_names[row.location_id] = row.location.name

        if kind == 'PIPE':
            taken = row.supply_tj + row.transfer_in_tj
            given = row.demand_tj + row.transfer_out_tj
            if taken:
                receipts.setdefault(row.facility_id, []).append((row.location_id, taken))
            if given:
                deliveries.setdefault(row.facility_id, []).append((row.location_id, given))
        if kind in SUPPLY_TYPES:
            node_supply[row.location_id] = node_supply.get(row.location_id, 0.0) + row.supply_tj
        if kind in END_USE_TYPES:
            node_demand[row.location_id] = node_demand.get(row.location_id, 0.0) + row.demand_tj
        if kind == 'LNGEXPORT':
            export_locations.add(row.location_id)

    facilities = {f.facility_id: f for f in
                  Facility.objects.filter(facility_id__in=set(receipts) | set(deliveries))}

    edges = {}
    inferred = 0
    for facility_id, taken in receipts.items():
        given = deliveries.get(facility_id)
        if not given:
            continue
        given_total = sum(q for _, q in given)
        if given_total <= 0:
            continue
        # Ambiguous only when there are several receipts AND several
        # deliveries. One receipt feeding several measured delivery points
        # is not a routing guess: all the gas came from the one place and
        # the deliveries are reported. Marking those as inferred dashed 42
        # of 44 edges and turned the caveat into wallpaper.
        multi = len(taken) > 1 and len(given) > 1
        for source, source_tj in taken:
            for target, target_tj in given:
                if source == target:
                    continue
                share = source_tj * (target_tj / given_total)
                if share < minimum_tj:
                    continue
                key = (source, target)
                edge = edges.setdefault(key, {
                    'source': source, 'target': target, 'tj': 0.0,
                    'pipelines': [], 'inferred': False,
                })
                edge['tj'] += share
                name = facilities[facility_id].short_name or facilities[facility_id].name
                if name not in edge['pipelines']:
                    edge['pipelines'].append(name)
                if multi:
                    edge['inferred'] = True
        if multi:
            inferred += 1

    edges = _net_opposing_edges(edges)

    used = {n for edge in edges.values() for n in (edge['source'], edge['target'])}
    used |= set(node_supply) | set(node_demand)

    nodes = []
    for location_id in used:
        if location_id not in LOCATION_LAYOUT:
            continue
        x, y, label = LOCATION_LAYOUT[location_id]
        supply = node_supply.get(location_id, 0.0)
        demand = node_demand.get(location_id, 0.0)
        net = supply - demand
        nodes.append({
            'id': location_id, 'label': label, 'x': x, 'y': y,
            'supply_tj': round(supply, 1), 'demand_tj': round(demand, 1),
            'net_tj': round(net, 1),
            'role': 'supply' if net > 0 else ('demand' if net < 0 else 'transit'),
        })

    placed = {n['id'] for n in nodes}
    drawn = []
    for edge in edges.values():
        if edge['source'] not in placed or edge['target'] not in placed:
            continue
        export = edge['target'] in export_locations or edge['source'] in export_locations
        drawn.append(dict(edge, tj=round(edge['tj'], 1), export=export))
    drawn.sort(key=lambda e: -e['tj'])

    domestic = [e for e in drawn if not e['export']]
    export = [e for e in drawn if e['export']]

    # Legend examples drawn FROM the day's own data rather than fixed
    # thresholds, so the legend always describes the chart it sits under.
    # Percentiles rather than min/median/max: an edge-case day with very
    # few flows could otherwise repeat the same value three times.
    #
    # The node legend excludes Regional QLD and Curtis Island — the same
    # two locations the domestic/export edge split already treats as
    # exceptional. Without that exclusion the 95th percentile lands on
    # Curtis Island's own size (roughly 3,800 TJ/day) and the legend jumps
    # from "45" to "3,830" with nothing between, which describes the one
    # export outlier rather than a typical domestic hub. Curtis Island's
    # actual size is still shown on the diagram itself, via its own node
    # and the LNG export annotation.
    export_endpoints = {n for edge in export for n in (edge['source'], edge['target'])}
    domestic_values = [e['tj'] for e in domestic]
    node_values = [abs(n['net_tj']) for n in nodes if n['net_tj'] and n['id'] not in export_endpoints]
    legend_flows = _legend_examples(domestic_values)
    legend_nodes = _legend_examples(node_values)

    return {
        'gas_date': gas_date,
        'nodes': sorted(nodes, key=lambda n: n['label']),
        'edges': drawn,
        'domestic_peak_tj': max((e['tj'] for e in domestic), default=0.0),
        'export_peak_tj': max((e['tj'] for e in export), default=0.0),
        'legend_flows': legend_flows,
        'legend_nodes': legend_nodes,
        'inferred_pipelines': inferred,
        'unplaced': sorted(node_names[i] for i in used - placed if i in node_names),
    }


def _percentile(values, p):
    """Linear-interpolated percentile, 0 <= p <= 1."""
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * p
    lower, upper = int(position), min(int(position) + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _legend_examples(values):
    """Three representative magnitudes from a real distribution.

    Rounded to the nearest 5 for a clean legend label, not to invent
    precision the source does not report.
    """
    if not values:
        return []
    examples = {round(_percentile(values, p) / 5) * 5 for p in (0.25, 0.60, 0.95)}
    return sorted(v for v in examples if v > 0)


def _net_opposing_edges(edges):
    """Collapse A→B and B→A into one edge carrying the net movement.

    Two directed flows between the same pair are a fair candidate for
    netting on a single gas day's total: what survives is which way gas
    moved on balance, and by how much. Both raw figures are kept as
    `gross_forward` (in the surviving direction) and `gross_reverse` (the
    smaller, opposing one) so a tooltip can show the full picture even
    though the resting diagram draws one line.
    """
    seen = set()
    netted = {}
    for key, edge in edges.items():
        if key in seen:
            continue
        source, target = key
        opposite_key = (target, source)
        opposite = edges.get(opposite_key)

        if opposite is None or opposite['tj'] <= edge['tj']:
            forward, reverse = edge, opposite
        else:
            forward, reverse = opposite, edge

        seen.add(key)
        seen.add(opposite_key)

        merged = dict(forward)
        merged['gross_forward'] = round(forward['tj'], 1)
        merged['gross_reverse'] = round(reverse['tj'], 1) if reverse else 0.0
        merged['tj'] = forward['tj'] - (reverse['tj'] if reverse else 0.0)
        if reverse:
            merged['pipelines'] = sorted(set(forward['pipelines']) | set(reverse['pipelines']))
            merged['inferred'] = forward['inferred'] or reverse['inferred']
        netted[(forward['source'], forward['target'])] = merged

    return netted


def location_state_regions(nodes):
    """Soft background regions grouping the diagram's nodes by state.

    A literal continent outline was tried and read as "a bit strange" — a
    shape that looked like a map but was not one. A grid of one square per
    state was tried next and lost the node-level detail (Wallumbilla,
    Moomba, Curtis Island by name) that made the diagram legible in the
    first place. This is the middle ground: keep every node, add a faint
    circle behind each state's own cluster of them for orientation.

    Computed from the nodes actually being drawn and `Location.state`
    rather than hand placed, so it can never drift out of sync with
    `LOCATION_LAYOUT` the way a separately hand-drawn outline could.
    """
    if not nodes:
        return []

    loc_state = dict(Location.objects.values_list('location_id', 'state'))
    by_state = {}
    for node in nodes:
        state = loc_state.get(node['id'])
        if not state:
            continue
        by_state.setdefault(state, []).append(node)

    regions = []
    for state, group in by_state.items():
        cx = sum(n['x'] for n in group) / len(group)
        cy = sum(n['y'] for n in group) / len(group)
        distances = sorted(((n['x'] - cx) ** 2 + (n['y'] - cy) ** 2) ** 0.5 for n in group)
        # The 80th-percentile distance rather than the true maximum: one
        # outlier location — Victoria's Longford is the furthest from its
        # own centroid — should not inflate the whole state's circle far
        # enough to swallow a neighbouring state. A soft orientation region
        # only needs to cover MOST of its nodes to read correctly; a node
        # poking slightly past the edge is a minor cost against a circle
        # that no longer overlaps SA.
        index = min(len(distances) - 1, int(len(distances) * 0.8))
        spread = distances[index]
        # A floor so a single-node state still reads as a region rather
        # than a dot, and padding so the glow reaches a little past its
        # covered nodes instead of clipping them exactly at the edge.
        radius = max(spread + 0.06, 0.10)
        regions.append({'state': state, 'cx': round(cx, 4), 'cy': round(cy, 4),
                        'r': round(radius, 4), 'nodes': len(group)})

    # Largest first, so a small state's glow is not fully buried under a
    # sprawling one when they overlap.
    return sorted(regions, key=lambda r: -r['r'])


SEASON_WINDOW_DAYS = 7


def seasonal_months(gas_date, window_days=SEASON_WINDOW_DAYS):
    """Calendar months a seasonal comparison can touch.

    The percentile only ever looks at days near the same point in the
    year, so pulling eight years of every series to answer it is waste:
    filtering to the two or three relevant months in SQL cut the page from
    three seconds to well under one. The window is widened by a day at
    each end so a month boundary cannot clip the comparison.
    """
    months = set()
    for offset in range(-window_days - 1, window_days + 2):
        months.add((gas_date + timedelta(days=offset)).month)
    return sorted(months)


def _tile(key, label, series, gas_date, unit, note, invert=False, headline=False):
    """One headline figure with its history and its recent movement.

    Carries three things because a level alone answers nothing: what it is,
    where it sits against the same week in other years, and which way it
    has moved in the last week. `invert` marks a measure where low is the
    notable direction — storage running out is news, storage full is not.

    `headline` marks the ONE tile the page renders as a dark, inverted
    card rather than a light one — a deliberate visual echo of
    ChargeTrace's stat block, where the total the other cards are
    components of gets the same treatment. Nothing here sums to LNG
    export the way ChargeTrace's other cards sum to its headline dollar
    figure, but it is the thesis's central number, so it earns the same
    visual weight for the same reason: one glance should say what this
    page is fundamentally about.
    """
    value = series.get(gas_date)
    if value is None:
        return None

    week_ago = series.get(gas_date - timedelta(days=7))
    change = (value - week_ago) if week_ago is not None else None
    change_pct = (change / week_ago * 100) if week_ago else None

    return {
        'key': key, 'label': label, 'value': value, 'unit': unit, 'note': note,
        'percentile': seasonal_percentile(series, gas_date),
        'change': change, 'change_pct': change_pct, 'invert': invert, 'headline': headline,
        # The arrow carries the sign, so the magnitude is rendered bare.
        # "▼ -682" reads as a double negative.
        'change_abs': abs(change) if change is not None else None,
        'change_pct_abs': abs(change_pct) if change_pct is not None else None,
        'direction': 'up' if (change or 0) > 0 else ('down' if (change or 0) < 0 else 'flat'),
    }


def system_headline(gas_date=None):
    """The state of the system in a handful of numbers, each in context.

    Every tile carries a percentile against the same season in other
    years, because a level without history is not a finding. The page
    opened for two revisions with a facility count and a refresh margin,
    which told a reader nothing about gas.
    """
    gas_date = gas_date or latest_gas_day()
    if gas_date is None:
        return None

    tiles = []
    # Only the weeks around this point in the year matter, plus the week
    # before for the change figure.
    months = seasonal_months(gas_date)
    recent = gas_date - timedelta(days=8)

    # Storage, like for like against the same week in other years.
    storage_rows = (FlowObservation.objects
                    .filter(facility__facility_type='STOR', held_in_storage_tj__isnull=False)
                    .filter(Q(gas_date__month__in=months) | Q(gas_date__gte=recent))
                    .values('gas_date', 'facility_id', 'facility__name',
                            'held_in_storage_tj', 'demand_tj', 'supply_tj'))
    by_facility = {}
    for row in storage_rows:
        entry = by_facility.setdefault(row['facility_id'], {
            'name': row['facility__name'], 'held': {}, 'moved': {}})
        entry['held'][row['gas_date']] = row['held_in_storage_tj']
        entry['moved'][row['gas_date']] = row['demand_tj'] + row['supply_tj']
    _drop_implausible_holdings(by_facility)

    reporting_today = [fid for fid, entry in by_facility.items() if gas_date in entry['held']]
    if reporting_today:
        # Restrict the whole history to today's reporting set, or the
        # percentile measures coverage changes rather than inventory.
        totals = {}
        for day in {d for fid in reporting_today for d in by_facility[fid]['held']}:
            if all(day in by_facility[fid]['held'] for fid in reporting_today):
                totals[day] = sum(by_facility[fid]['held'][day] for fid in reporting_today)
        tiles.append(_tile('storage', 'Gas in storage', totals, gas_date, 'TJ',
                           f'{len(reporting_today)} facilities reporting', invert=True))

    # Constraint: pipelines flagged, against the same week in other years.
    flag_rows = (LinepackAdequacy.objects
                 .filter(flag__in=LCA_CONSTRAINED_FLAGS)
                 .filter(Q(gas_date__month__in=months) | Q(gas_date__gte=recent))
                 .values('gas_date')
                 .annotate(n=Count('pk')))
    flagged = {row['gas_date']: float(row['n']) for row in flag_rows}
    assessed_today = LinepackAdequacy.objects.filter(gas_date=gas_date).count()
    if assessed_today:
        flagged.setdefault(gas_date, 0.0)
        tiles.append(_tile('constraint', 'Pipelines flagged', flagged, gas_date,
                           f'of {assessed_today}', 'linepack adequacy, AEMO'))

    # LNG export draw, the dominant demand and the international link.
    lng_rows = (FlowObservation.objects
                .filter(facility__facility_type='LNGEXPORT')
                .filter(Q(gas_date__month__in=months) | Q(gas_date__gte=recent))
                .values('gas_date').annotate(tj=Sum('demand_tj')))
    lng = {row['gas_date']: row['tj'] or 0.0 for row in lng_rows}
    tiles.append(_tile('lng', 'LNG export draw', lng, gas_date, 'TJ',
                       'three Curtis Island trains', headline=True))

    # Gas for power: small in volume, decisive for the electricity price.
    gpg_rows = (FlowObservation.objects
                .filter(facility__facility_type='BBGPG')
                .filter(Q(gas_date__month__in=months) | Q(gas_date__gte=recent))
                .values('gas_date').annotate(tj=Sum('demand_tj')))
    gpg = {row['gas_date']: row['tj'] or 0.0 for row in gpg_rows}
    tiles.append(_tile('gpg', 'Gas for power', gpg, gas_date, 'TJ',
                       'sets a floor under NEM prices'))

    return {'gas_date': gas_date, 'tiles': [t for t in tiles if t]}


def state_balance(gas_date=None):
    """Supply, demand and net position by state for one gas day.

    The highest information-per-pixel view of the system: it says in six
    rows that New South Wales produces nothing and imports everything,
    while Queensland and Victoria carry the supply. AEMO's own Bulletin
    Board dashboard leads with this table for that reason.

    Supply is production plus storage withdrawal.

    Demand is reported TWO ways, side by side and never added, because
    neither alone is a state's consumption:

    * `end_use_tj` counts facilities that report directly — LNG trains,
      generators, large industrials. It is exact where it applies and
      **blind where consumption arrives through a transmission system**.
      Victoria returns 27 TJ this way against a real load in the hundreds,
      because Melbourne is served by the Victorian Transmission System, a
      pipeline. AEMO's own Bulletin Board dashboard carries the same
      caveat for Victoria, so this is a property of the data rather than a
      mistake in the arithmetic.
    * `delivered_tj` counts what pipelines delivered into the state, which
      captures the transmission-served load but double counts wherever a
      pipeline feeds a facility that also reports — the WGP into QCLNG
      being the largest instance.

    There is deliberately no net column. A single balance would have to
    pick one of the two and would be wrong for half the states.
    """
    gas_date = gas_date or latest_gas_day()
    if gas_date is None:
        return None

    rows = (FlowObservation.objects
            .filter(gas_date=gas_date)
            .values('state', 'facility__facility_type')
            .annotate(demand=Sum('demand_tj'), supply=Sum('supply_tj')))

    by_state = {}
    for row in rows:
        state = row['state'] or 'Unknown'
        entry = by_state.setdefault(state, {
            'state': state, 'supply_tj': 0.0, 'end_use_tj': 0.0, 'delivered_tj': 0.0,
        })
        kind = row['facility__facility_type']
        if kind in SUPPLY_TYPES:
            entry['supply_tj'] += row['supply'] or 0.0
        if kind in END_USE_TYPES:
            entry['end_use_tj'] += row['demand'] or 0.0
        if kind == 'PIPE':
            entry['delivered_tj'] += row['demand'] or 0.0

    ordered = sorted(by_state.values(), key=lambda e: -e['supply_tj'])
    return {
        'gas_date': gas_date,
        'rows': ordered,
        'supply_tj': sum(e['supply_tj'] for e in ordered),
        'end_use_tj': sum(e['end_use_tj'] for e in ordered),
        'delivered_tj': sum(e['delivered_tj'] for e in ordered),
    }


def percentile_of(value, history):
    """Where `value` sits within `history`, as a 0-100 percentile.

    The point of holding eight years of data. "Storage is in the 4th
    percentile for early August" is a claim a reader can act on;
    "77% of median" is arithmetic they have to interpret themselves.
    """
    usable = [v for v in history if v is not None]
    if not usable or value is None:
        return None
    below = sum(1 for v in usable if v < value)
    equal = sum(1 for v in usable if v == value)
    return (below + equal / 2) / len(usable) * 100


def seasonal_percentile(series_by_date, gas_date, window_days=7):
    """Percentile of one gas day against the same season in other years.

    Compared against a window around the same day-of-year rather than the
    whole record, because an August level judged against every day since
    2018 would mostly be measuring the seasonal cycle rather than whether
    this August is unusual.
    """
    value = series_by_date.get(gas_date)
    if value is None:
        return None

    history = []
    for day, other in series_by_date.items():
        if day.year == gas_date.year:
            continue
        # Distance in days from the same calendar position, ignoring year.
        try:
            same_position = date(day.year, gas_date.month, gas_date.day)
        except ValueError:      # 29 February in a non-leap year
            continue
        if abs((day - same_position).days) <= window_days:
            history.append(other)

    return percentile_of(value, history)


def system_balance_series(days=90, end=None):
    """Supply against end-use demand over time, for the whole east coast.

    The one chart that shows the system as a system. Supply is production
    plus storage withdrawal; demand is end use only, so the two are on the
    same footing and the gap between them is real rather than an artefact
    of counting pipeline deliveries twice.

    Clamped to the 2023 expansion for the same reason the composition
    chart is: before it there are no end-use facilities at all, so the
    demand line would start from nothing and invent a story.
    """
    end = end or latest_gas_day()
    if end is None:
        return None

    requested_start = end - timedelta(days=days - 1)
    start = max(requested_start, GBB_EXPANSION_DATE)

    rows = (FlowObservation.objects
            .filter(gas_date__gte=start, gas_date__lte=end)
            .values('gas_date', 'facility__facility_type')
            .annotate(demand=Sum('demand_tj'), supply=Sum('supply_tj'))
            .order_by('gas_date'))

    supply, demand, export = {}, {}, {}
    for row in rows:
        kind = row['facility__facility_type']
        day = row['gas_date']
        if kind in SUPPLY_TYPES:
            supply[day] = supply.get(day, 0.0) + (row['supply'] or 0.0)
        if kind in END_USE_TYPES:
            demand[day] = demand.get(day, 0.0) + (row['demand'] or 0.0)
        if kind == 'LNGEXPORT':
            export[day] = export.get(day, 0.0) + (row['demand'] or 0.0)

    dates = sorted(set(supply) | set(demand))
    if not dates:
        return None

    domestic = [round(demand.get(d, 0.0) - export.get(d, 0.0), 1) for d in dates]

    return {
        'dates': [d.isoformat() for d in dates],
        'supply': [round(supply.get(d, 0.0), 1) for d in dates],
        'demand': [round(demand.get(d, 0.0), 1) for d in dates],
        'export': [round(export.get(d, 0.0), 1) for d in dates],
        'domestic': domestic,
        'start': dates[0],
        'end': dates[-1],
        'truncated': requested_start < GBB_EXPANSION_DATE,
        'expansion_date': GBB_EXPANSION_DATE,
        # The headline ratio the thesis rests on, averaged over the window.
        'export_share': (sum(export.get(d, 0.0) for d in dates) /
                         sum(demand.get(d, 0.0) for d in dates) * 100)
                        if sum(demand.get(d, 0.0) for d in dates) else None,
        'latest_supply': supply.get(dates[-1]),
        'latest_demand': demand.get(dates[-1]),
    }


def demand_composition(days=365, end=None):
    """End-use demand by consumer type, one point per gas day.

    Starts no earlier than the 15 March 2023 Bulletin Board expansion,
    whatever `days` asks for. Before that date the record holds no end-use
    facilities at all, so a chart crossing the boundary would show demand
    climbing out of nothing — a reporting change drawn as a market event.
    The returned `truncated` flag lets the page say so.
    """
    end = end or latest_gas_day()
    if end is None:
        return None

    requested_start = end - timedelta(days=days - 1)
    start = max(requested_start, GBB_EXPANSION_DATE)

    rows = (FlowObservation.objects
            .filter(gas_date__gte=start, gas_date__lte=end,
                    facility__facility_type__in=END_USE_TYPES)
            .values('gas_date', 'facility__facility_type')
            .annotate(tj=Sum('demand_tj'))
            .order_by('gas_date'))

    by_day = {}
    for row in rows:
        day = by_day.setdefault(row['gas_date'], {})
        day[row['facility__facility_type']] = row['tj'] or 0.0

    dates = sorted(by_day)
    # A fixed series order so the stack never reshuffles between renders,
    # largest at the bottom because that is the stable band.
    order = ['LNGEXPORT', 'BBLARGE', 'BBGPG', 'BDIST']
    present = [code for code in order if any(code in day for day in by_day.values())]

    return {
        'dates': [d.isoformat() for d in dates],
        'series': [
            {'code': code,
             'label': FACILITY_TYPES.get(code, code),
             'values': [round(by_day[d].get(code, 0.0), 1) for d in dates]}
            for code in present
        ],
        'start': start,
        'end': end,
        'truncated': requested_start < GBB_EXPANSION_DATE,
        'expansion_date': GBB_EXPANSION_DATE,
    }


def constraint_history(days=180, end=None):
    """Linepack adequacy per pipeline per gas day, for the strip chart.

    Only pipelines that were flagged at least once in the window are
    returned. Rendering 53 rows of unbroken green to surface two amber ones
    buries the signal in its own background.
    """
    end = end or (timezone.localdate() + timedelta(days=3))
    start = end - timedelta(days=days - 1)

    flags = (LinepackAdequacy.objects
             .filter(gas_date__gte=start, gas_date__lte=end)
             .select_related('facility')
             .order_by('gas_date'))

    dates = set()
    by_facility = {}
    ever_constrained = set()

    for flag in flags:
        dates.add(flag.gas_date)
        row = by_facility.setdefault(flag.facility_id, {'name': flag.facility.name, 'flags': {}})
        row['flags'][flag.gas_date] = flag.flag
        if flag.flag in LCA_CONSTRAINED_FLAGS:
            ever_constrained.add(flag.facility_id)

    if not dates:
        return None

    ordered_dates = sorted(dates)
    rows = []
    for facility_id in ever_constrained:
        entry = by_facility[facility_id]
        cells = [entry['flags'].get(d, '') for d in ordered_dates]
        assessed = sum(1 for c in cells if c)
        constrained = sum(1 for c in cells if c in LCA_CONSTRAINED_FLAGS)
        rows.append({
            'name': entry['name'],
            'cells': cells,
            'constrained_days': constrained,
            # A pipeline flagged on most of the days it was assessed is
            # structurally tight, not having an event. Presenting the two
            # identically turns a permanent condition into a false alarm,
            # which is how a monitor loses its reader.
            'chronic': assessed > 0 and constrained / assessed >= CHRONIC_THRESHOLD,
        })
    rows.sort(key=lambda r: (-r['constrained_days'], r['name']))

    totals = []
    for index, day in enumerate(ordered_dates):
        counts = {}
        for entry in by_facility.values():
            flag = entry['flags'].get(day)
            if flag:
                counts[flag] = counts.get(flag, 0) + 1
        totals.append({'date': day.isoformat(),
                       'constrained': sum(counts.get(f, 0) for f in LCA_CONSTRAINED_FLAGS),
                       'assessed': sum(counts.values())})

    # Chronic and episodic are separated rather than sorted together. Two
    # permanently amber pipelines rendered as solid slabs beside two
    # single-day events reduced the events to hairlines: the loudest thing
    # on the chart was the thing that never changes, which is exactly
    # backwards for a monitor.
    chronic = [row for row in rows if row['chronic']]
    episodic = [row for row in rows if not row['chronic']]

    return {
        'dates': [d.isoformat() for d in ordered_dates],
        'rows': rows,
        'chronic': chronic,
        'episodic': episodic,
        'totals': totals,
        'pipelines_assessed': len(by_facility),
        'pipelines_flagged': len(rows),
        'start': ordered_dates[0],
        'end': ordered_dates[-1],
    }


def constraint_outlook(today=None, trailing_days=0):
    """Linepack adequacy around today: recent observed days plus the forward outlook.

    The system-wide FORWARD outlook is SHORT: three gas days on
    10 August 2026, when 53 pipelines were assessed for each of them.
    Beyond that a single NT pipeline publishes a year of its own outlooks
    — 321 further days — and listing them produced a table of 325 rows,
    322 of which said one pipeline was green. So forward days are kept
    only while a system-wide assessment exists, meaning at least half as
    many pipelines as the best-covered day; a later well-covered day
    reappearing after a gap would misrepresent the outlook as longer than
    it is, so this is a horizon that stops at the first collapse, not a
    filter that skips over one.

    `trailing_days` adds recent OBSERVED days before today, which are
    real historical flags rather than a forecast and are never subject to
    the threshold cutoff above — three forward rows floating with nothing
    behind them read as thin on their own. Each returned day carries
    `observed` so the caller can label which is which. The default of 0
    reproduces the forward-only behaviour exactly.
    """
    today = today or timezone.localdate()
    window_start = today - timedelta(days=trailing_days)
    flags = (LinepackAdequacy.objects
             .filter(gas_date__gte=window_start)
             .select_related('facility')
             .order_by('gas_date', 'facility__name'))

    by_day = {}
    for flag in flags:
        day = by_day.setdefault(flag.gas_date, {'gas_date': flag.gas_date, 'counts': {},
                                                'constrained': [], 'assessed': 0,
                                                'observed': flag.gas_date < today})
        day['counts'][flag.flag] = day['counts'].get(flag.flag, 0) + 1
        day['assessed'] += 1
        if flag.flag in LCA_CONSTRAINED_FLAGS:
            day['constrained'].append(flag)

    if not by_day:
        return []

    forward_days = [d for d in by_day.values() if not d['observed']]
    threshold = max((d['assessed'] for d in forward_days), default=0) / 2

    horizon = []
    for day in sorted(by_day.values(), key=lambda d: d['gas_date']):
        if not day['observed'] and day['assessed'] < threshold:
            break
        horizon.append(day)
    return horizon
