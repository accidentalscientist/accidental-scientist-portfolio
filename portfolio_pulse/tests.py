import io
from collections import Counter
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from . import metrics, sample_data
from .aggregate import build_dashboard_context
from .parsing import group_timeline_by_account, parse_snapshot, parse_timeline
from .scoring import BANDS, _band, portfolio_health, score_account, score_portfolio

TODAY = date(2026, 7, 30)


def _account(**overrides):
    base = {
        "account_id": "ACC-1",
        "account_name": "Acme Co",
        "segment": "Mid-Market",
        "industry": "Technology / SaaS",
        "csm_owner": "Jordan Reyes",
        "customer_since": date(2023, 1, 1),
        "product_tier": "Growth",
        "seats_purchased": 20,
        "contract_start": date(2025, 1, 1),
        "renewal_date": date(2028, 1, 1),
        "term_length_months": 36,
        "auto_renew": True,
        "entry_arr": 50_000.0,
        "current_arr": 120_000.0,
        "last_qbr_date": date(2026, 6, 1),
        "tickets_12mo": 4,
        "pct_high_priority": 10.0,
        "days_since_contact": 20,
        "overdue_flag": False,
        "seat_utilisation_pct": 75.0,
        "active_user_pct": 70.0,
        "arr_trend_pct": 0.0,
    }
    base.update(overrides)
    return base


def _timeline_rows(account_id="ACC-1", arrs=None, utils=None):
    arrs = arrs or [100_000.0, 100_000.0, 100_000.0]
    utils = utils or [75.0] * len(arrs)
    rows = []
    year, month = 2026, 1
    for arr, util in zip(arrs, utils):
        rows.append({
            "account_id": account_id,
            "month": date(year, month, 1),
            "arr": arr,
            "seat_utilisation_pct": util,
            "active_user_pct": util * 0.85,
            "tickets_opened": 1,
        })
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return rows


class ScoreAccountTests(TestCase):
    def test_healthy_account_scores_high(self):
        result = score_account(_account(), today=TODAY)
        self.assertEqual(result["band"], "Healthy")
        self.assertGreaterEqual(result["score"], 76)

    def test_missing_qbr_uses_full_customer_tenure(self):
        result = score_account(
            _account(last_qbr_date=None, customer_since=date(2020, 1, 1)),
            today=TODAY,
        )
        self.assertTrue(result["qbr_inferred"])
        self.assertEqual(result["days_since_qbr"], (TODAY - date(2020, 1, 1)).days)
        self.assertLess(result["data_completeness"], 100)
        self.assertIn("No QBR recorded", [driver["signal"] for driver in result["health_drivers"]])

    def test_one_year_contract_reduces_health(self):
        three_year = score_account(_account(term_length_months=36), today=TODAY)
        one_year = score_account(_account(term_length_months=12), today=TODAY)
        self.assertLess(one_year["score"], three_year["score"])

    def test_two_year_term_is_neutral_for_a_new_customer(self):
        new_customer = _account(
            customer_since=date(2026, 1, 1),
            contract_start=date(2026, 1, 15),
            term_length_months=24,
        )
        established_renewal = _account(
            customer_since=date(2020, 1, 1),
            contract_start=date(2026, 1, 1),
            term_length_months=24,
        )
        self.assertGreater(
            score_account(new_customer, TODAY)["score"],
            score_account(established_renewal, TODAY)["score"],
        )

    def test_renewal_proximity_amplifies_existing_health_deductions(self):
        troubled = _account(last_qbr_date=date(2025, 1, 1))
        immediate = score_account(
            {**troubled, "renewal_date": date(2026, 9, 1)}, TODAY,
        )
        far = score_account(
            {**troubled, "renewal_date": date(2029, 9, 1)}, TODAY,
        )
        self.assertLess(immediate["score"], far["score"])

    def test_arr_direction_adjusts_health(self):
        declining = score_account(_account(arr_trend_pct=-20), TODAY)
        growing = score_account(_account(arr_trend_pct=20), TODAY)
        self.assertLess(declining["score"], growing["score"])

    def test_score_stays_in_bounds(self):
        result = score_account(_account(
            last_qbr_date=None,
            customer_since=date(2010, 1, 1),
            overdue_flag=True,
            tickets_12mo=100,
            pct_high_priority=100,
            seat_utilisation_pct=0,
            active_user_pct=0,
            term_length_months=12,
            renewal_date=date(2026, 7, 1),
        ), TODAY)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class BandTests(TestCase):
    def test_single_health_vocabulary(self):
        self.assertEqual([label for _, label in BANDS], ["Critical", "Watch", "Healthy"])
        self.assertEqual(_band(50), "Critical")
        self.assertEqual(_band(51), "Watch")
        self.assertEqual(_band(75), "Watch")
        self.assertEqual(_band(76), "Healthy")


