from django.test import TestCase, override_settings
from django.utils import timezone

from .aemo_fuel import classify_fuel
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
