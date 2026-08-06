"""Tests for the Price Predictor Lab.

The bias here is toward the things that would be embarrassing to get wrong
in public: interval alignment, market time, leakage, and the arithmetic
behind any number the page publishes. The chart rendering is not tested;
the claims are.
"""

from datetime import datetime, timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from . import forecasting as fc
from . import services
from .constants import NEM_TZ
from .ingest import interval_end_for, month_range, parse_price_csv, IngestError
from .models import ForecastRun, RegionPrice, RegionWeather

WEEK = timedelta(days=7)
HALF_HOUR = timedelta(minutes=30)


def nem(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=NEM_TZ)


# ── Interval alignment and market time ────────────────────────────────

class IntervalAlignmentTests(SimpleTestCase):
    def test_five_minute_stamps_round_up_to_their_containing_half_hour(self):
        # AEMO stamps an interval with its END, so 00:05 belongs to 00:30.
        self.assertEqual(interval_end_for(nem(2026, 6, 1, 0, 5)), nem(2026, 6, 1, 0, 30))
        self.assertEqual(interval_end_for(nem(2026, 6, 1, 0, 25)), nem(2026, 6, 1, 0, 30))

    def test_a_stamp_already_on_the_boundary_is_left_alone(self):
        self.assertEqual(interval_end_for(nem(2026, 6, 1, 0, 30)), nem(2026, 6, 1, 0, 30))
        self.assertEqual(interval_end_for(nem(2026, 6, 1, 0, 0)), nem(2026, 6, 1, 0, 0))

    def test_stamps_past_the_half_hour_roll_into_the_next_one(self):
        self.assertEqual(interval_end_for(nem(2026, 6, 1, 0, 35)), nem(2026, 6, 1, 1, 0))
        self.assertEqual(interval_end_for(nem(2026, 6, 1, 23, 35)), nem(2026, 6, 2, 0, 0))

    def test_market_time_is_a_fixed_offset_and_ignores_daylight_saving(self):
        # Australia/Sydney would be UTC+11 in January. NEM time never is.
        january = nem(2026, 1, 15, 12, 0)
        july = nem(2026, 7, 15, 12, 0)
        self.assertEqual(january.utcoffset(), timedelta(hours=10))
        self.assertEqual(july.utcoffset(), timedelta(hours=10))


class WeekSlotTests(SimpleTestCase):
    def test_the_midnight_interval_belongs_to_the_previous_day(self):
        # The interval stamped Tuesday 00:00 covers Monday 23:30-00:00, so it
        # is Monday's last slot, not Tuesday's first.
        monday_last = fc.week_slot(nem(2026, 8, 4, 0, 0))   # Tue 00:00 stamp
        self.assertEqual(monday_last, 47)

    def test_slots_wrap_a_full_week(self):
        monday_first = fc.week_slot(nem(2026, 8, 3, 0, 30))  # Mon 00:00-00:30
        self.assertEqual(monday_first, 0)
        self.assertEqual(fc.week_slot(nem(2026, 8, 3, 0, 30) + WEEK), monday_first)

    def test_the_same_half_hour_a_week_apart_shares_a_slot(self):
        moment = nem(2026, 8, 5, 18, 30)
        self.assertEqual(fc.week_slot(moment), fc.week_slot(moment + WEEK))

    def test_bands_are_read_from_the_interval_start(self):
        # 17:00 stamp covers 16:30-17:00, which is still the afternoon.
        self.assertEqual(fc.band_for(nem(2026, 8, 5, 17, 0)), 'afternoon')
        self.assertEqual(fc.band_for(nem(2026, 8, 5, 17, 30)), 'evening')


