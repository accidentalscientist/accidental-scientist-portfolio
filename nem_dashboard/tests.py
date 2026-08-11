from unittest.mock import call, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .aemo_fuel import classify_fuel
from .management.commands.refresh_nem_suite import Command as RefreshSuiteCommand
from .models import FuelGenerationData


@override_settings(ALLOWED_HOSTS=['testserver'])
class NemDashboardTests(TestCase):
    def test_no_data_state(self):
        resp = self.client.get('/nem/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No generation data')

    def test_with_data_state(self):
        now = timezone.now()
        for fuel in ['Black coal', 'Wind', 'Gas']:
            FuelGenerationData.objects.create(
                timestamp=now, state='NSW', fuel_type=fuel, supply_mw=100,
            )
        resp = self.client.get('/nem/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'No generation data')


class FuelClassificationTests(TestCase):
    def test_aemo_technologies_map_to_public_fuel_labels(self):
        cases = [
            (('Coal', 'Black Coal', ''), 'Black coal'),
            (('Coal', 'Brown Coal', ''), 'Brown coal'),
            (('Battery Storage', 'Lithium-ion', ''), 'Battery'),
            (('Solar PV', 'Single Axis Tracking', ''), 'Solar'),
            (('Gas Turbine', 'OCGT', 'Natural Gas'), 'Gas'),
            (('Gas Turbine', 'OCGT', 'Diesel/ Fuel Oil'), 'Liquid Fuel'),
            (('Other', 'Other', 'Landfill Gas'), 'Biomass'),
        ]
        for inputs, expected in cases:
            with self.subTest(inputs=inputs):
                self.assertEqual(classify_fuel(*inputs), expected)


class RefreshSuiteCommandTests(SimpleTestCase):
    def test_price_refresh_fills_recent_issue_time_weather_gap(self):
        command = RefreshSuiteCommand()
        with patch.object(command, '_run') as run, patch.object(
            command, '_publish_missing_forecasts'
        ) as publish:
            command.handle(
                skip_fuel=True,
                skip_price=False,
                skip_battery=True,
                skip_gas=True,
            )

        run.assert_has_calls([
            call([], 'Settled prices', 'ingest_nem_prices'),
            call([], 'Observed weather', 'ingest_nem_weather', kind='observed', months=1),
            call(
                [],
                'Recent archived weather forecasts',
                'ingest_nem_weather',
                kind='forecast',
                months=1,
            ),
            call([], 'Forward weather', 'ingest_nem_weather', forward=True),
        ])
        publish.assert_called_once_with([])
