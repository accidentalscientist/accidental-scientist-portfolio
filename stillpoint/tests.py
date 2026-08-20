import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import StillpointSession


@override_settings(ALLOWED_HOSTS=['testserver'])
class StillpointTests(TestCase):
    def test_timer_ok(self):
        self.assertEqual(self.client.get('/stillpoint/').status_code, 200)


@override_settings(ALLOWED_HOSTS=['testserver'])
class StillpointSessionSyncTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sp_user', password='pw12345a', is_staff=False, is_superuser=False)
        self.url = reverse('stillpoint:sessions')

    def test_anonymous_get_returns_empty_without_error(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'sessions': []})

    def test_anonymous_post_is_skipped_not_persisted(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'completedAt': '2026-08-19T09:00:00Z', 'durationSeconds': 900, 'mode': 'master'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StillpointSession.objects.count(), 0)

    def test_authenticated_post_then_get_round_trips(self):
        self.client.login(username='sp_user', password='pw12345a')
        response = self.client.post(
            self.url,
            data=json.dumps({'completedAt': '2026-08-19T09:00:00Z', 'durationSeconds': 900, 'mode': 'master'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(StillpointSession.objects.filter(user=self.user).count(), 1)

        get_response = self.client.get(self.url)
        sessions = get_response.json()['sessions']
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['durationSeconds'], 900)
        self.assertEqual(sessions[0]['mode'], 'master')

    def test_post_rejects_invalid_payload(self):
        self.client.login(username='sp_user', password='pw12345a')
        response = self.client.post(
            self.url,
            data=json.dumps({'completedAt': '', 'durationSeconds': 900, 'mode': 'master'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
