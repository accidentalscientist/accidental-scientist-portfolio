"""Data acquisition for the gas monitor's static system model.

One source, public and free of API keys: the AEMO Gas Bulletin Board's
report directory at nemweb.com.au/Reports/Current/GBB/.

The reports here are the REFERENCE set — what the system is made of rather
than what flowed through it. They are snapshots of current state, so
re-fetching replaces what is stored rather than extending a history. The
newer-wins guard that the flow tables will need (comparing the incoming
`LastUpdated` against the stored one before overwriting) does not apply to
a snapshot, and is deliberately not implemented here.

Everything uses the standard library. Adding `requests` for a handful of
HTTP GETs would reverse a deliberate dependency cull for no benefit.
"""

import csv
import io
import urllib.request
import zipfile
from datetime import datetime

from .constants import (
    AEST, ARCHIVE_REPORTS, GBB_BASE, HTTP_TIMEOUT, REFERENCE_REPORTS,
    TIME_SERIES_REPORTS, USER_AGENT,
)

ALL_REPORTS = {**REFERENCE_REPORTS, **TIME_SERIES_REPORTS}


class IngestError(Exception):
    """Raised when a source cannot be read or does not look like what we expect."""


# ── Timestamps ────────────────────────────────────────────────────────
# The Bulletin Board is not internally consistent about date format. The
# same directory serves '2023/05/25', '2019/08/29 16:17:08' and
# '29 Aug 2019 00:00:00', sometimes in different columns of one file. A
# tolerant parser is the honest response; guessing one format would drop
# rows silently, which is the failure mode this project is least willing
# to accept.
GBB_DATETIME_FORMATS = (
    '%Y/%m/%d %H:%M:%S',
    '%Y/%m/%d %H:%M',
    '%Y/%m/%d',
    '%d %b %Y %H:%M:%S',
    '%d %b %Y',
    '%d-%m-%Y',
    '%Y-%m-%d',
)


def parse_gbb_datetime(raw):
    """Parse any of the Bulletin Board's date formats into an aware datetime."""
    text = (raw or '').strip()
    if not text:
        return None
    for fmt in GBB_DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=AEST)
        except ValueError:
            continue
    return None


def parse_gbb_date(raw):
    """Same, reduced to a date. Returns None rather than raising."""
    parsed = parse_gbb_datetime(raw)
    return parsed.date() if parsed else None


def _to_int(raw):
    try:
        return int(float((raw or '').strip()))
    except (TypeError, ValueError):
        return None


def _to_float(raw):
    try:
        return float((raw or '').strip())
    except (TypeError, ValueError):
        return None


# ── HTTP ──────────────────────────────────────────────────────────────

def _fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return response.read()
    except Exception as exc:  # urllib raises a wide family; the caller needs the message
        raise IngestError(f'could not fetch {url}: {exc}') from exc


def fetch_report(key):
    """Download one named report as text.

    `key` is a member of ALL_REPORTS, not a URL, so a typo fails here
    rather than fetching something unexpected.
    """
    try:
        filename = ALL_REPORTS[key]
    except KeyError:
        raise IngestError(f'unknown report {key!r}; expected one of {", ".join(sorted(ALL_REPORTS))}')
    return _fetch(GBB_BASE + filename).decode('utf-8-sig', errors='replace')


def unzip_single(payload, label='archive'):
    """Return the text of a one-member zip.

    The Bulletin Board archives each hold exactly one CSV. Asserting that
    rather than picking the first member means a source that starts
    shipping several fails loudly instead of silently ingesting whichever
    one happened to be first.
    """
    try:
        bundle = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise IngestError(f'{label}: not a readable zip ({exc})') from exc

    members = [name for name in bundle.namelist() if not name.endswith('/')]
    if len(members) != 1:
        raise IngestError(f'{label}: expected one file in the zip, found {len(members)}: '
                          f'{", ".join(members[:5])}')
    return bundle.read(members[0]).decode('utf-8-sig', errors='replace')


def fetch_archive(key):
    """Download and unzip one full-history archive.

    Tens of megabytes uncompressed, which is why this is a command-line
    path and never runs behind an admin Save button.
    """
    try:
        filename = ARCHIVE_REPORTS[key]
    except KeyError:
        raise IngestError(f'no archive for {key!r}; archives exist for '
                          f'{", ".join(sorted(ARCHIVE_REPORTS))}')
    return unzip_single(_fetch(GBB_BASE + filename), label=filename)