class MarketTimeCalendarTests(SimpleTestCase):
    """Calendar features must be read in market time, never in UTC.

    Django stores and returns datetimes in UTC. An interval that is 00:30 on
    Tuesday in the market is 14:30 on Monday in UTC, so reading `.hour` or
    `.weekday()` off a raw database value shifts every calendar feature by
    ten hours and lands the evening peak's coefficients on pre-dawn data.
    """

    def test_a_utc_valued_interval_resolves_to_its_market_hour(self):
        # 2025-06-30 14:30 UTC is 2025-07-01 00:30 in the market.
        from datetime import timezone as dt_timezone
        utc_value = datetime(2025, 6, 30, 14, 30, tzinfo=dt_timezone.utc)

        start = fc.interval_start(utc_value)

        self.assertEqual(start.hour, 0)
        self.assertEqual(start.minute, 0)
        self.assertEqual(start.day, 1)
        self.assertEqual(start.month, 7)

    def test_a_utc_valued_interval_lands_in_the_right_band(self):
        from datetime import timezone as dt_timezone
        utc_value = datetime(2025, 6, 30, 14, 30, tzinfo=dt_timezone.utc)

        # Midnight in the market is overnight, not the UTC-hour-14 midday.
        self.assertEqual(fc.band_for(utc_value), 'overnight')

    def test_the_weekday_follows_the_market_date_not_the_utc_date(self):
        from datetime import timezone as dt_timezone
        # 2025-06-30 is a Monday in UTC; 2025-07-01 is a Tuesday in the market.
        utc_value = datetime(2025, 6, 30, 14, 30, tzinfo=dt_timezone.utc)

        self.assertEqual(fc.interval_start(utc_value).weekday(), 1)

    def test_market_time_and_utc_inputs_agree_on_the_same_instant(self):
        from datetime import timezone as dt_timezone
        market = nem(2026, 8, 5, 18, 30)
        same_instant_utc = market.astimezone(dt_timezone.utc)

        self.assertEqual(fc.band_for(market), fc.band_for(same_instant_utc))
        self.assertEqual(fc.week_slot(market), fc.week_slot(same_instant_utc))


# ── CSV parsing ───────────────────────────────────────────────────────

class PriceCsvTests(SimpleTestCase):
    def test_six_five_minute_rows_average_into_one_half_hour(self):
        rows = ['REGION,SETTLEMENTDATE,TOTALDEMAND,RRP,PERIODTYPE']
        for index, minute in enumerate([5, 10, 15, 20, 25, 30]):
            rows.append(f'NSW1,2026/06/01 00:{minute:02d}:00,8000,{10 * (index + 1)},TRADE')

        parsed, report = parse_price_csv('\n'.join(rows))

        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['interval_end'], nem(2026, 6, 1, 0, 30))
        self.assertAlmostEqual(parsed[0]['rrp'], 35.0)  # mean of 10..60
        self.assertEqual(report['regions'], ['NSW1'])

    def test_thirty_minute_era_rows_pass_through_unchanged(self):
        text = (
            'REGION,SETTLEMENTDATE,TOTALDEMAND,RRP,PERIODTYPE\n'
            'NSW1,2019/06/01 00:30:00,8533.47,92.24,TRADE\n'
            'NSW1,2019/06/01 01:00:00,8277.33,87.72,TRADE\n'
        )
        parsed, _ = parse_price_csv(text)

        self.assertEqual(len(parsed), 2)
        self.assertAlmostEqual(parsed[0]['rrp'], 92.24)

    def test_unreadable_rows_are_skipped_not_fatal(self):
        text = (
            'REGION,SETTLEMENTDATE,TOTALDEMAND,RRP,PERIODTYPE\n'
            'NSW1,2026/06/01 00:30:00,8000,50,TRADE\n'
            'NSW1,not-a-date,8000,50,TRADE\n'
            'NSW1,2026/06/01 01:00:00,8000,oops,TRADE\n'
        )
        parsed, report = parse_price_csv(text)

        self.assertEqual(len(parsed), 1)
        self.assertEqual(report['skipped'], 2)

    def test_a_file_missing_required_columns_is_rejected(self):
        with self.assertRaises(IngestError):
            parse_price_csv('REGION,SETTLEMENTDATE\nNSW1,2026/06/01 00:30:00\n')

    def test_month_range_walks_backwards_across_a_year_boundary(self):
        self.assertEqual(
            month_range(datetime(2026, 2, 15).date(), 4),
            ['202511', '202512', '202601', '202602'],
        )


# ── Forecast models ───────────────────────────────────────────────────

class SeasonalNaiveTests(SimpleTestCase):
    def test_it_repeats_the_price_from_exactly_one_week_earlier(self):
        origin = nem(2026, 8, 2)
        history = {origin - WEEK + HALF_HOUR * i: float(i) for i in range(1, 337)}

        predictions = fc.seasonal_naive(history, origin, horizon_days=7)

        self.assertEqual(len(predictions), 336)
        self.assertEqual(predictions[origin + HALF_HOUR], 1.0)
        self.assertEqual(predictions[origin + HALF_HOUR * 336], 336.0)

    def test_it_predicts_nothing_where_last_week_has_a_hole(self):
        origin = nem(2026, 8, 2)
        history = {origin - WEEK + HALF_HOUR: 50.0}

        predictions = fc.seasonal_naive(history, origin, horizon_days=7)

        self.assertEqual(list(predictions), [origin + HALF_HOUR])

    def test_predictions_are_held_at_the_market_floor(self):
        origin = nem(2026, 8, 2)
        history = {origin - WEEK + HALF_HOUR: -5000.0}

        predictions = fc.seasonal_naive(history, origin, horizon_days=7)

        self.assertEqual(predictions[origin + HALF_HOUR], -1000.0)


