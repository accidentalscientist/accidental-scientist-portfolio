from django.test import TestCase, override_settings
from django.utils import timezone

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