def iter_chunks(rows, size):
    """Yield successive slices, so a backfill never holds one giant batch."""
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


# ── Parsing ───────────────────────────────────────────────────────────

def _reader(text, required, report_name):
    """A DictReader with the header checked before any row is trusted.

    Column names vary in case between reports (`facilityname` in the
    nameplate file, `FacilityName` almost everywhere else), so every
    header is lowercased and callers address columns in lower case.
    """
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise IngestError(f'{report_name}: file is empty')
    reader.fieldnames = [(name or '').strip().lower() for name in reader.fieldnames]
    missing = {c.lower() for c in required} - set(reader.fieldnames)
    if missing:
        raise IngestError(f'{report_name}: missing columns: {", ".join(sorted(missing))}')
    return reader


def _finish(rows, skipped, issues):
    return rows, {'parsed': len(rows), 'skipped': skipped, 'issues': issues}


def _note(issues, line_no, message):
    if len(issues) < 10:
        issues.append(f'line {line_no}: {message}')


def parse_basins(text):
    reader = _reader(text, ['BasinId', 'BasinName'], 'basins')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        basin_id = _to_int(row.get('basinid'))
        name = (row.get('basinname') or '').strip()
        if basin_id is None or not name:
            skipped += 1
            _note(issues, line_no, 'unreadable basin id or name')
            continue
        rows.append({'basin_id': basin_id, 'name': name})
    return _finish(rows, skipped, issues)


def parse_locations(text):
    reader = _reader(text, ['LocationName', 'LocationId'], 'locations')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        location_id = _to_int(row.get('locationid'))
        name = (row.get('locationname') or '').strip()
        if location_id is None or not name:
            skipped += 1
            _note(issues, line_no, 'unreadable location id or name')
            continue
        rows.append({
            'location_id': location_id,
            'name': name,
            'location_type': (row.get('locationtype') or '').strip(),
            'state': (row.get('state') or '').strip(),
            'description': (row.get('description') or '').strip(),
            'source_last_updated': parse_gbb_datetime(row.get('lastupdated')),
        })
    return _finish(rows, skipped, issues)


def parse_facilities(text):
    reader = _reader(text, ['FacilityName', 'FacilityId', 'FacilityType'], 'facilities')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        facility_id = _to_int(row.get('facilityid'))
        name = (row.get('facilityname') or '').strip()
        facility_type = (row.get('facilitytype') or '').strip()
        if facility_id is None or not name or not facility_type:
            skipped += 1
            _note(issues, line_no, 'unreadable facility id, name or type')
            continue
        rows.append({
            'facility_id': facility_id,
            'name': name,
            'short_name': (row.get('facilityshortname') or '').strip(),
            'facility_type': facility_type,
            'type_description': (row.get('facilitytypedescription') or '').strip(),
            'operating_state': (row.get('operatingstate') or '').strip(),
            'operating_state_date': parse_gbb_date(row.get('operatingstatedate')),
            'operator_name': (row.get('operatorname') or '').strip(),
            'operator_id': _to_int(row.get('operatorid')),
            'source_last_updated': parse_gbb_datetime(row.get('lastupdated')),
        })
    return _finish(rows, skipped, issues)


def parse_connection_points(text):
    reader = _reader(text, ['ConnectionPointId', 'FacilityId', 'ConnectionPointName'],
                     'connection points')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        cp_id = _to_int(row.get('connectionpointid'))
        facility_id = _to_int(row.get('facilityid'))
        if cp_id is None or facility_id is None:
            skipped += 1
            _note(issues, line_no, 'unreadable connection point or facility id')
            continue
        # A location id of -1 is the source's way of saying "not applicable",
        # not a real location. Storing it would create a dangling reference.
        location_id = _to_int(row.get('locationid'))
        if location_id is not None and location_id < 0:
            location_id = None
        rows.append({
            'connection_point_id': cp_id,
            'facility_id': facility_id,
            'location_id': location_id,
            'name': (row.get('connectionpointname') or '').strip(),
            'flow_direction': (row.get('flowdirection') or '').strip(),
            'node_id': _to_int(row.get('nodeid')),
            'state_name': (row.get('statename') or '').strip(),
            'source_last_updated': parse_gbb_datetime(row.get('lastupdated')),
        })
    return _finish(rows, skipped, issues)