class RollingMedianTests(SimpleTestCase):
    def test_a_single_spike_week_does_not_move_the_median(self):
        origin = nem(2026, 8, 2)
        target = origin + HALF_HOUR
        history = {
            target - WEEK: 15000.0,   # the spike week
            target - WEEK * 2: 50.0,
            target - WEEK * 3: 52.0,
            target - WEEK * 4: 48.0,
        }

        predictions = fc.rolling_median(history, origin, horizon_days=7, weeks=4)

        self.assertAlmostEqual(predictions[target], 51.0)  # median of 48,50,52,15000
        # The naive baseline, by contrast, copies the spike straight through.
        self.assertEqual(fc.seasonal_naive(history, origin, 7)[target], 15000.0)


class DegreeSplitTests(SimpleTestCase):
    def test_a_warm_day_is_all_cooling_and_no_heating(self):
        self.assertAlmostEqual(fc.cooling_degrees(28.0), 10.0)
        self.assertAlmostEqual(fc.heating_degrees(28.0), 0.0)

    def test_a_cold_day_is_all_heating_and_no_cooling(self):
        self.assertAlmostEqual(fc.cooling_degrees(8.0), 0.0)
        self.assertAlmostEqual(fc.heating_degrees(8.0), 10.0)

    def test_the_comfort_base_itself_needs_neither(self):
        self.assertAlmostEqual(fc.cooling_degrees(fc.COMFORT_BASE_C), 0.0)
        self.assertAlmostEqual(fc.heating_degrees(fc.COMFORT_BASE_C), 0.0)


class TemperatureModelTests(SimpleTestCase):
    def test_slope_is_pinned_through_the_origin(self):
        # y = 3x exactly; an intercept-free fit must recover 3.
        self.assertAlmostEqual(fc.slope_through_origin([(1, 3), (2, 6), (4, 12)]), 3.0)

    def test_two_variable_fit_separates_the_two_drivers(self):
        # y = 2*x1 + 5*x2 exactly.
        triples = [(1, 0, 2), (0, 1, 5), (2, 1, 9), (3, 2, 16), (1, 4, 22)]
        cooling, heating = fc.two_slopes_through_origin(triples)

        self.assertAlmostEqual(cooling, 2.0, places=6)
        self.assertAlmostEqual(heating, 5.0, places=6)

    def test_a_collinear_band_falls_back_rather_than_dividing_by_zero(self):
        # Only the heating side ever varies: cooling must not explode.
        cooling, heating = fc.two_slopes_through_origin([(0, 1, 4), (0, 2, 8), (0, 3, 12)])

        self.assertAlmostEqual(cooling, 0.0)
        self.assertAlmostEqual(heating, 4.0)

    def test_no_temperature_change_returns_the_naive_answer(self):
        origin = nem(2026, 8, 2)
        target = origin + HALF_HOUR
        history = {target - WEEK: 80.0}
        temps = {target - WEEK: 25.0}
        target_temps = {target: 25.0}

        predictions = fc.temperature_adjusted(
            history, temps, target_temps,
            {'overnight': {'cooling': 5.0, 'heating': 3.0}}, origin, horizon_days=7
        )

        self.assertAlmostEqual(predictions[target], 80.0)

    def test_a_hotter_summer_week_raises_the_prediction(self):
        origin = nem(2026, 8, 2)
        target = origin + HALF_HOUR
        history = {target - WEEK: 80.0}
        temps = {target - WEEK: 24.0}        # 6 cooling degrees
        target_temps = {target: 30.0}        # 12 cooling degrees, so +6

        predictions = fc.temperature_adjusted(
            history, temps, target_temps,
            {'overnight': {'cooling': 4.0, 'heating': 9.0}}, origin, horizon_days=7
        )

        self.assertAlmostEqual(predictions[target], 80.0 + 6 * 4.0)

    def test_a_colder_winter_week_also_raises_the_prediction(self):
        # The whole point of the split: cold moves price the SAME direction
        # as heat, which a single linear coefficient cannot express.
        origin = nem(2026, 8, 2)
        target = origin + HALF_HOUR
        history = {target - WEEK: 80.0}
        temps = {target - WEEK: 12.0}        # 6 heating degrees
        target_temps = {target: 6.0}         # 12 heating degrees, so +6

        predictions = fc.temperature_adjusted(
            history, temps, target_temps,
            {'overnight': {'cooling': 4.0, 'heating': 9.0}}, origin, horizon_days=7
        )

        self.assertAlmostEqual(predictions[target], 80.0 + 6 * 9.0)

    def test_missing_temperature_degrades_to_the_baseline(self):
        origin = nem(2026, 8, 2)
        target = origin + HALF_HOUR
        history = {target - WEEK: 80.0}

        predictions = fc.temperature_adjusted(
            history, {}, {}, {'overnight': {'cooling': 4.0, 'heating': 9.0}}, origin, 7
        )

        self.assertAlmostEqual(predictions[target], 80.0)

    def test_a_band_with_too_little_evidence_is_pinned_to_zero(self):
        origin = nem(2026, 8, 2)
        history, temps = {}, {}
        for i in range(1, 20):   # far fewer than MIN_SAMPLES_PER_BAND
            moment = origin - WEEK * 2 + HALF_HOUR * i
            history[moment] = 50.0
            history[moment + WEEK] = 60.0
            temps[moment] = 15.0
            temps[moment + WEEK] = 20.0

        betas, diagnostics = fc.fit_temperature_betas(history, temps)

        for band, value in betas.items():
            self.assertEqual(value['cooling'], 0.0)
            self.assertEqual(value['heating'], 0.0)
            self.assertFalse(diagnostics[band]['fitted'])

    def test_opposite_seasonal_responses_are_both_recovered(self):
        """The regression test for the defect that motivated the split.

        History alternates between hot weeks and cold weeks. Price rises
        $6/MWh per cooling degree AND $9/MWh per heating degree. A single
        linear coefficient would average these toward zero; the split must
        return both with their own sign.
        """
        origin = nem(2026, 8, 2)
        history, temps = {}, {}
        for week in range(52):
            for slot in range(6):   # overnight band
                moment = origin - WEEK * (week + 1) + HALF_HOUR * (slot + 1)
                # Swing either side of the 18C base.
                temperature = 26.0 + (week % 5) if week % 2 else 10.0 - (week % 5)
                temps[moment] = temperature
                history[moment] = (
                    40.0
                    + 6.0 * fc.cooling_degrees(temperature)
                    + 9.0 * fc.heating_degrees(temperature)
                )

        betas, diagnostics = fc.fit_temperature_betas(history, temps)

        self.assertTrue(diagnostics['overnight']['fitted'])
        self.assertAlmostEqual(betas['overnight']['cooling'], 6.0, places=4)
        self.assertAlmostEqual(betas['overnight']['heating'], 9.0, places=4)


