import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import BatteryAsset, BatteryRegistration


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent / 'data' / 'battery_registry_v1.json'
REQUIRED_SOURCE_FIELDS = {'name', 'url', 'published_on'}
REQUIRED_ASSET_FIELDS = {
    'slug', 'name', 'region', 'owner', 'custodian', 'aemo_survey_id',
    'commitment_status', 'is_spike_cohort', 'registrations',
}
REQUIRED_REGISTRATION_FIELDS = {
    'duid', 'direction_model', 'effective_from', 'effective_to',
    'power_capacity_mw', 'storage_capacity_mwh',
    'aemo_generation_info_unit_id', 'unit_name', 'connection_point_id', 'notes',
}


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class RegistryLoadResult:
    assets_created: int = 0
    assets_updated: int = 0
    registrations_created: int = 0
    registrations_updated: int = 0


def _date(value, field, *, optional=False):
    if value is None and optional:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise RegistryError(f'{field} must be an ISO date.') from exc


def _positive_decimal(value, field):
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RegistryError(f'{field} must be a number.') from exc
    if parsed <= 0:
        raise RegistryError(f'{field} must be greater than zero.')
    return parsed


def read_registry(path=DEFAULT_REGISTRY_PATH):
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistryError(f'Could not read registry {path}: {exc}') from exc

    if payload.get('schema_version') != 1:
        raise RegistryError('Only battery registry schema_version 1 is supported.')
    if not payload.get('registry_version'):
        raise RegistryError('registry_version is required.')
    source = payload.get('source') or {}
    missing_source = REQUIRED_SOURCE_FIELDS - source.keys()
    if missing_source:
        raise RegistryError(f'Source is missing: {", ".join(sorted(missing_source))}.')
    _date(source['published_on'], 'source.published_on')

    assets = payload.get('assets')
    if not isinstance(assets, list) or not assets:
        raise RegistryError('Registry must contain at least one asset.')

    seen_slugs = set()
    seen_registrations = set()
    for asset in assets:
        missing = REQUIRED_ASSET_FIELDS - asset.keys()
        if missing:
            raise RegistryError(f'Asset is missing: {", ".join(sorted(missing))}.')
        if asset['slug'] in seen_slugs:
            raise RegistryError(f'Duplicate asset slug: {asset["slug"]}.')
        seen_slugs.add(asset['slug'])
        if not isinstance(asset['registrations'], list) or not asset['registrations']:
            raise RegistryError(f'{asset["slug"]} must contain at least one registration.')

        for registration in asset['registrations']:
            missing_registration = REQUIRED_REGISTRATION_FIELDS - registration.keys()
            if missing_registration:
                raise RegistryError(
                    f'{asset["slug"]} registration is missing: '
                    f'{", ".join(sorted(missing_registration))}.'
                )
            start = _date(registration['effective_from'], 'effective_from')
            end = _date(registration['effective_to'], 'effective_to', optional=True)
            if end and end < start:
                raise RegistryError(f'{asset["slug"]} has an effective end before its start.')
            _positive_decimal(registration['power_capacity_mw'], 'power_capacity_mw')
            _positive_decimal(registration['storage_capacity_mwh'], 'storage_capacity_mwh')
            key = (asset['slug'], registration['duid'], registration['effective_from'])
            if key in seen_registrations:
                raise RegistryError(f'Duplicate registration: {key}.')
            seen_registrations.add(key)

    return payload


@transaction.atomic
def load_registry(path=DEFAULT_REGISTRY_PATH, *, dry_run=False):
    payload = read_registry(path)
    source = payload['source']
    counts = {
        'assets_created': 0,
        'assets_updated': 0,
        'registrations_created': 0,
        'registrations_updated': 0,
    }

    for item in payload['assets']:
        registrations = item['registrations']
        defaults = {
            'name': item['name'],
            'region': item['region'],
            'owner': item['owner'],
            'custodian': item['custodian'],
            'aemo_survey_id': item['aemo_survey_id'],
            'commitment_status': item['commitment_status'],
            'is_spike_cohort': item['is_spike_cohort'],
            'notes': item.get('notes', ''),
        }
        asset, created = BatteryAsset.objects.update_or_create(slug=item['slug'], defaults=defaults)
        counts['assets_created' if created else 'assets_updated'] += 1

        for registration in registrations:
            identity = {
                'asset': asset,
                'duid': registration['duid'],
                'effective_from': _date(registration['effective_from'], 'effective_from'),
            }
            registration_defaults = {
                'direction_model': registration['direction_model'],
                'effective_to': _date(registration['effective_to'], 'effective_to', optional=True),
                'power_capacity_mw': _positive_decimal(
                    registration['power_capacity_mw'], 'power_capacity_mw'
                ),
                'storage_capacity_mwh': _positive_decimal(
                    registration['storage_capacity_mwh'], 'storage_capacity_mwh'
                ),
                'aemo_generation_info_unit_id': registration['aemo_generation_info_unit_id'],
                'unit_name': registration['unit_name'],
                'connection_point_id': registration['connection_point_id'],
                'source_name': source['name'],
                'source_url': source['url'],
                'source_published_on': _date(source['published_on'], 'source.published_on'),
                'source_registry_version': payload['registry_version'],
                'notes': registration['notes'],
            }
            record, registration_created = BatteryRegistration.objects.update_or_create(
                **identity,
                defaults=registration_defaults,
            )
            try:
                record.full_clean()
            except ValidationError as exc:
                raise RegistryError(f'Invalid registration {record.duid}: {exc}') from exc
            record.save()
            counts[
                'registrations_created' if registration_created else 'registrations_updated'
            ] += 1

    if dry_run:
        transaction.set_rollback(True)
    return RegistryLoadResult(**counts)