class PortfolioHealthTests(TestCase):
    def test_arr_weighted_health(self):
        accounts = [
            {**score_account(_account(account_id="A", last_qbr_date=date(2026, 7, 1)), TODAY), "current_arr": 900_000},
            {**score_account(_account(account_id="B", last_qbr_date=None, customer_since=date(2018, 1, 1)), TODAY), "current_arr": 100_000},
        ]
        result = portfolio_health(accounts)
        self.assertGreater(result["weighted"], result["unweighted"])


class ParseSnapshotTests(TestCase):
    HEADER = (
        "account_id,account_name,segment,industry,csm_owner,customer_since,"
        "contract_start,renewal_date,term_length_months,auto_renew,current_arr,last_qbr_date\n"
    )

    def test_arr_native_snapshot(self):
        row = (
            "ACC-1,Acme,Mid-Market,Technology / SaaS,Jordan,2023-01-01,"
            "2025-01-01,2028-01-01,36,TRUE,120000,2026-06-01\n"
        )
        accounts, errors = parse_snapshot(io.BytesIO((self.HEADER + row).encode()))
        self.assertEqual(errors, [])
        self.assertEqual(accounts["ACC-1"]["current_arr"], 120_000)
        self.assertEqual(accounts["ACC-1"]["last_qbr_date"], date(2026, 6, 1))
        self.assertEqual(accounts["ACC-1"]["customer_since"], date(2023, 1, 1))

    def test_blank_qbr_is_allowed(self):
        row = (
            "ACC-1,Acme,Mid-Market,Technology / SaaS,Jordan,2023-01-01,"
            "2025-01-01,2028-01-01,36,TRUE,120000,\n"
        )
        accounts, errors = parse_snapshot(io.BytesIO((self.HEADER + row).encode()))
        self.assertEqual(errors, [])
        self.assertIsNone(accounts["ACC-1"]["last_qbr_date"])

    def test_legacy_snapshot_revenue_is_still_accepted(self):
        header = (
            "account_id,account_name,segment,industry,csm_owner,customer_since,"
            "contract_start,renewal_date,auto_renew,avg_monthly_revenue_6mo,total_revenue_36mo\n"
        )
        row = "ACC-1,Acme,Mid-Market,Technology / SaaS,Jordan,2023-01-01,2025-01-01,2028-01-01,TRUE,10000,300000\n"
        accounts, errors = parse_snapshot(io.BytesIO((header + row).encode()))
        self.assertEqual(errors, [])
        self.assertEqual(accounts["ACC-1"]["current_arr"], 120_000)

    def test_missing_arr_field_fails_fast(self):
        header = (
            "account_id,account_name,segment,industry,csm_owner,customer_since,"
            "contract_start,renewal_date,auto_renew\n"
        )
        row = "ACC-1,Acme,Mid-Market,Technology / SaaS,Jordan,2023-01-01,2025-01-01,2028-01-01,TRUE\n"
        accounts, errors = parse_snapshot(io.BytesIO((header + row).encode()))
        self.assertEqual(accounts, {})
        self.assertIn("current_arr", errors[0])


