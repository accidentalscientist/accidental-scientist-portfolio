import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import LifeCompassData


@override_settings(ALLOWED_HOSTS=['testserver'])
class LifeCompassPageTests(TestCase):
    def test_pages_ok(self):
        self.assertEqual(self.client.get(reverse('life_compass:home')).status_code, 200)
        self.assertEqual(self.client.get(reverse('life_compass:strategy')).status_code, 200)
        self.assertEqual(self.client.get(reverse('life_compass:execution')).status_code, 200)

    def test_anonymous_page_has_no_data_authenticated_true(self):
        response = self.client.get(reverse('life_compass:home'))
        self.assertContains(response, 'data-authenticated="false"')

    def test_execution_has_edit_only_daily_task_reset(self):
        response = self.client.get(reverse('life_compass:execution'))
        self.assertContains(response, 'id="reset-day"')
        self.assertContains(response, 'aria-label="Clear completed daily task slots"')
        self.assertContains(response, 'id="reset-day-hint"')
        self.assertContains(response, "When 3 Tasks are completed, R let's you add 3 new tasks to complete. A sign of great productivity!")
        self.assertContains(response, 'data-edit-only')
        self.assertContains(response, 'disabled')
        self.assertContains(response, 'execution-reset-daily-tasks.js')
        self.assertContains(response, 'execution-reset-daily-tasks.css')

    def test_daily_task_reset_only_replaces_daily_slots(self):
        asset = Path(settings.BASE_DIR) / 'life_compass/static/life_compass/assets/execution-reset-daily-tasks.js'
        javascript = asset.read_text(encoding='utf-8')

        self.assertIn('localStorage.setItem(todayKey()', javascript)
        self.assertIn('allThreeTasksAreComplete()', javascript)
        self.assertIn('tasks.length === 3', javascript)
        self.assertIn('Completed tasks will stay completed.', javascript)
        self.assertNotIn('lifeCompass.kanban', javascript)
        self.assertNotIn('lifeCompass.doneLedger', javascript)
        self.assertNotIn('lifeCompass.calendar', javascript)

        stylesheet = asset.with_suffix('.css').read_text(encoding='utf-8')
        self.assertIn('.task-reset-button', stylesheet)
        self.assertIn('display: none !important', stylesheet)
        self.assertIn('.reset-day-wrap.is-locked:hover .reset-day-hint', stylesheet)

    def test_execution_first_pass_visual_hierarchy(self):
        response = self.client.get(reverse('life_compass:execution'))

        self.assertContains(response, 'class="panel execution-hero execution-focus-strip"')
        self.assertContains(response, 'id="focus-main"', count=1)
        self.assertContains(response, 'id="focus-secondary"', count=1)
        self.assertContains(response, 'id="focus-health"', count=1)
        self.assertContains(response, 'id="execution-north-star"', count=1)
        self.assertContains(response, 'Projects Kanban')
        self.assertContains(response, 'Move Ideas Forward.')
        self.assertContains(response, '<h2>X Calendar</h2>', html=True)
        self.assertContains(response, 'Move The Needle.')
        self.assertContains(response, 'href="#icon-sailboat"')
        self.assertContains(response, 'href="#icon-anchor"')
        self.assertContains(response, 'href="#icon-lighthouse"')
        self.assertContains(response, 'href="#icon-wheel"')
        self.assertContains(response, 'id="back-site-hint"')
        self.assertContains(response, 'class="nav-icon-hint"')
        self.assertContains(response, 'id="open-archive" data-edit-only')
        self.assertContains(response, 'execution-visual-enhancements.js')
        self.assertContains(response, 'execution-visual-enhancements.css')

        stylesheet = Path(settings.BASE_DIR) / 'life_compass/static/life_compass/assets/execution-visual-enhancements.css'
        visual_css = stylesheet.read_text(encoding='utf-8')
        self.assertIn('.calendar-panel .day-cell', visual_css)
        self.assertIn('url("/static/life_compass/assets/sail-hero.png")', visual_css)
        self.assertIn('url("/static/life_compass/assets/roman-bireme-explorer.webp")', visual_css)
        self.assertIn('background-size: cover', visual_css)

        visual_javascript = stylesheet.with_suffix('.js').read_text(encoding='utf-8')
        self.assertIn('href="#icon-settings"', visual_javascript)
        self.assertIn('function alignPanelArtwork', visual_javascript)
        self.assertIn('[".execution-focus-strip", ".daily-panel", ".ledger-panel"]', visual_javascript)
        self.assertIn('[".calendar-panel", ".kanban-panel"]', visual_javascript)
        self.assertIn('panel.style.backgroundPosition', visual_javascript)
        self.assertIn('positioning: { zoom: 1.05, x: -0.02, y: -0.03 }', visual_javascript)
        self.assertIn('positioning: { zoom: 1.35, x: -0.08, y: -0.18 }', visual_javascript)


@override_settings(ALLOWED_HOSTS=['testserver'])
class LifeCompassSyncTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user('lc_user_a', password='pw12345a', is_staff=False, is_superuser=False)
        self.user_b = User.objects.create_user('lc_user_b', password='pw12345b', is_staff=False, is_superuser=False)
        self.url = reverse('life_compass:sync_data')

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('life_compass:login'), response.url)

    def test_get_before_any_save_returns_empty(self):
        self.client.login(username='lc_user_a', password='pw12345a')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'data': {}})

    def test_post_then_get_round_trips(self):
        self.client.login(username='lc_user_a', password='pw12345a')
        payload = {'data': {'lifeCompass.parkingLot': 'a marker value'}}
        post_response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(post_response.status_code, 200)

        get_response = self.client.get(self.url)
        self.assertEqual(get_response.json(), payload)

    def test_data_is_isolated_per_user(self):
        self.client.login(username='lc_user_a', password='pw12345a')
        self.client.post(
            self.url,
            data=json.dumps({'data': {'lifeCompass.parkingLot': 'user a only'}}),
            content_type='application/json',
        )
        self.client.logout()

        self.client.login(username='lc_user_b', password='pw12345b')
        response = self.client.get(self.url)
        self.assertEqual(response.json(), {'data': {}})

    def test_post_rejects_non_object_data(self):
        self.client.login(username='lc_user_a', password='pw12345a')
        response = self.client.post(
            self.url, data=json.dumps({'data': 'not an object'}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_post_rejects_invalid_json(self):
        self.client.login(username='lc_user_a', password='pw12345a')
        response = self.client.post(self.url, data='not json', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_login_view_rejects_wrong_password(self):
        response = self.client.post(reverse('life_compass:login'), data={'username': 'lc_user_a', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['user'].is_authenticated)