class AsinhInversionTests(SimpleTestCase):
    """The asinh/sinh round trip must never be allowed to run away.

    The target is compressed with asinh and inverted with sinh. sinh grows
    exponentially, so a model that can extrapolate in transformed space turns
    a small overshoot into an astronomical price. A neural network did
    exactly that: an unbounded Victorian run averaged $3.8 billion per MWh.
    """

    def test_sinh_amplifies_a_small_overshoot_enormously(self):
        import math
        # A plausible target: $200/MWh is asinh ~ 6.0.
        self.assertAlmostEqual(math.asinh(200.0), 5.99, places=1)
        # Overshooting by 10 units in transformed space is not a small error.
        self.assertGreater(math.sinh(16.0), 4_000_000)

    def test_predictions_are_bounded_by_the_observed_training_range(self):
        from . import tree_models
        if not tree_models.sklearn_available():
            self.skipTest('scikit-learn not installed')

        origin = nem(2026, 8, 2)
        prices, temps, demands = {}, {}, {}
        for i in range(6 * 336):
            interval = origin - timedelta(minutes=30 * i)
            prices[interval] = 60.0 + (i % 40)
            temps[interval] = 12.0 + (i % 15)
            demands[interval] = 8000.0 + (i % 500)

        targets = fc.target_intervals(origin, 7)
        target_temps = {t: 19.0 for t in targets}

        predictions, diagnostics = tree_models.fit_and_predict(
            tree_models.NEURAL_NETWORK, prices, temps, demands,
            targets, origin, target_temps,
        )

        self.assertTrue(diagnostics['trained'])
        observed_low, observed_high = diagnostics['training_price_range']
        for value in predictions.values():
            self.assertGreaterEqual(value, fc.MARKET_PRICE_FLOOR)
            self.assertLessEqual(value, observed_high)
        self.assertLessEqual(max(predictions.values()), 200.0)


