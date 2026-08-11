"""Small, explicit readers for the public AEMO files used by the explorer."""

import csv
import hashlib
import io
import re
import shutil
import time
from datetime import datetime, time as day_time, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile


NEM_TIME = timezone(timedelta(hours=10), name='NEM')
NEXT_DAY_INDEX = 'https://www.nemweb.com.au/Reports/CURRENT/Next_Day_Dispatch/'
DISPATCH_IS_ARCHIVE = 'https://nemweb.com.au/Reports/Archive/DispatchIS_Reports/'
SCADA_ARCHIVE = 'https://nemweb.com.au/Reports/Archive/Dispatch_SCADA/'
USER_AGENT = 'AccidentalScientist-NEMBatteryExplorer/1.0'

FCAS_DISPATCH_FIELDS = {
    'raise_1s': 'RAISE1SEC',
    'raise_6s': 'RAISE6SEC',
    'raise_60s': 'RAISE60SEC',
    'raise_5m': 'RAISE5MIN',
    'raise_reg': 'RAISEREG',
    'lower_1s': 'LOWER1SEC',
    'lower_6s': 'LOWER6SEC',
    'lower_60s': 'LOWER60SEC',
    'lower_5m': 'LOWER5MIN',
    'lower_reg': 'LOWERREG',
}
FCAS_PRICE_FIELDS = {key: f'{field}RRP' for key, field in FCAS_DISPATCH_FIELDS.items()}


class AEMODataError(RuntimeError):
    pass


def parse_nem_datetime(value):
    try:
        return datetime.strptime(value, '%Y/%m/%d %H:%M:%S').replace(tzinfo=NEM_TIME)
    except (TypeError, ValueError) as exc:
        raise AEMODataError(f'Invalid AEMO timestamp: {value!r}') from exc


def calendar_window(operating_date):
    start = datetime.combine(operating_date, day_time.min, tzinfo=NEM_TIME)
    return start, start + timedelta(days=1)


def interval_belongs_to(when, operating_date):
    start, end = calendar_window(operating_date)
    return start < when <= end


