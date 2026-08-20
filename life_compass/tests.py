import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import CalendarMark, KanbanCard, Strategy, WeeklyFocus


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
        self.assertContains(response, 'When all three daily tasks are done, Reset clears the slots so you can add three new ones.')
        self.assertContains(response, 'data-edit-only')
        self.assertContains(response, 'disabled')
        self.assertRegex(response.content.decode(), r'execution-[\w-]+\.js')
        self.assertRegex(response.content.decode(), r'sync-[\w-]+\.css')

    def test_daily_task_reset_only_replaces_daily_slots(self):
        asset_dir = Path(settings.BASE_DIR) / 'life_compass/static/life_compass/assets'
        javascript = next(asset_dir.glob('execution-*.js')).read_text(encoding='utf-8')

        self.assertIn("Clear today's three task slots? Completed tasks will stay completed.", javascript)
        # Checked as a bare array literal, not tied to a specific minified
        # variable name on the left — that's an implementation detail the
        # bundler is free to rename, and has (single-letter names shift
        # whenever unrelated source changes move things around).
        empty_slot = '{text:"",done:!1,projectId:null,subtaskId:null}'
        self.assertIn(f'[{empty_slot},{empty_slot},{empty_slot}]', javascript)

        stylesheet = next(asset_dir.glob('sync-*.css')).read_text(encoding='utf-8')
        self.assertIn('#reset-day:disabled', stylesheet)
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
        self.assertContains(response, '<h2>X Calendar.</h2>', html=True)
        self.assertContains(response, 'Move The Needle.')
        self.assertContains(response, 'href="#icon-sailboat"')
        self.assertContains(response, 'href="#icon-anchor"')
        self.assertContains(response, 'href="#icon-lighthouse"')
        self.assertContains(response, 'href="#icon-wheel"')
        self.assertContains(response, 'id="back-site-hint"')
        self.assertContains(response, 'class="nav-icon-hint"')
        self.assertContains(response, 'id="open-archive" data-edit-only')
        asset_dir = Path(settings.BASE_DIR) / 'life_compass/static/life_compass/assets'
        visual_css = next(asset_dir.glob('sync-*.css')).read_text(encoding='utf-8')
        self.assertIn('.calendar-panel .day-cell', visual_css)
        self.assertIn('url(/static/life_compass/assets/sail-hero.png)', visual_css)
        self.assertIn('url(/static/life_compass/assets/roman-bireme-explorer.webp)', visual_css)
        self.assertIn('background-size:cover', visual_css)


@override_settings(ALLOWED_HOSTS=['testserver'])
class LifeCompassSyncTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user('lc_user_a', password='pw12345a', is_staff=False, is_superuser=False)
        self.user_b = User.objects.create_user('lc_user_b', password='pw12345b', is_staff=False, is_superuser=False)
        self.url = reverse('life_compass:sync_data')

    def full_payload(self):
        return {
            'lifeCompass.strategy': {
                'title': 'The map before action.',
                'principle': 'Strategy is the map.',
                'northStar': 'Build a meaningful career',
                'currentSeason': 'Create visible progress',
                'careerCompass': {'title': 'Direction', 'items': [{'label': 'Capability', 'text': 'Build skills.'}]},
                'season': {'title': 'Season', 'summary': 'A focused season.', 'points': ['Ship it.'], 'tags': ['Focus']},
                'rules': [{'number': '01', 'name': 'Protect Momentum', 'summary': 'Keep going.', 'text': 'Small steps.'}],
                'careerStory': {'title': 'Story', 'body': 'Body text.', 'points': ['Point one.']},
                'longTermDirection': ['Build a useful career.'],
            },
            'lifeCompass.kanban': {
                'Ideas': [],
                'This Week': [
                    {
                        'id': 'card-1',
                        'title': 'Write project brief',
                        'date': '2026-08-19',
                        'description': 'Draft the brief.',
                        'priority': 'high',
                        'subtasks': [{'id': 'sub-1', 'text': 'Outline', 'done': True}],
                        'createdAt': '2026-08-01T00:00:00Z',
                        'updatedAt': '2026-08-19T00:00:00Z',
                        'enteredThisWeekAt': '2026-08-15T00:00:00Z',
                    }
                ],
                'Complete': [],
                'Parking Lot': [],
            },
            'lifeCompass.parkingLot': [],
            'lifeCompass.archive': [],
            'lifeCompass.calendar': {'2026-08-19': True},
            'lifeCompass.dailyTasks.2026-08-19': [
                {'text': 'Draft the brief', 'done': False, 'projectId': 'card-1', 'subtaskId': None},
            ],
            'lifeCompass.weeklyFocus.2026-34': {'main': 'Draft the brief', 'secondary': 'Review', 'health': 'Walk'},
            'lifeCompass.doneLedger': [
                {'text': 'Outline', 'source': 'Daily task', 'date': '2026-08-19T09:00:00Z'},
            ],
            'lifeCompass.settings': {'editMode': False},
            'lifeCompass.stats': {'pomodoroCount': 2, 'taskCompletionCount': 1},
        }

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
        payload = {'data': self.full_payload()}
        post_response = self.client.post(self.url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(post_response.status_code, 200)

        get_response = self.client.get(self.url)
        got = get_response.json()['data']
        self.assertEqual(got['lifeCompass.strategy']['title'], 'The map before action.')
        self.assertEqual(got['lifeCompass.kanban']['This Week'][0]['id'], 'card-1')
        self.assertEqual(got['lifeCompass.calendar'], {'2026-08-19': True})
        self.assertEqual(got['lifeCompass.dailyTasks.2026-08-19'][0]['text'], 'Draft the brief')
        self.assertEqual(got['lifeCompass.weeklyFocus.2026-34']['main'], 'Draft the brief')
        self.assertEqual(got['lifeCompass.doneLedger'][0]['text'], 'Outline')
        self.assertEqual(got['lifeCompass.settings'], {'editMode': False})
        self.assertEqual(got['lifeCompass.stats'], {'pomodoroCount': 2, 'taskCompletionCount': 1})

    def test_second_post_updates_rows_instead_of_duplicating(self):
        self.client.login(username='lc_user_a', password='pw12345a')
        payload = self.full_payload()
        self.client.post(self.url, data=json.dumps({'data': payload}), content_type='application/json')

        payload['lifeCompass.strategy']['title'] = 'Updated title'
        payload['lifeCompass.kanban']['Complete'] = payload['lifeCompass.kanban']['This Week']
        payload['lifeCompass.kanban']['This Week'] = []
        self.client.post(self.url, data=json.dumps({'data': payload}), content_type='application/json')

        self.assertEqual(Strategy.objects.filter(user=self.user_a).count(), 1)
        self.assertEqual(Strategy.objects.get(user=self.user_a).title, 'Updated title')
        self.assertEqual(KanbanCard.objects.filter(user=self.user_a, client_id='card-1').count(), 1)
        self.assertEqual(KanbanCard.objects.get(user=self.user_a, client_id='card-1').column, 'Complete')
        self.assertEqual(WeeklyFocus.objects.filter(user=self.user_a).count(), 1)
        self.assertEqual(CalendarMark.objects.filter(user=self.user_a).count(), 1)

        history = Strategy.objects.get(user=self.user_a).history.all()
        self.assertEqual(history.count(), 2)
        card_history = KanbanCard.objects.get(user=self.user_a, client_id='card-1').history.all()
        self.assertEqual(card_history.count(), 2)

    def test_data_is_isolated_per_user(self):
        self.client.login(username='lc_user_a', password='pw12345a')
        self.client.post(
            self.url,
            data=json.dumps({'data': self.full_payload()}),
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
