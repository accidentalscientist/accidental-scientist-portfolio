import json
from unittest import SkipTest

from django.test import SimpleTestCase
from django.urls import reverse

from .views import DATA_PATH, DATA_PATH_V2


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


class WorldLedgerGigaV2Tests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not DATA_PATH_V2.is_file():
            raise SkipTest('Giga Dataset v2 has not been generated yet.')
        cls.payload = json.loads(DATA_PATH_V2.read_text(encoding='utf-8'))

    def test_dashboard_embeds_the_v2_dataset_and_switcher(self):
        response = self.client.get(reverse('world_lens:dashboard'))

        self.assertContains(response, 'world-lens-data-v2')
        self.assertContains(response, 'Giga v2')

    def test_giga_v2_expands_to_ten_pillars_per_model(self):
        self.assertEqual(self.payload['meta']['dataset'], 'Giga Dataset version 2.0')
        self.assertEqual(self.payload['meta']['cohort_count'], 60)
        self.assertEqual(len(self.payload['countries']), 60)
        self.assertEqual(len(self.payload['meta']['models']['power']['components']), 10)
        self.assertEqual(len(self.payload['meta']['models']['potential']['components']), 10)
        for pillar_key in self.payload['meta']['models']['power']['components'] + self.payload['meta']['models']['potential']['components']:
            self.assertEqual(len(self.payload['meta']['pillars'][pillar_key]['inputs']), 3)

    def test_china_and_india_remain_in_the_v2_cohort(self):
        iso3_codes = {country['iso3'] for country in self.payload['countries']}

        self.assertIn('CHN', iso3_codes)
        self.assertIn('IND', iso3_codes)

    def test_military_panel_is_present_and_unscored(self):
        for country in self.payload['countries']:
            self.assertIn('military', country)
            self.assertNotIn('military', country['models'])

    def test_sipri_is_declared_as_a_source(self):
        source_names = {source['name'] for source in self.payload['meta']['sources']}

        self.assertIn('SIPRI Arms Transfers Database', source_names)

    def test_approximated_values_are_explicitly_flagged(self):
        for country in self.payload['countries']:
            for model in country['models'].values():
                for component in model['components'].values():
                    for item in component['inputs'].values():
                        if item.get('approximated'):
                            self.assertIn('approximation_basis', item)
                            self.assertGreater(len(item['approximation_basis']), 0)