class ParseTimelineTests(TestCase):
    def test_arr_native_timeline(self):
        body = b"account_id,month,arr\nACC-1,2026-01,120000\n"
        rows, errors, orphan_count = parse_timeline(io.BytesIO(body), {"ACC-1"})
        self.assertEqual(errors, [])
        self.assertEqual(orphan_count, 0)
        self.assertEqual(rows[0]["arr"], 120_000)

    def test_legacy_mrr_converts_to_arr(self):
        body = b"account_id,month,mrr\nACC-1,2026-01,10000\n"
        rows, errors, _ = parse_timeline(io.BytesIO(body), {"ACC-1"})
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["arr"], 120_000)

    def test_orphan_is_skipped(self):
        body = b"account_id,month,arr\nACC-2,2026-01,120000\n"
        rows, errors, orphan_count = parse_timeline(io.BytesIO(body), {"ACC-1"})
        self.assertEqual(rows, [])
        self.assertEqual(errors, [])
        self.assertEqual(orphan_count, 1)


class TimelineMetricTests(TestCase):
    def test_twelve_month_arr_change(self):
        rows = _timeline_rows(arrs=[100_000 + i * 5_000 for i in range(13)])
        self.assertEqual(metrics.arr_change_dollars(rows), 60_000)
        self.assertEqual(metrics.arr_trend(rows), 60.0)

    def test_usage_decline_with_steady_arr_is_hidden_renewal_risk(self):
        rows = _timeline_rows(
            arrs=[100_000] * 13,
            utils=[80 - i * 3 for i in range(13)],
        )
        self.assertTrue(metrics.is_hidden_renewal_risk(rows))

    def test_obvious_arr_decline_is_not_hidden_renewal_risk(self):
        rows = _timeline_rows(
            arrs=[100_000 - i * 5_000 for i in range(13)],
            utils=[80 - i * 3 for i in range(13)],
        )
        self.assertFalse(metrics.is_hidden_renewal_risk(rows))

    def test_arr_expansion_without_usage_growth_is_hidden_renewal_risk(self):
        rows = _timeline_rows(
            arrs=[100_000 + i * 2_500 for i in range(13)],
            utils=[70] * 13,
        )
        self.assertTrue(metrics.is_hidden_renewal_risk(rows))

    def test_arr_expansion_with_usage_growth_is_not_hidden_renewal_risk(self):
        rows = _timeline_rows(
            arrs=[100_000 + i * 2_500 for i in range(13)],
            utils=[60 + i for i in range(13)],
        )
        self.assertFalse(metrics.is_hidden_renewal_risk(rows))

    def test_monthly_arr_movement(self):
        jan, feb = date(2026, 1, 1), date(2026, 2, 1)
        timeline = {
            "A": [{"month": jan, "arr": 100_000}, {"month": feb, "arr": 120_000}],
            "B": [{"month": jan, "arr": 100_000}, {"month": feb, "arr": 80_000}],
            "C": [{"month": jan, "arr": 50_000}, {"month": feb, "arr": 0}],
            "D": [{"month": feb, "arr": 40_000}],
        }
        movement = metrics.monthly_arr_movement(timeline)[0]
        self.assertEqual(movement["new"], 40_000)
        self.assertEqual(movement["expansion"], 20_000)
        self.assertEqual(movement["contraction"], -20_000)
        self.assertEqual(movement["churn"], -50_000)
        self.assertEqual(movement["net"], -10_000)

    def test_timeline_overrides_snapshot_arr(self):
        account = _account(current_arr=999_999)
        rows = _timeline_rows(arrs=[100_000, 110_000])
        by_account = group_timeline_by_account(rows)
        updated = metrics.apply_timeline_overrides({"ACC-1": account}, by_account)
        self.assertEqual(updated["ACC-1"]["current_arr"], 110_000)