class ScoringTests(SimpleTestCase):
    def test_mean_and_median_diverge_when_one_interval_spikes(self):
        actuals = {nem(2026, 8, 3, 0, 30) + HALF_HOUR * i: 50.0 for i in range(10)}
        predictions = dict(actuals)
        spike = nem(2026, 8, 3, 0, 30)
        predictions[spike] = 5050.0   # one catastrophic miss

        result = fc.score(predictions, actuals)

        self.assertEqual(result['intervals'], 10)
        self.assertAlmostEqual(result['mae'], 500.0)   # dragged by the spike
        self.assertAlmostEqual(result['medae'], 0.0)   # unmoved
        self.assertAlmostEqual(result['max_error'], 5000.0)

    def test_skill_is_positive_when_the_model_beats_the_baseline(self):
        model = {'mae': 25.0}
        baseline = {'mae': 50.0}
        self.assertAlmostEqual(fc.skill(model, baseline), 0.5)

    def test_skill_is_negative_when_the_model_loses(self):
        self.assertAlmostEqual(fc.skill({'mae': 75.0}, {'mae': 50.0}), -0.5)

    def test_intervals_without_an_actual_are_not_scored(self):
        actuals = {nem(2026, 8, 3, 0, 30): 50.0}
        predictions = {
            nem(2026, 8, 3, 0, 30): 60.0,
            nem(2026, 8, 3, 1, 0): 999.0,   # week not settled yet
        }
        self.assertEqual(fc.score(predictions, actuals)['intervals'], 1)


class TargetIntervalTests(SimpleTestCase):
    def test_the_first_target_is_after_the_origin_never_on_it(self):
        origin = nem(2026, 8, 2)
        targets = fc.target_intervals(origin, 7)

        self.assertEqual(len(targets), 336)
        self.assertEqual(targets[0], origin + HALF_HOUR)
        self.assertGreater(targets[0], origin)
        self.assertEqual(targets[-1], origin + timedelta(days=7))


# ── Database-facing behaviour ─────────────────────────────────────────

class OriginTests(TestCase):
    def test_a_sunday_resolves_to_its_own_midnight(self):
        self.assertEqual(
            services.most_recent_sunday(nem(2026, 8, 2, 14, 30)),
            nem(2026, 8, 2, 0, 0),
        )

    def test_a_midweek_moment_walks_back_to_the_sunday_just_gone(self):
        self.assertEqual(
            services.most_recent_sunday(nem(2026, 8, 5, 9, 0)),   # Wednesday
            nem(2026, 8, 2, 0, 0),
        )

    def test_a_saturday_does_not_jump_forward_to_tomorrow(self):
        self.assertEqual(
            services.most_recent_sunday(nem(2026, 8, 8, 23, 59)),  # Saturday
            nem(2026, 8, 2, 0, 0),
        )


class UpsertTests(TestCase):
    def test_reingesting_a_month_updates_rather_than_duplicates(self):
        rows = [{
            'region': 'NSW1', 'interval_end': nem(2026, 6, 1, 0, 30),
            'rrp': 50.0, 'total_demand': 8000.0,
        }]
        services.upsert_prices(rows)
        rows[0]['rrp'] = 61.0
        services.upsert_prices(rows)

        self.assertEqual(RegionPrice.objects.count(), 1)
        self.assertAlmostEqual(RegionPrice.objects.get().rrp, 61.0)

    def test_one_regions_upload_never_disturbs_another_at_the_same_interval(self):
        interval = nem(2026, 6, 1, 0, 30)
        services.upsert_prices([
            {'region': 'NSW1', 'interval_end': interval, 'rrp': 50.0, 'total_demand': 8000.0},
            {'region': 'VIC1', 'interval_end': interval, 'rrp': 30.0, 'total_demand': 5000.0},
        ])

        # Re-upload NSW alone, as a single-region file would.
        services.upsert_prices([
            {'region': 'NSW1', 'interval_end': interval, 'rrp': 55.0, 'total_demand': 8100.0},
        ])

        self.assertEqual(RegionPrice.objects.count(), 2)
        self.assertAlmostEqual(RegionPrice.objects.get(region='VIC1').rrp, 30.0)


