from django.test import TestCase, override_settings


@override_settings(ALLOWED_HOSTS=['testserver'])
class StillpointTests(TestCase):
    def test_timer_ok(self):
        self.assertEqual(self.client.get('/stillpoint/').status_code, 200)