def parse_demand_zones(text):
    """Map connection points to demand zones.

    A second pass over an already-ingested connection point, not a table of
    its own: the mapping is published separately but describes the same
    object. Rows for connection points we do not hold are reported rather
    than inserted, because a mapping without its point is a signal that the
    registry needs refreshing first.
    """
    reader = _reader(text, ['ConnectionPointId', 'DemandZone'], 'demand zones')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        cp_id = _to_int(row.get('connectionpointid'))
        zone = (row.get('demandzone') or '').strip()
        if cp_id is None or not zone:
            skipped += 1
            _note(issues, line_no, 'unreadable connection point id or demand zone')
            continue
        rows.append({'connection_point_id': cp_id, 'demand_zone': zone})
    return _finish(rows, skipped, issues)


def parse_linepack_zones(text):
    reader = _reader(text, ['Operator', 'LinepackZone'], 'linepack zones')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        code = (row.get('linepackzone') or '').strip()
        if not code:
            skipped += 1
            _note(issues, line_no, 'missing linepack zone code')
            continue
        rows.append({
            'code': code,
            'operator': (row.get('operator') or '').strip(),
            'description': (row.get('linepackzonedescription') or '').strip(),
        })
    return _finish(rows, skipped, issues)


def parse_nameplate(text):
    """Rated capacity per directed leg.

    Note the lower-case column names: this report alone publishes
    `facilityname` and `capacityquantity` rather than the camel case used
    elsewhere, which is why `_reader` normalises the header.
    """
    reader = _reader(text, ['facilityid', 'capacitytype', 'capacityquantity', 'effectivedate'],
                     'nameplate ratings')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        facility_id = _to_int(row.get('facilityid'))
        capacity = _to_float(row.get('capacityquantity'))
        effective = parse_gbb_date(row.get('effectivedate'))
        capacity_type = (row.get('capacitytype') or '').strip()
        if facility_id is None or capacity is None or effective is None or not capacity_type:
            skipped += 1
            _note(issues, line_no, 'unreadable facility, capacity, type or effective date')
            continue
        rows.append({
            'facility_id': facility_id,
            'capacity_type': capacity_type,
            'flow_direction': (row.get('flowdirection') or '').strip(),
            'receipt_location_id': _to_int(row.get('receiptlocation')),
            'receipt_location_name': (row.get('receiptlocationname') or '').strip(),
            'delivery_location_id': _to_int(row.get('deliverylocation')),
            'delivery_location_name': (row.get('deliverylocationname') or '').strip(),
            'capacity_tj': capacity,
            'effective_date': effective,
            'capacity_description': (row.get('capacitydescription') or '').strip(),
            'description': (row.get('description') or '').strip(),
            'source_last_updated': parse_gbb_datetime(row.get('lastupdated')),
        })
    return _finish(rows, skipped, issues)


# ── Time series ───────────────────────────────────────────────────────

def _quantity(raw):
    """A reported quantity in TJ.

    Blank means "does not apply", which for a flow column means zero: the
    facility reported, it just did not move gas that way. Storage holdings
    are handled separately by `_optional_quantity`, because there blank
    means "this facility does not store gas" and zero would be a lie.
    """
    value = _to_float(raw)
    return 0.0 if value is None else value


def _optional_quantity(raw):
    return _to_float(raw)