class LeakageTests(TestCase):
    """The one rule at this horizon: nothing after the origin may inform a run."""

    def setUp(self):
        self.origin = nem(2026, 8, 2)
        rows = []
        # Four weeks of history behind the origin, plus a week ahead of it
        # carrying an absurd price the model must never be able to see.
        # i starts at 0: the interval stamped exactly at the origin covers
        # 23:30-00:00 and is settled history, not the future.
        for i in range(4 * 336):
            rows.append({
                'region': 'NSW1',
                'interval_end': self.origin - timedelta(minutes=30 * i),
                'rrp': 100.0,
                'total_demand': 8000.0,
            })
        for i in range(1, 337):
            rows.append({
                'region': 'NSW1',
                'interval_end': self.origin + timedelta(minutes=30 * i),
                'rrp': 99999.0,
                'total_demand': 8000.0,
            })
        services.upsert_prices(rows)

    def test_the_history_a_run_sees_stops_at_the_origin(self):
        history = services.price_map('NSW1', self.origin - timedelta(weeks=52), self.origin)

        self.assertTrue(all(interval <= self.origin for interval in history))
        self.assertNotIn(99999.0, set(history.values()))

    def test_predictions_never_reproduce_a_price_from_after_the_origin(self):
        results = services.build_forecasts('NSW1', self.origin, horizon_days=7)

        for model_key, result in results.items():
            values = set(result['predictions'].values())
            self.assertNotIn(99999.0, values, f'{model_key} leaked a future price')
            self.assertTrue(all(v == 100.0 for v in values), f'{model_key} produced {values}')

    def test_a_run_without_forecast_temperature_is_flagged_not_silently_backfilled(self):
        # Observed temperature exists for the target week; forecast does not.
        services.upsert_weather('NSW1', RegionWeather.OBSERVED, {
            self.origin + timedelta(minutes=30 * i): 20.0 for i in range(1, 337)
        })

        results = services.build_forecasts('NSW1', self.origin, horizon_days=7)

        self.assertEqual(
            results[fc.TEMP_ADJUSTED]['temperature_source'],
            ForecastRun.SOURCE_OBSERVED_FALLBACK,
        )
        run = services.save_forecast_run(
            'NSW1', fc.TEMP_ADJUSTED, self.origin, results[fc.TEMP_ADJUSTED]
        )
        self.assertFalse(run.is_leakage_safe)

    def test_a_run_using_real_forecast_temperature_is_marked_clean(self):
        services.upsert_weather('NSW1', RegionWeather.FORECAST, {
            self.origin + timedelta(minutes=30 * i): 20.0 for i in range(1, 337)
        })

        results = services.build_forecasts('NSW1', self.origin, horizon_days=7)
        run = services.save_forecast_run(
            'NSW1', fc.TEMP_ADJUSTED, self.origin, results[fc.TEMP_ADJUSTED]
        )

        self.assertEqual(run.temperature_source, ForecastRun.SOURCE_FORECAST)
        self.assertTrue(run.is_leakage_safe)


class ForecastRunTests(TestCase):
    def setUp(self):
        self.origin = nem(2026, 8, 2)
        # i starts at 0 so the interval ending exactly on the origin is
        # present: seasonal naive needs it to reach the final target.
        services.upsert_prices([
            {
                'region': 'NSW1',
                'interval_end': self.origin - timedelta(minutes=30 * i),
                'rrp': 100.0,
                'total_demand': 8000.0,
            }
            for i in range(4 * 336)
        ])

    def test_generating_a_run_stores_every_model_with_its_points(self):
        runs = services.generate_and_save('NSW1', self.origin, horizon_days=7)

        # Derived from the registry so adding a model does not break the test.
        self.assertEqual(len(runs), len(fc.MODEL_ORDER))
        self.assertEqual({r.model_key for r in runs}, set(fc.MODEL_ORDER))

        # The price-only models cover the whole horizon from price history
        # alone. The tree models need weather and a minimum training set, so
        # on a fixture with neither they correctly publish nothing at all
        # rather than imputing their way to a full week.
        for run in runs:
            if run.model_key in fc.TREE_MODELS:
                self.assertEqual(run.points.count(), 0)
            else:
                self.assertEqual(run.points.count(), 336)

    def test_rerunning_the_same_origin_replaces_rather_than_duplicates(self):
        services.generate_and_save('NSW1', self.origin, horizon_days=7)
        services.generate_and_save('NSW1', self.origin, horizon_days=7)

        self.assertEqual(
            ForecastRun.objects.filter(region='NSW1', issued_at=self.origin).count(),
            len(fc.MODEL_ORDER),
        )

    def test_a_run_is_unscored_while_its_week_is_still_in_the_future(self):
        runs = services.generate_and_save('NSW1', self.origin, horizon_days=7)
        # No actuals exist past the origin at all.
        self.assertIsNone(services.score_run(runs[0]))

    def test_a_finished_week_scores_against_what_actually_cleared(self):
        runs = services.generate_and_save('NSW1', self.origin, horizon_days=7)
        services.upsert_prices([
            {
                'region': 'NSW1',
                'interval_end': self.origin + timedelta(minutes=30 * i),
                'rrp': 120.0,      # every model predicted 100
                'total_demand': 8000.0,
            }
            for i in range(1, 337)
        ])

        naive = next(r for r in runs if r.model_key == fc.SEASONAL_NAIVE)
        result = services.score_run(naive)

        self.assertEqual(result['intervals'], 336)
        self.assertAlmostEqual(result['mae'], 20.0)
        self.assertAlmostEqual(result['medae'], 20.0)


