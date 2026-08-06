import json

from django.test import SimpleTestCase
from django.urls import reverse

from .views import DATA_PATH


class WorldLedgerDashboardTests(SimpleTestCase):
    def test_dashboard_renders_giga_dataset_and_visual_stories(self):
        response = self.client.get(reverse('world_lens:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'World Ledger')
        self.assertContains(response, 'Giga Dataset version 1.0')
        self.assertContains(response, 'What drives the ranking?')
        self.assertContains(response, 'Trade constellation')
        self.assertContains(response, 'Harvard Growth Lab Atlas of Economic Complexity')
        self.assertContains(response, 'world-lens-data')

    def test_giga_v1_uses_one_complete_48_economy_cohort(self):
        payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))

        self.assertEqual(payload['meta']['product'], 'World Ledger')
        self.assertEqual(payload['meta']['dataset'], 'Giga Dataset version 1.0')
        self.assertEqual(payload['meta']['cohort_count'], 48)
        self.assertEqual(len(payload['countries']), 48)
        self.assertEqual(
            payload['meta']['models']['power']['components'],
            ['domestic_market', 'productive_base', 'trade_power', 'financial_buffer', 'population_base'],
        )
        self.assertIn('conversion_capacity', payload['meta']['models']['potential']['components'])
        self.assertIn('resource_optionality', payload['meta']['models']['potential']['components'])
        for pillar in payload['meta']['pillars'].values():
            self.assertEqual(len(pillar['inputs']), 3)
        for country in payload['countries']:
            self.assertEqual(set(country['models']), {'power', 'potential'})

    def test_china_and_india_are_in_the_strict_cohort(self):
        payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))
        iso3_codes = {country['iso3'] for country in payload['countries']}

        self.assertIn('CHN', iso3_codes)
        self.assertIn('IND', iso3_codes)

    def test_trade_links_only_point_to_real_world_bank_economies(self):
        payload = json.loads(DATA_PATH.read_text(encoding='utf-8'))

        for country in payload['countries']:
            self.assertNotIn('USP', {link['iso3'] for link in country['trade_links']})

    def test_old_world_lens_url_redirects_to_world_ledger(self):
        response = self.client.get('/world-lens/')

        self.assertRedirects(response, reverse('world_lens:dashboard'), status_code=301)