class SampleDataTests(TestCase):
    def setUp(self):
        self.snapshot, self.timeline_rows = sample_data.generate_sample(TODAY)
        self.accounts = list(self.snapshot.values())

    def test_demo_reconciles_to_five_million_arr(self):
        self.assertAlmostEqual(
            sum(account["current_arr"] for account in self.accounts),
            sample_data.TARGET_TOTAL_ARR,
            places=2,
        )

    def test_top_five_hold_thirty_percent(self):
        ranked = sorted(self.accounts, key=lambda account: account["current_arr"], reverse=True)
        share = sum(account["current_arr"] for account in ranked[:5]) / sample_data.TARGET_TOTAL_ARR
        self.assertAlmostEqual(share, sample_data.TOP5_REVENUE_SHARE, delta=0.001)

    def test_contract_policy_is_represented(self):
        terms = Counter(account["term_length_months"] for account in self.accounts)
        self.assertGreater(terms[36], terms[12])
        self.assertGreaterEqual(terms[60], 2)
        self.assertGreaterEqual(terms[24], 1)

    def test_two_five_year_accounts_include_mid_market_harbor(self):
        five_year = [
            account for account in self.accounts if account["term_length_months"] == 60
        ]
        self.assertGreaterEqual(len(five_year), 2)
        harbor = next(account for account in five_year if account["account_name"] == "Harbor Advisory")
        self.assertEqual(harbor["segment"], "Mid-Market")
        self.assertGreater(harbor["current_arr"] * 5, harbor["current_arr"] * 3)

    def test_qbr_and_customer_since_are_in_demo(self):
        self.assertTrue(all(account.get("customer_since") for account in self.accounts))
        self.assertTrue(any(account.get("last_qbr_date") is None for account in self.accounts))
        self.assertTrue(any(account.get("last_qbr_date") is not None for account in self.accounts))

    def test_arr_native_csv_headers(self):
        self.assertIn("current_arr", sample_data.SNAPSHOT_COLUMNS)
        self.assertIn("last_qbr_date", sample_data.SNAPSHOT_COLUMNS)
        self.assertIn("customer_since", sample_data.SNAPSHOT_COLUMNS)
        self.assertIn("arr", sample_data.TIMELINE_COLUMNS)
        self.assertNotIn("mrr", sample_data.TIMELINE_COLUMNS)


class DashboardContextTests(TestCase):
    def _context(self, with_timeline=True):
        snapshot, timeline_rows = sample_data.generate_sample(TODAY)
        by_account = group_timeline_by_account(timeline_rows) if with_timeline else {}
        if by_account:
            snapshot = metrics.apply_timeline_overrides(snapshot, by_account)
        scored = score_portfolio(
            [metrics.enrich_snapshot_metrics(account) for account in snapshot.values()],
            TODAY,
        )
        return build_dashboard_context(scored, TODAY, by_account or None)

    def test_three_product_payloads_exist(self):
        context = self._context()
        for key in (
            "chart_concentration",
            "chart_arr_distribution",
            "chart_contract_runway",
            "chart_customer_tenure",
            "chart_industry_portfolio",
            "chart_health_distribution",
            "chart_qbr_coverage",
            "priority_accounts",
            "chart_arr_trend",
            "chart_health_trend",
            "chart_arr_movement",
            "chart_arr_by_group",
        ):
            self.assertIn(key, context)

    def test_removed_metrics_and_charts_are_absent(self):
        context = self._context()
        for key in ("chart_revenue_vs_risk", "chart_arr_bridge", "nrr", "grr"):
            self.assertNotIn(key, context)
            self.assertNotIn(key, context["kpi"])

    def test_contract_runway_has_four_buckets(self):
        context = self._context()
        self.assertEqual(
            [row["label"] for row in context["chart_contract_runway"]],
            ["0-6 months", "6-18 months", "18-36 months", "36+ months"],
        )

    def test_value_tiers_are_balanced_and_show_average_arr(self):
        context = self._context()
        tiers = context["chart_arr_distribution"]
        self.assertEqual([row["label"] for row in tiers], ["Gold", "Silver", "Bronze"])
        self.assertEqual(sum(row["count"] for row in tiers), 46)
        self.assertTrue(all("average_arr" in row for row in tiers))
        self.assertGreater(tiers[0]["average_arr"], tiers[1]["average_arr"])
        self.assertGreater(tiers[1]["average_arr"], tiers[2]["average_arr"])

    def test_outlook_has_three_additional_summary_fields(self):
        context = self._context()
        for key in (
            "immediate_count",
            "critical_watch_arr",
            "critical_watch_pct",
            "established_arr",
            "established_count",
        ):
            self.assertIn(key, context["kpi"])

    def test_concentration_payload_is_capped_at_top_50(self):
        context = self._context()
        payload = context["chart_concentration"]
        self.assertLessEqual(len(payload["accounts"]), 50)
        self.assertEqual(payload["shown_count"], len(payload["accounts"]))

    def test_intervention_queue_is_limited_to_top_six(self):
        context = self._context()
        self.assertEqual(len(context["priority_accounts"]), 6)

    def test_current_views_exclude_zero_arr_churns_but_history_keeps_them(self):
        context = self._context()
        distribution_count = sum(
            row["count"] for row in context["chart_arr_distribution"]
        )
        self.assertEqual(context["kpi"]["account_count"], 46)
        self.assertEqual(distribution_count, 46)
        self.assertIn(
            "Redwood Trust",
            [row["name"] for row in context["chart_growers_decliners"]],
        )

    def test_snapshot_only_omits_revenue_story_payloads(self):
        context = self._context(with_timeline=False)
        self.assertFalse(context["has_timeline"])
        self.assertNotIn("chart_arr_trend", context)


