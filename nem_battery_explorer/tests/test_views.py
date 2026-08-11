from datetime import date, datetime

from django.test import TestCase
from django.urls import reverse

from nem_battery_explorer.aemo import NEM_TIME
from nem_battery_explorer.models import (
    BatteryAsset,
    BatteryDailySummary,
    BatteryDispatchInterval,
    BatteryRegistration,
    RegionPriceInterval,
)


class ExplorerViewTests(TestCase):
    def test_projects_catalogue_lists_explorer_under_nem_dashboard(self):
        response = self.client.get(reverse('projects'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ChargeTrace')
        self.assertContains(response, 'href="/nem/charge-trace/"')

    def test_explorer_is_a_nem_dashboard_child_route(self):
        self.assertEqual(reverse('nem_battery_explorer:explorer'), '/nem/charge-trace/')

    def test_strategy_guide_has_independent_child_route(self):
        response = self.client.get(reverse('nem_battery_explorer:guide'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'How a grid battery really works')
        self.assertContains(response, 'What a senior trading strategist wants to know')

    def test_previous_standalone_route_redirects_and_preserves_selection(self):
        response = self.client.get(
            '/battery-explorer/?asset=test-battery&date=2026-07-01'
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response['Location'],
            '/nem/charge-trace/?asset=test-battery&date=2026-07-01',
        )

    def test_legacy_nem_route_redirects_and_preserves_selection(self):
        response = self.client.get(
            '/nem/battery-explorer/?asset=test-battery&date=2026-07-01'
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(
            response['Location'],
            '/nem/charge-trace/?asset=test-battery&date=2026-07-01',
        )

    def test_empty_state_explains_how_to_load_data(self):
        response = self.client.get(reverse('nem_battery_explorer:explorer'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No battery interval data has been loaded yet.')
        self.assertContains(response, 'refresh_battery_data')

    def test_selected_asset_and_date_render_public_method_boundary(self):
        operating_date = date(2026, 7, 1)
        asset = BatteryAsset.objects.create(
            slug='test-battery',
            name='Test Battery',
            region='NSW1',
        )
        registration = BatteryRegistration.objects.create(
            asset=asset,
            duid='TESTB1',
            effective_from=operating_date,
            direction_model=BatteryRegistration.BIDIRECTIONAL,
            power_capacity_mw=100,
            storage_capacity_mwh=200,
            source_name='Test source',
            source_url='https://example.com/source',
            source_published_on=date(2026, 7, 31),
            source_registry_version='test-v1',
        )
        interval_end = datetime(2026, 7, 1, 0, 5, tzinfo=NEM_TIME)
        price = RegionPriceInterval.objects.create(
            operating_date=operating_date,
            region='NSW1',
            interval_end=interval_end,
            rrp=100,
            fcas_prices={'raise_6s': 50},
            source_file='price.csv',
        )
        BatteryDispatchInterval.objects.create(
            registration=registration,
            regional_price=price,
            operating_date=operating_date,
            interval_end=interval_end,
            scada_mw=60,
            energy_storage_mwh=115,
            fcas_enablement_mw={'raise_6s': 10},
            discharge_mwh=5,
            discharge_value=500,
            energy_market_value=500,
            gross_fcas_value=50,
            observable_gross_value=550,
            dispatch_source_file='dispatch.csv',
            scada_source_file='scada.csv',
        )
        BatteryDailySummary.objects.create(
            asset=asset,
            operating_date=operating_date,
            interval_count=1,
            scada_interval_count=1,
            storage_interval_count=1,
            discharge_mwh=5,
            throughput_mwh=5,
            equivalent_cycles=0.025,
            discharge_value=500,
            energy_market_value=500,
            gross_fcas_value=50,
            observable_gross_value=550,
            value_per_discharge_mwh=110,
            capture_price=100,
            quality_status='partial',
            quality_notes=['Expected 288 dispatch intervals; found 1.'],
        )

        response = self.client.get(
            reverse('nem_battery_explorer:explorer'),
            {'asset': asset.slug, 'date': operating_date.isoformat()},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Battery')
        self.assertContains(response, 'estimated observable gross market value')
        self.assertContains(response, 'not participant profit')
        self.assertContains(response, 'Mondays at 09:00 Australia/Sydney')
        self.assertContains(response, 'Weekly data refresh')
        self.assertContains(response, 'Week ending 1 July 2026')
        self.assertContains(response, '>Week</a>', html=False)
        self.assertContains(response, '>3 Months</a>', html=False)
        self.assertNotContains(response, '>Annual</a>', html=False)
        self.assertContains(response, 'Not live data')
        self.assertContains(response, 'bex-interval-data')
        self.assertContains(response, 'bex-period-data')
        self.assertContains(response, 'Five-minute day inspector')
        self.assertContains(response, 'Project thesis')
        self.assertNotContains(response, 'All projects')
        self.assertContains(response, 'Opportunity capture')
        self.assertContains(response, 'Fleet coverage')
        self.assertContains(response, 'Growth versus cannibalisation')
        rendered = response.content.decode()
        self.assertLess(rendered.index('Build the foundations'), rendered.index('Period operation'))

        quarter_response = self.client.get(
            reverse('nem_battery_explorer:explorer'),
            {'asset': asset.slug, 'period': 'quarter', 'date': operating_date.isoformat()},
        )
        self.assertEqual(quarter_response.status_code, 200)
        self.assertEqual(quarter_response.context['period'], 'quarter')
        self.assertEqual(quarter_response.context['period_overview']['expected_days'], 91)
        self.assertContains(quarter_response, 'Values are not scaled to a full period or extrapolated.')
        self.assertContains(quarter_response, 'Energy flow')
        self.assertContains(quarter_response, 'Value mix')
        self.assertContains(quarter_response, 'Capture rate')
