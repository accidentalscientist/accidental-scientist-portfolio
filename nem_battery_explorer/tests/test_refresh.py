from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.test import TestCase

from nem_battery_explorer.aemo import AEMODataError, NEM_TIME
from nem_battery_explorer.models import (
    BatteryAsset,
    BatteryDailySummary,
    BatteryDispatchInterval,
    BatteryRegistration,
    RegionPriceInterval,
)
from nem_battery_explorer.refresh import persist_operating_day, refresh_range


class RefreshIdempotencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        asset = BatteryAsset.objects.create(
            slug='test-battery',
            name='Test Battery',
            region='NSW1',
        )
        cls.registration = BatteryRegistration.objects.create(
            asset=asset,
            duid='TESTB1',
            effective_from=date(2026, 7, 1),
            direction_model=BatteryRegistration.BIDIRECTIONAL,
            power_capacity_mw=100,
            storage_capacity_mwh=200,
            source_name='Test source',
            source_url='https://example.com/source',
            source_published_on=date(2026, 7, 31),
            source_registry_version='test-v1',
        )

    def test_reprocessing_same_interval_updates_without_duplicates(self):
        operating_date = date(2026, 7, 1)
        interval_end = datetime(2026, 7, 1, 0, 5, tzinfo=NEM_TIME)
        prices = {
            ('NSW1', interval_end): {
                'rrp': 100,
                'fcas_prices': {'raise_6s': 50},
                'source_file': 'price.csv',
            },
        }
        dispatch = {
            ('TESTB1', interval_end): {
                'initial_mw': 0,
                'dispatch_target_mw': 60,
                'availability_mw': 100,
                'initial_energy_storage_mwh': 120,
                'energy_storage_mwh': 115,
                'fcas_enablement_mw': {'raise_6s': 10},
                'source_file': 'dispatch.csv',
            },
        }
        scada = {
            ('TESTB1', interval_end): {
                'scada_mw': 60,
                'source_file': 'scada.csv',
            },
        }

        persist_operating_day(operating_date, [self.registration], prices, dispatch, scada)
        prices[('NSW1', interval_end)]['rrp'] = 120
        persist_operating_day(operating_date, [self.registration], prices, dispatch, scada)

        self.assertEqual(RegionPriceInterval.objects.count(), 1)
        self.assertEqual(BatteryDispatchInterval.objects.count(), 1)
        self.assertEqual(BatteryDailySummary.objects.count(), 1)
        interval = BatteryDispatchInterval.objects.get()
        self.assertAlmostEqual(interval.energy_market_value, 600)

    @patch('nem_battery_explorer.refresh.persist_operating_day')
    @patch('nem_battery_explorer.refresh._validate_source_coverage')
    @patch('nem_battery_explorer.refresh.parse_dispatch_scada', return_value={})
    @patch('nem_battery_explorer.refresh.parse_dispatch_prices', return_value={})
    @patch('nem_battery_explorer.refresh.parse_next_day_dispatch', return_value={})
    def test_completed_days_remain_in_audit_when_later_day_fails(
        self,
        _dispatch,
        _prices,
        _scada,
        _coverage,
        persist,
    ):
        start = date(2026, 7, 1)
        end = start + timedelta(days=1)
        persist.side_effect = [['first-day warning'], AEMODataError('second day failed')]
        processed_days = []
        warnings = []
        sources = {
            'next_day': {start - timedelta(days=1): 'dispatch-a.zip', start: 'dispatch-b.zip'},
            'prices': {start: 'price-a.zip', end: 'price-b.zip'},
            'scada': {start: 'scada-a.zip', end: 'scada-b.zip'},
        }

        with self.assertRaisesRegex(AEMODataError, 'second day failed'):
            refresh_range(
                start,
                end,
                sources,
                processed_days=processed_days,
                warnings=warnings,
            )

        self.assertEqual(processed_days, [start])
        self.assertEqual(warnings, ['first-day warning'])