def parse_flows(text):
    """Actual flows and storage, one row per facility per location per gas day."""
    reader = _reader(text, ['GasDate', 'FacilityId', 'LocationId'], 'flows')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        gas_date = parse_gbb_date(row.get('gasdate'))
        facility_id = _to_int(row.get('facilityid'))
        location_id = _to_int(row.get('locationid'))
        if gas_date is None or facility_id is None or location_id is None:
            skipped += 1
            _note(issues, line_no, 'unreadable gas date, facility or location')
            continue
        rows.append({
            'gas_date': gas_date,
            'facility_id': facility_id,
            'location_id': location_id,
            'demand_tj': _quantity(row.get('demand')),
            'supply_tj': _quantity(row.get('supply')),
            'transfer_in_tj': _quantity(row.get('transferin')),
            'transfer_out_tj': _quantity(row.get('transferout')),
            'held_in_storage_tj': _optional_quantity(row.get('heldinstorage')),
            'cushion_gas_tj': _optional_quantity(row.get('cushiongasstorage')),
            'state': (row.get('state') or '').strip(),
            'source_last_updated': parse_gbb_datetime(row.get('lastupdated')),
        })
    return _finish(rows, skipped, issues)


def parse_forecasts(text):
    """Nominations and forecasts for the next seven gas days.

    The source spells the column `Gasdate` here and `GasDate` in the
    actuals file. `_reader` lower-cases the header, which is the only
    reason the same field name works for both.
    """
    reader = _reader(text, ['Gasdate', 'FacilityId', 'LocationId'], 'forecasts')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        gas_date = parse_gbb_date(row.get('gasdate'))
        facility_id = _to_int(row.get('facilityid'))
        location_id = _to_int(row.get('locationid'))
        if gas_date is None or facility_id is None or location_id is None:
            skipped += 1
            _note(issues, line_no, 'unreadable gas date, facility or location')
            continue
        rows.append({
            'gas_date': gas_date,
            'facility_id': facility_id,
            'location_id': location_id,
            'demand_tj': _quantity(row.get('demand')),
            'supply_tj': _quantity(row.get('supply')),
            'transfer_in_tj': _quantity(row.get('transferin')),
            'transfer_out_tj': _quantity(row.get('transferout')),
            'state': (row.get('state') or '').strip(),
            'source_last_updated': parse_gbb_datetime(row.get('lastupdated')),
        })
    return _finish(rows, skipped, issues)


def parse_linepack_adequacy(text):
    """Forward linepack adequacy flags, one per pipeline per gas day.

    `GasDate` carries a time here (15:15) that is the assessment moment,
    not part of the gas day's identity. Reducing it to a date is what keeps
    one flag per pipeline per day; keeping the time would multiply rows
    every time AEMO reassessed.
    """
    reader = _reader(text, ['FacilityId', 'GasDate', 'Flag'], 'linepack adequacy')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        gas_date = parse_gbb_date(row.get('gasdate'))
        facility_id = _to_int(row.get('facilityid'))
        flag = (row.get('flag') or '').strip().upper()
        if gas_date is None or facility_id is None or not flag:
            skipped += 1
            _note(issues, line_no, 'unreadable gas date, facility or flag')
            continue
        rows.append({
            'gas_date': gas_date,
            'facility_id': facility_id,
            'flag': flag,
            'description': (row.get('description') or '').strip(),
            'source_last_updated': parse_gbb_datetime(row.get('lastupdated')),
        })
    return _finish(rows, skipped, issues)


def parse_missing(text):
    """Facilities AEMO records as not having submitted for a gas day."""
    reader = _reader(text, ['GasDate', 'FacilityId'], 'missing submissions')
    rows, skipped, issues = [], 0, []
    for line_no, row in enumerate(reader, start=2):
        gas_date = parse_gbb_date(row.get('gasdate'))
        facility_id = _to_int(row.get('facilityid'))
        if gas_date is None or facility_id is None:
            skipped += 1
            _note(issues, line_no, 'unreadable gas date or facility')
            continue
        point_id = _to_int(row.get('connectionpointid'))
        rows.append({
            'gas_date': gas_date,
            'facility_id': facility_id,
            # -1 is the source's "the whole facility", not a real point.
            'connection_point_id': -1 if point_id is None else point_id,
        })
    return _finish(rows, skipped, issues)


PARSERS = {
    'basins': parse_basins,
    'locations': parse_locations,
    'facilities': parse_facilities,
    'connection_points': parse_connection_points,
    'demand_zones': parse_demand_zones,
    'linepack_zones': parse_linepack_zones,
    'nameplate': parse_nameplate,
    'flows': parse_flows,
    'forecasts': parse_forecasts,
    'linepack_adequacy': parse_linepack_adequacy,
    'missing': parse_missing,
}
