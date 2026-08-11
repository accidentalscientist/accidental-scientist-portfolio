from types import SimpleNamespace

from django.test import SimpleTestCase

from nem_battery_explorer.calculations import calculate_interval, summarise_day


class IntervalCalculationTests(SimpleTestCase):
    def test_discharge_energy_and_fcas_value_use_five_minute_interval(self):
        result = calculate_interval(
            scada_mw=120,
            rrp=100,
            fcas_enablement={'raise_6s': 12},
            fcas_prices={'raise_6s': 50},
            storage_mwh=150,
            capacity_mwh=200,
        )

        self.assertAlmostEqual(result['discharge_mwh'], 10)
        self.assertAlmostEqual(result['energy_market_value'], 1000)
        self.assertAlmostEqual(result['gross_fcas_value'], 50)
        self.assertAlmostEqual(result['observable_gross_value'], 1050)

    def test_negative_price_charging_creates_positive_market_value(self):
        result = calculate_interval(
            scada_mw=-60,
            rrp=-100,
            fcas_enablement={},
            fcas_prices={},
            storage_mwh=100,
            capacity_mwh=200,
        )

        self.assertAlmostEqual(result['charge_mwh'], 5)
        self.assertAlmostEqual(result['charging_cost'], -500)
        self.assertAlmostEqual(result['energy_market_value'], 500)
        self.assertAlmostEqual(result['observable_gross_value'], 500)

    def test_public_capacity_exceedance_is_flagged_not_clipped(self):
        result = calculate_interval(
            scada_mw=0,
            rrp=0,
            fcas_enablement={},
            fcas_prices={},
            storage_mwh=210,
            capacity_mwh=200,
        )

        self.assertIn('storage_above_public_capacity', result['quality_flags'])


class DailySummaryTests(SimpleTestCase):
    def test_complete_day_has_288_intervals_and_published_cycle_convention(self):
        rows = [
            SimpleNamespace(
                scada_mw=100,
                energy_storage_mwh=150,
                charge_mwh=0,
                discharge_mwh=100 / 12,
                charging_cost=0,
                discharge_value=100,
                energy_market_value=100,
                gross_fcas_value=10,
                observable_gross_value=110,
                quality_flags=[],
            )
            for _ in range(288)
        ]

        summary = summarise_day(rows, capacity_mwh=400)

        self.assertEqual(summary['quality_status'], 'complete')
        self.assertAlmostEqual(summary['discharge_mwh'], 2400)
        self.assertAlmostEqual(summary['equivalent_cycles'], 6)
        self.assertAlmostEqual(summary['capture_price'], 12)

    def test_missing_interval_makes_day_partial(self):
        rows = [
            SimpleNamespace(
                scada_mw=0,
                energy_storage_mwh=100,
                charge_mwh=0,
                discharge_mwh=0,
                charging_cost=0,
                discharge_value=0,
                energy_market_value=0,
                gross_fcas_value=0,
                observable_gross_value=0,
                quality_flags=[],
            )
            for _ in range(287)
        ]

        summary = summarise_day(rows, capacity_mwh=200)

        self.assertEqual(summary['quality_status'], 'partial')
        self.assertIn('Expected 288 unit dispatch intervals; found 287.', summary['quality_notes'])

    def test_multi_unit_day_uses_unit_interval_expectation(self):
        rows = [
            SimpleNamespace(
                scada_mw=0,
                energy_storage_mwh=100,
                charge_mwh=0,
                discharge_mwh=0,
                charging_cost=0,
                discharge_value=0,
                energy_market_value=0,
                gross_fcas_value=0,
                observable_gross_value=0,
                quality_flags=[],
            )
            for _ in range(576)
        ]

        summary = summarise_day(rows, capacity_mwh=400, expected_intervals=576)

        self.assertEqual(summary['quality_status'], 'complete')
        self.assertEqual(summary['interval_count'], 576)

    def test_capacity_advisory_does_not_make_complete_coverage_partial(self):
        rows = [
            SimpleNamespace(
                scada_mw=0,
                energy_storage_mwh=205,
                charge_mwh=0,
                discharge_mwh=0,
                charging_cost=0,
                discharge_value=0,
                energy_market_value=0,
                gross_fcas_value=0,
                observable_gross_value=0,
                quality_flags=['storage_above_public_capacity'],
            )
            for _ in range(288)
        ]

        summary = summarise_day(rows, capacity_mwh=200)

        self.assertEqual(summary['quality_status'], 'complete')
        self.assertIn('storage above public capacity', summary['quality_notes'])