def _float(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise AEMODataError(f'Expected a number, received {value!r}.') from exc


def _mms_rows(binary_stream, table_name):
    headers = None
    reader = csv.reader(io.TextIOWrapper(binary_stream, encoding='utf-8-sig', errors='replace', newline=''))
    for row in reader:
        if len(row) < 4 or row[1:3] != ['DISPATCH', table_name]:
            continue
        if row[0] == 'I':
            headers = row[4:]
        elif row[0] == 'D' and headers:
            values = row[4:]
            if len(values) < len(headers):
                values.extend([''] * (len(headers) - len(values)))
            yield dict(zip(headers, values))


def _nested_mms_rows(archive_path, table_name):
    try:
        with ZipFile(archive_path) as outer:
            for nested_info in sorted(outer.infolist(), key=lambda item: item.filename):
                if not nested_info.filename.lower().endswith('.zip'):
                    continue
                nested_bytes = outer.read(nested_info)
                with ZipFile(io.BytesIO(nested_bytes)) as nested:
                    csv_entries = [item for item in nested.infolist() if item.filename.lower().endswith('.csv')]
                    if len(csv_entries) != 1:
                        raise AEMODataError(
                            f'{nested_info.filename} contains {len(csv_entries)} CSV files; expected one.'
                        )
                    with nested.open(csv_entries[0]) as stream:
                        for row in _mms_rows(stream, table_name):
                            yield row, csv_entries[0].filename
    except BadZipFile as exc:
        raise AEMODataError(f'Invalid ZIP archive: {archive_path}') from exc


def parse_next_day_dispatch(archive_paths, duids):
    """Read selected DUIDs from one or more 04:00-to-04:00 trading-day files."""

    duids = set(duids)
    records = {}
    for archive_path in archive_paths:
        try:
            with ZipFile(archive_path) as archive:
                csv_entries = [item for item in archive.infolist() if item.filename.lower().endswith('.csv')]
                if len(csv_entries) != 1:
                    raise AEMODataError(f'{archive_path} must contain exactly one CSV file.')
                source_file = csv_entries[0].filename
                with archive.open(csv_entries[0]) as stream:
                    for row in _mms_rows(stream, 'UNIT_SOLUTION'):
                        if row.get('DUID') not in duids or row.get('INTERVENTION') != '0':
                            continue
                        when = parse_nem_datetime(row['SETTLEMENTDATE'])
                        key = (row['DUID'], when)
                        records[key] = {
                            'initial_mw': _float(row.get('INITIALMW')),
                            'dispatch_target_mw': _float(row.get('TOTALCLEARED')),
                            'availability_mw': _float(row.get('AVAILABILITY')),
                            'initial_energy_storage_mwh': _float(row.get('INITIAL_ENERGY_STORAGE')),
                            'energy_storage_mwh': _float(row.get('ENERGY_STORAGE')),
                            'fcas_enablement_mw': {
                                key: _float(row.get(field)) or 0.0
                                for key, field in FCAS_DISPATCH_FIELDS.items()
                            },
                            'source_file': source_file,
                        }
        except BadZipFile as exc:
            raise AEMODataError(f'Invalid next-day dispatch ZIP: {archive_path}') from exc
    return records


def parse_dispatch_prices(archive_path, regions):
    regions = set(regions)
    records = {}
    for row, source_file in _nested_mms_rows(archive_path, 'PRICE'):
        if row.get('REGIONID') not in regions or row.get('INTERVENTION') != '0':
            continue
        when = parse_nem_datetime(row['SETTLEMENTDATE'])
        records[(row['REGIONID'], when)] = {
            'rrp': _float(row.get('RRP')),
            'fcas_prices': {
                key: _float(row.get(field)) or 0.0
                for key, field in FCAS_PRICE_FIELDS.items()
            },
            'source_file': source_file,
        }
    return records


def parse_dispatch_scada(archive_path, duids):
    duids = set(duids)
    records = {}
    for row, source_file in _nested_mms_rows(archive_path, 'UNIT_SCADA'):
        if row.get('DUID') not in duids:
            continue
        when = parse_nem_datetime(row['SETTLEMENTDATE'])
        records[(row['DUID'], when)] = {
            'scada_mw': _float(row.get('SCADAVALUE')),
            'source_file': source_file,
        }
    return records


def discover_next_day_files():
    request = Request(NEXT_DAY_INDEX, headers={'User-Agent': USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response:
            page = response.read().decode('utf-8', errors='replace')
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise AEMODataError(f'Could not read AEMO next-day dispatch index: {exc}') from exc

    filenames = re.findall(r'PUBLIC_NEXT_DAY_DISPATCH_(\d{8})_[^"<>\s]+\.zip', page, re.I)
    mapping = {}
    for date_token in filenames:
        match = re.search(
            rf'(PUBLIC_NEXT_DAY_DISPATCH_{date_token}_[^"<>\s]+\.zip)',
            page,
            re.I,
        )
        if match:
            mapping[datetime.strptime(date_token, '%Y%m%d').date()] = match.group(1)
    if not mapping:
        raise AEMODataError('AEMO next-day dispatch index contained no matching files.')
    return mapping


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url, destination, *, attempts=3):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        try:
            with ZipFile(destination) as archive:
                if archive.testzip() is None:
                    return destination
        except BadZipFile:
            destination.unlink()

    last_error = None
    for attempt in range(1, attempts + 1):
        temporary = destination.with_suffix(destination.suffix + '.part')
        try:
            request = Request(url, headers={'User-Agent': USER_AGENT})
            with urlopen(request, timeout=60) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            with ZipFile(temporary) as archive:
                corrupt = archive.testzip()
                if corrupt:
                    raise AEMODataError(f'{temporary.name} contains a corrupt member: {corrupt}')
            temporary.replace(destination)
            return destination
        except (AEMODataError, BadZipFile, HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if temporary.exists():
                temporary.unlink()
            if attempt < attempts:
                time.sleep(attempt)
    raise AEMODataError(f'Could not download {url}: {last_error}')


def download_source_set(start_date, end_date, cache_dir):
    """Download each unique source file once and return paths plus receipts."""

    cache_dir = Path(cache_dir)
    next_day_index = discover_next_day_files()
    next_day_paths = {}
    price_paths = {}
    scada_paths = {}
    receipts = []

    dispatch_date = start_date - timedelta(days=1)
    while dispatch_date <= end_date:
        filename = next_day_index.get(dispatch_date)
        if not filename:
            raise AEMODataError(
                f'No current next-day dispatch file was found for {dispatch_date}. '
                'An archive backfill is required.'
            )
        url = NEXT_DAY_INDEX + filename
        path = download_file(url, cache_dir / filename)
        next_day_paths[dispatch_date] = path
        receipts.append(_receipt('next_day_dispatch', dispatch_date, url, path))
        dispatch_date += timedelta(days=1)

    operating_date = start_date
    while operating_date <= end_date:
        token = operating_date.strftime('%Y%m%d')
        price_name = f'PUBLIC_DISPATCHIS_{token}.zip'
        price_url = DISPATCH_IS_ARCHIVE + price_name
        price_path = download_file(price_url, cache_dir / price_name)
        price_paths[operating_date] = price_path
        receipts.append(_receipt('dispatchis', operating_date, price_url, price_path))

        scada_name = f'PUBLIC_DISPATCHSCADA_{token}.zip'
        scada_url = SCADA_ARCHIVE + scada_name
        scada_path = download_file(scada_url, cache_dir / scada_name)
        scada_paths[operating_date] = scada_path
        receipts.append(_receipt('dispatch_scada', operating_date, scada_url, scada_path))
        operating_date += timedelta(days=1)

    return {
        'next_day': next_day_paths,
        'prices': price_paths,
        'scada': scada_paths,
        'receipts': receipts,
    }


def _receipt(source, operating_date, url, path):
    path = Path(path)
    return {
        'source': source,
        'operating_date': operating_date.isoformat(),
        'url': url,
        'filename': path.name,
        'bytes': path.stat().st_size,
        'sha256': sha256_file(path),
    }