# ── The page ──────────────────────────────────────────────────────────

class LabViewTests(TestCase):
    def test_the_empty_state_explains_how_to_load_data(self):
        response = self.client.get(reverse('nem_price_lab:lab'))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['has_data'])
        self.assertContains(response, 'No price data loaded yet')
        self.assertContains(response, 'ingest_nem_prices')

    def test_the_page_renders_once_prices_exist(self):
        origin = nem(2026, 8, 2)
        services.upsert_prices([
            {
                'region': 'NSW1',
                'interval_end': origin - timedelta(minutes=30 * i),
                'rrp': 100.0 if i % 3 else -20.0,
                'total_demand': 8000.0,
            }
            for i in range(1, 337)
        ])

        response = self.client.get(reverse('nem_price_lab:lab'))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['has_data'])
        self.assertEqual(response.context['default_region'], 'NSW1')
        self.assertContains(response, 'NEM Price Predictor Lab')
        self.assertContains(response, 'plab-data')

    def test_negative_price_share_is_reported_not_averaged_away(self):
        origin = nem(2026, 8, 2)
        rows = []
        for i in range(1, 337):
            rows.append({
                'region': 'NSW1',
                'interval_end': origin - timedelta(minutes=30 * i),
                'rrp': -10.0 if i <= 84 else 100.0,   # exactly a quarter below zero
                'total_demand': 8000.0,
            })
        services.upsert_prices(rows)

        response = self.client.get(reverse('nem_price_lab:lab'))
        stats = response.context['regions_json']['NSW1']['stats']

        self.assertAlmostEqual(stats['negative_pct'], 25.0)
        self.assertAlmostEqual(stats['low'], -10.0)

    def test_the_lab_route_does_not_collide_with_the_fuel_mix_dashboard(self):
        self.assertEqual(reverse('nem_price_lab:lab'), '/nem/price-lab/')
        self.assertEqual(reverse('nem_dashboard:nem_dashboard'), '/nem/')
        self.assertEqual(self.client.get('/nem/price-lab/').status_code, 200)

    def test_the_page_opens_on_the_market_wide_view_and_cycles(self):
        origin = nem(2026, 8, 2)
        _seed_two_regions(origin)
        services.rebuild_nem_aggregate()

        response = self.client.get(reverse('nem_price_lab:lab'))

        self.assertEqual(response.context['default_region'], 'NEM')
        self.assertTrue(response.context['auto_cycle'])
        self.assertEqual(response.context['region_order'][0], 'NEM')

    def test_pinning_a_region_by_query_suppresses_the_cycle(self):
        origin = nem(2026, 8, 2)
        _seed_two_regions(origin)
        services.rebuild_nem_aggregate()

        response = self.client.get(reverse('nem_price_lab:lab'), {'region': 'VIC1'})

        self.assertEqual(response.context['default_region'], 'VIC1')
        self.assertFalse(response.context['auto_cycle'])

    def test_the_baseline_and_temperature_model_are_shown_by_default(self):
        origin = nem(2026, 8, 2)
        _seed_two_regions(origin)

        response = self.client.get(reverse('nem_price_lab:lab'))
        defaults = {m['key'] for m in response.context['model_order'] if m['default_on']}

        self.assertEqual(defaults, {fc.SEASONAL_NAIVE, fc.TEMP_ADJUSTED})

    def test_history_window_is_ninety_days(self):
        from .views import DAYS_HISTORY
        self.assertEqual(DAYS_HISTORY, 90)


def _seed_two_regions(origin):
    """A week of settled data in two regions with different demand weights."""
    rows = []
    for i in range(336):
        interval = origin - timedelta(minutes=30 * i)
        rows.append({'region': 'NSW1', 'interval_end': interval,
                     'rrp': 100.0, 'total_demand': 8000.0})
        rows.append({'region': 'VIC1', 'interval_end': interval,
                     'rrp': 50.0, 'total_demand': 2000.0})
    services.upsert_prices(rows)


