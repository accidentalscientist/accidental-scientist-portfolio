import json
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from nem_battery_explorer.models import BatteryAsset, BatteryRegistration
from nem_battery_explorer.registry import DEFAULT_REGISTRY_PATH, RegistryError, read_registry


class RegistryImportTests(TestCase):
    def test_default_registry_has_expanded_source_backed_cohort(self):
        call_command('load_battery_registry', verbosity=0)

        self.assertEqual(BatteryAsset.objects.count(), 17)
        self.assertEqual(BatteryRegistration.objects.count(), 18)
        self.assertEqual(BatteryAsset.objects.filter(is_spike_cohort=True).count(), 3)
        duids = set(BatteryRegistration.objects.values_list('duid', flat=True))
        self.assertTrue({'CAPBES1', 'BLYTHB1', 'VBB1', 'ERB01', 'TARBESS1', 'WDBESS2'} <= duids)

        total_mw = sum(float(value) for value in BatteryRegistration.objects.values_list('power_capacity_mw', flat=True))
        total_mwh = sum(float(value) for value in BatteryRegistration.objects.values_list('storage_capacity_mwh', flat=True))
        self.assertAlmostEqual(total_mw, 4316.82, places=2)
        self.assertAlmostEqual(total_mwh, 9219.89, places=2)

    def test_import_is_idempotent(self):
        call_command('load_battery_registry', verbosity=0)
        call_command('load_battery_registry', verbosity=0)

        self.assertEqual(BatteryAsset.objects.count(), 17)
        self.assertEqual(BatteryRegistration.objects.count(), 18)

    def test_dry_run_leaves_database_unchanged(self):
        call_command('load_battery_registry', dry_run=True, verbosity=0)

        self.assertFalse(BatteryAsset.objects.exists())
        self.assertFalse(BatteryRegistration.objects.exists())

    def test_rejects_duplicate_asset_slug(self):
        payload = read_registry(DEFAULT_REGISTRY_PATH)
        payload['assets'].append(payload['assets'][0])
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'registry.json'
            path.write_text(json.dumps(payload), encoding='utf-8')
            with self.assertRaisesRegex(RegistryError, 'Duplicate asset slug'):
                read_registry(path)


class BatteryRegistrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.asset = BatteryAsset.objects.create(
            slug='test-battery',
            name='Test Battery',
            region='NSW1',
        )
        cls.source_defaults = {
            'asset': cls.asset,
            'direction_model': BatteryRegistration.BIDIRECTIONAL,
            'power_capacity_mw': 100,
            'storage_capacity_mwh': 200,
            'source_name': 'Test source',
            'source_url': 'https://example.com/source',
            'source_published_on': date(2026, 7, 31),
            'source_registry_version': 'test-v1',
        }

    def test_effective_date_is_inclusive(self):
        registration = BatteryRegistration.objects.create(
            duid='TESTB1',
            effective_from=date(2026, 7, 1),
            effective_to=date(2026, 7, 31),
            **self.source_defaults,
        )

        self.assertTrue(registration.is_effective_on(date(2026, 7, 1)))
        self.assertTrue(registration.is_effective_on(date(2026, 7, 31)))
        self.assertFalse(registration.is_effective_on(date(2026, 8, 1)))

    def test_overlapping_duid_registration_is_rejected(self):
        BatteryRegistration.objects.create(
            duid='TESTB1',
            effective_from=date(2026, 7, 1),
            effective_to=date(2026, 7, 31),
            **self.source_defaults,
        )
        overlapping = BatteryRegistration(
            duid='TESTB1',
            effective_from=date(2026, 7, 15),
            effective_to=None,
            **self.source_defaults,
        )

        with self.assertRaises(ValidationError):
            overlapping.full_clean()
