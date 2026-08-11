from django.test import SimpleTestCase

from nem_battery_explorer.insights import opportunity_benchmark


class OpportunityBenchmarkTests(SimpleTestCase):
    def test_benchmark_charges_low_and_discharges_high_with_same_storage_boundary(self):
        rows = [
            {'time': '00:05', 'rrp': 0, 'storage_mwh': 50, 'scada_mw': 0, 'energy_value': 0},
            {'time': '00:10', 'rrp': 200, 'storage_mwh': 50, 'scada_mw': 0, 'energy_value': 0},
        ]

        result = opportunity_benchmark(rows, power_mw=100, capacity_mwh=100)

        self.assertLess(result['rows'][0]['benchmark_mw'], 0)
        self.assertGreater(result['rows'][1]['benchmark_mw'], 0)
        self.assertGreater(result['benchmark_value'], 0)
        self.assertLessEqual(abs(result['rows'][0]['benchmark_mw']), 100)
        self.assertLessEqual(abs(result['rows'][1]['benchmark_mw']), 100)

    def test_actual_value_and_capture_ratio_are_reported_separately(self):
        rows = [
            {'time': '00:05', 'rrp': -50, 'storage_mwh': 50, 'scada_mw': -10, 'energy_value': 40},
            {'time': '00:10', 'rrp': 150, 'storage_mwh': 50, 'scada_mw': 10, 'energy_value': 120},
        ]

        result = opportunity_benchmark(rows, power_mw=100, capacity_mwh=100)

        self.assertEqual(result['actual_value'], 160)
        self.assertIsNotNone(result['capture_ratio'])
        self.assertAlmostEqual(result['capture_pct'], result['capture_ratio'] * 100)