class NemAggregateTests(TestCase):
    def setUp(self):
        self.origin = nem(2026, 8, 2)
        _seed_two_regions(self.origin)

    def test_the_market_wide_price_is_demand_weighted_not_a_plain_mean(self):
        services.rebuild_nem_aggregate()

        row = RegionPrice.objects.get(region='NEM', interval_end=self.origin)

        # Plain mean would be 75. Demand-weighted is
        # (100*8000 + 50*2000) / 10000 = 90.
        self.assertAlmostEqual(row.rrp, 90.0)
        self.assertAlmostEqual(row.total_demand, 10000.0)

    def test_rebuilding_replaces_rather_than_accumulates(self):
        services.rebuild_nem_aggregate()
        first = RegionPrice.objects.filter(region='NEM').count()
        services.rebuild_nem_aggregate()

        self.assertEqual(RegionPrice.objects.filter(region='NEM').count(), first)

    def test_the_aggregate_never_folds_itself_back_in(self):
        services.rebuild_nem_aggregate()
        services.rebuild_nem_aggregate()

        row = RegionPrice.objects.get(region='NEM', interval_end=self.origin)
        self.assertAlmostEqual(row.rrp, 90.0)
        self.assertAlmostEqual(row.total_demand, 10000.0)

    def test_demand_shares_reflect_relative_size(self):
        shares = services.average_demand_shares()

        self.assertAlmostEqual(shares['NSW1'], 0.8)
        self.assertAlmostEqual(shares['VIC1'], 0.2)

    def test_forward_forecast_weather_aggregates_without_settled_demand(self):
        """Future intervals have no demand rows, so shares must carry them."""
        future = {self.origin + timedelta(minutes=30 * i): 20.0 for i in range(1, 337)}
        services.upsert_weather('NSW1', RegionWeather.FORECAST, future)
        services.upsert_weather('VIC1', RegionWeather.FORECAST,
                                {k: 10.0 for k in future})

        services.rebuild_nem_aggregate()

        aggregated = services.weather_map('NEM', RegionWeather.FORECAST)
        self.assertEqual(len(aggregated), 336)
        # Weighted by the 80/20 demand split, not averaged to 15.
        self.assertAlmostEqual(aggregated[self.origin + timedelta(minutes=30)], 18.0)

    def test_the_aggregate_is_forecastable_like_any_other_region(self):
        services.rebuild_nem_aggregate()

        runs = services.generate_and_save('NEM', self.origin, horizon_days=7)

        self.assertEqual(len(runs), len(fc.MODEL_ORDER))
        for run in runs:
            if run.model_key not in fc.TREE_MODELS:
                self.assertGreater(run.points.count(), 0)


class PerformanceSummaryTests(TestCase):
    def setUp(self):
        self.origin = nem(2026, 8, 2)
        services.upsert_prices([
            {'region': 'NSW1', 'interval_end': self.origin - timedelta(minutes=30 * i),
             'rrp': 100.0, 'total_demand': 8000.0}
            for i in range(4 * 336)
        ])

    def test_a_week_still_running_is_not_counted_as_complete(self):
        services.generate_and_save('NSW1', self.origin, horizon_days=7)
        # Only half the week has settled.
        services.upsert_prices([
            {'region': 'NSW1', 'interval_end': self.origin + timedelta(minutes=30 * i),
             'rrp': 120.0, 'total_demand': 8000.0}
            for i in range(1, 169)
        ])

        self.assertEqual(services.completed_origins('NSW1'), [])
        self.assertIsNone(services.performance_summary('NSW1'))

    def test_a_finished_week_produces_last_week_and_average_figures(self):
        services.generate_and_save('NSW1', self.origin, horizon_days=7)
        services.upsert_prices([
            {'region': 'NSW1', 'interval_end': self.origin + timedelta(minutes=30 * i),
             'rrp': 120.0, 'total_demand': 8000.0}
            for i in range(1, 337)
        ])

        summary = services.performance_summary('NSW1')
        naive = next(r for r in summary['rows'] if r['model_key'] == fc.SEASONAL_NAIVE)

        self.assertEqual(summary['weeks'], 1)
        self.assertEqual(naive['weeks'], 1)
        self.assertAlmostEqual(naive['last_week']['mae'], 20.0)
        self.assertAlmostEqual(naive['average_mae'], 20.0)
        # The baseline has no skill against itself.
        self.assertAlmostEqual(naive['average_skill'], 0.0)

    def test_the_average_spans_every_completed_week_not_just_the_last(self):
        earlier = self.origin - WEEK
        services.generate_and_save('NSW1', earlier, horizon_days=7)
        services.generate_and_save('NSW1', self.origin, horizon_days=7)
        # Settle both weeks at a price the naive model missed by 20.
        services.upsert_prices([
            {'region': 'NSW1', 'interval_end': self.origin + timedelta(minutes=30 * i),
             'rrp': 120.0, 'total_demand': 8000.0}
            for i in range(1, 337)
        ])

        summary = services.performance_summary('NSW1')

        self.assertEqual(summary['weeks'], 2)
        self.assertEqual(summary['first_origin'], earlier)
        self.assertEqual(summary['latest_origin'], self.origin)