class DashboardViewTests(TestCase):
    def _sample_files(self):
        snapshot, timeline_rows = sample_data.generate_sample(TODAY)
        return (
            SimpleUploadedFile(
                "snapshot.csv",
                sample_data.snapshot_to_csv(snapshot).encode(),
                content_type="text/csv",
            ),
            SimpleUploadedFile(
                "timeline.csv",
                sample_data.timeline_to_csv(timeline_rows).encode(),
                content_type="text/csv",
            ),
        )

    def test_get_renders_upload_form(self):
        response = self.client.get("/pulse/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload your book of business")

    def test_sample_renders_three_named_products(self):
        response = self.client.get("/pulse/?sample=1")
        self.assertEqual(response.status_code, 200)
        for label in ("Portfolio Outlook", "Customer Action Centre", "Revenue Story"):
            self.assertContains(response, label)
        for chart_id in (
            "pulse-chart-concentration",
            "pulse-chart-arr-distribution",
            "pulse-chart-contract-runway",
            "pulse-chart-tenure",
            "pulse-chart-industry",
            "pulse-chart-health-distribution",
            "pulse-chart-qbr",
            "pulse-chart-growers",
            "pulse-chart-divergence",
            "pulse-chart-portfolio-trend",
            "pulse-chart-arr-movement",
            "pulse-chart-arr-group",
        ):
            self.assertContains(response, chart_id)
        self.assertNotContains(response, "Revenue vs. risk")
        self.assertNotContains(response, "ARR bridge")
        self.assertNotContains(response, "NRR / GRR")
        self.assertNotContains(response, "Part I")
        self.assertContains(response, "One portfolio, three decisions")
        self.assertContains(response, "The Value Ladder")
        self.assertContains(response, "The Revenue Skyline")
        self.assertContains(response, "The Intervention Queue")
        self.assertContains(response, "The Portfolio Current")
        self.assertContains(response, "pulse-priority-card")
        self.assertEqual(
            response.content.decode().count("pulse-priority-card pulse-priority-card--"),
            6,
        )
        self.assertNotContains(response, 'id="pulse-chart-arr-trend"')
        self.assertNotContains(response, 'id="pulse-chart-health-trend"')
        self.assertNotContains(response, "pulse-table")
        self.assertContains(
            response,
            'class="pulse-group-toggle__btn is-active" data-group="by_industry"',
            html=False,
        )
        hidden_risk_names = {
            account["account_name"]
            for account in response.context["hidden_renewal_risks"]
        }
        self.assertIn("Frontier Trust", hidden_risk_names)

    def test_arr_native_upload_renders(self):
        snapshot, timeline = self._sample_files()
        response = self.client.post(
            "/pulse/",
            {"snapshot_file": snapshot, "timeline_file": timeline},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Revenue Story")

    def test_downloaded_csvs_use_arr_and_qbr(self):
        snapshot_response = self.client.get("/pulse/sample/snapshot.csv")
        timeline_response = self.client.get("/pulse/sample/timeline.csv")
        snapshot_header = snapshot_response.content.decode().splitlines()[0]
        timeline_header = timeline_response.content.decode().splitlines()[0]
        self.assertIn("customer_since", snapshot_header)
        self.assertIn("last_qbr_date", snapshot_header)
        self.assertIn("current_arr", snapshot_header)
        self.assertIn("arr", timeline_header)
        self.assertNotIn("mrr", timeline_header)
