import io
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from . import metrics, sample_data
from .aggregate import build_dashboard_context
from .parsing import group_timeline_by_account, parse_snapshot, parse_timeline
from .scoring import _band, portfolio_health, score_account, score_portfolio

TODAY = date(2026, 7, 1)


def _account(**overrides):
    base = {
        "account_id": "ACC-1", "account_name": "Acme Co", "segment": "Mid-Market",
        "industry": "Technology / SaaS", "csm_owner": "Jordan Reyes",
        "customer_since": date(2023, 1, 1), "product_tier": "Growth", "seats_purchased": 20,
        "contract_start": date(2023, 1, 1), "renewal_date": date(2027, 1, 1),
        "term_length_months": 12, "auto_renew": True, "entry_arr": 50_000.0,
        "last_qbr_date": date(2026, 6, 1),
        "avg_monthly_revenue_6mo": 10_000.0, "total_revenue_36mo": 300_000.0,
        "tickets_12mo": 4, "pct_high_priority": 10.0, "days_since_contact": 20,
        "overdue_flag": False, "seat_utilisation_pct": 75.0, "active_user_pct": 70.0,
    }
    base.update(overrides)
    return base


class ScoreAccountTests(TestCase):
    def test_healthy_account_scores_high(self):
        result = score_account(_account(), today=TODAY)
        self.assertEqual(result["band"], "Healthy")
        self.assertGreaterEqual(result["score"], 60)

    def test_risk_score_and_health_score_are_distinct_values(self):
        # Risk is the raw pre-multiplier deduction; health is post-multiplier.
        # For a troubled account with a near renewal, they should differ.
        troubled = _account(days_since_contact=200, renewal_date=date(2026, 7, 20))
        result = score_account(troubled, today=TODAY)
        self.assertNotEqual(result["score"], 100 - result["risk_score"])

    def test_continuous_ramp_no_cliff_at_band_edges(self):
        just_under = score_account(_account(days_since_contact=89), today=TODAY)
        just_over = score_account(_account(days_since_contact=91), today=TODAY)
        self.assertLess(abs(just_under["score"] - just_over["score"]), 1.0)

    def test_segment_aware_thresholds(self):
        enterprise = score_account(_account(segment="Enterprise", days_since_contact=100, tickets_12mo=6), today=TODAY)
        smb = score_account(_account(segment="SMB", days_since_contact=100, tickets_12mo=6), today=TODAY)
        self.assertGreater(enterprise["score"], smb["score"])

    def test_momentum_multiplier_direction(self):
        troubled = _account(days_since_contact=200)
        declining = score_account({**troubled, "momentum_ratio": 0.8}, today=TODAY)
        growing = score_account({**troubled, "momentum_ratio": 1.2}, today=TODAY)
        self.assertLess(declining["score"], growing["score"])

    def test_missing_signals_contribute_zero_penalty(self):
        blank = _account(days_since_contact=None, overdue_flag=None, tickets_12mo=None,
                          pct_high_priority=None, seat_utilisation_pct=None, active_user_pct=None)
        result = score_account(blank, today=TODAY)
        self.assertEqual(result["score"], 100.0)
        self.assertEqual(result["data_completeness"], 0.0)

    def test_full_signal_coverage_is_100_percent_complete(self):
        result = score_account(_account(), today=TODAY)
        self.assertEqual(result["data_completeness"], 100.0)

    def test_renewal_proximity_amplifies_existing_risk(self):
        troubled = _account(days_since_contact=200, overdue_flag=True)
        far = score_account({**troubled, "renewal_date": date(2027, 6, 1)}, today=TODAY)
        near = score_account({**troubled, "renewal_date": date(2026, 7, 20)}, today=TODAY)
        self.assertLess(near["score"], far["score"])

    def test_score_never_leaves_0_100_bounds(self):
        worst = _account(days_since_contact=999, overdue_flag=True, tickets_12mo=100,
                          pct_high_priority=100, seat_utilisation_pct=0, active_user_pct=0,
                          renewal_date=date(2026, 7, 10), customer_since=date(2026, 6, 1))
        result = score_account(worst, today=TODAY)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class BandBoundaryTests(TestCase):
    def test_three_tiers_only(self):
        from .scoring import BANDS
        self.assertEqual([label for _, label in BANDS], ["Critical", "At-risk", "Healthy"])

    def test_band_boundaries_are_inclusive_on_the_lower_side(self):
        self.assertEqual(_band(50), "Critical")
        self.assertEqual(_band(51), "At-risk")
        self.assertEqual(_band(75), "At-risk")
        self.assertEqual(_band(76), "Healthy")
        self.assertEqual(_band(100), "Healthy")


class PortfolioHealthTests(TestCase):
    def test_arr_weighted_average(self):
        scored = [
            {**score_account(_account(days_since_contact=5), today=TODAY), "current_arr": 900_000.0},
            {**score_account(_account(days_since_contact=400), today=TODAY), "current_arr": 100_000.0},
        ]
        result = portfolio_health(scored)
        # The large, healthy account dominates the weighted average.
        self.assertGreater(result["weighted"], result["unweighted"])


class ParseSnapshotTests(TestCase):
    HEADER = ("account_id,account_name,segment,industry,csm_owner,customer_since,contract_start,"
              "renewal_date,auto_renew,avg_monthly_revenue_6mo,total_revenue_36mo\n")

    def _csv(self, body):
        return io.BytesIO((self.HEADER + body).encode("utf-8"))

    def test_parses_valid_row(self):
        row = "ACC-1,Acme,Mid-Market,Technology / SaaS,Jordan,2023-01-01,2023-01-01,2027-01-01,TRUE,10000,300000\n"
        accounts, errors = parse_snapshot(self._csv(row))
        self.assertEqual(errors, [])
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts["ACC-1"]["auto_renew"], True)

    def test_missing_required_column_fails_fast(self):
        bad = io.BytesIO(b"account_id,account_name\nACC-1,Acme\n")
        accounts, errors = parse_snapshot(bad)
        self.assertEqual(accounts, {})
        self.assertIn("missing required column", errors[0])

    def test_revenue_fields_optional_when_timeline_present(self):
        row = "ACC-1,Acme,Mid-Market,Technology / SaaS,Jordan,2023-01-01,2023-01-01,2027-01-01,TRUE,,\n"
        accounts, errors = parse_snapshot(self._csv(row), require_revenue_fields=False)
        self.assertEqual(errors, [])
        self.assertEqual(len(accounts), 1)

    def test_unrecognised_industry_falls_back_to_other(self):
        row = "ACC-1,Acme,Mid-Market,Made Up Industry,Jordan,2023-01-01,2023-01-01,2027-01-01,TRUE,10000,300000\n"
        accounts, _ = parse_snapshot(self._csv(row))
        self.assertEqual(accounts["ACC-1"]["industry"], "Other")


class ParseTimelineTests(TestCase):
    def test_valid_rows_and_orphan_skipping(self):
        body = (b"account_id,month,mrr\n"
                b"ACC-1,2026-01,1000\n"
                b"ACC-2,2026-01,2000\n")  # ACC-2 is not a known account
        rows, errors, orphan_count = parse_timeline(io.BytesIO(body), known_account_ids={"ACC-1"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(orphan_count, 1)
        self.assertEqual(errors, [])

    def test_bad_row_is_skipped_and_counted_as_an_error(self):
        body = b"account_id,month,mrr\nACC-1,not-a-month,1000\n"
        rows, errors, orphan_count = parse_timeline(io.BytesIO(body), known_account_ids={"ACC-1"})
        self.assertEqual(rows, [])
        self.assertEqual(len(errors), 1)


class RevenueRetentionTests(TestCase):
    def test_nrr_grr_hand_checked(self):
        jan, feb = date(2026, 1, 1), date(2026, 2, 1)
        timeline = {
            "A": [{"month": jan, "mrr": 1000.0}, {"month": feb, "mrr": 1200.0}],  # expansion 200
            "B": [{"month": jan, "mrr": 2000.0}, {"month": feb, "mrr": 1500.0}],  # contraction 500
            "C": [{"month": jan, "mrr": 500.0}, {"month": feb, "mrr": 0.0}],      # churn 500
        }
        result = metrics.revenue_retention(timeline, jan, feb)
        self.assertEqual(result["start"], 3500.0)
        self.assertEqual(result["expansion"], 200.0)
        self.assertEqual(result["contraction"], 500.0)
        self.assertEqual(result["churn"], 500.0)
        self.assertEqual(result["end"], 2700.0)
        self.assertAlmostEqual(result["nrr"], 77.1, places=1)
        self.assertAlmostEqual(result["grr"], 71.4, places=1)

    def test_bridge_reconciles(self):
        jan, feb = date(2026, 1, 1), date(2026, 2, 1)
        timeline = {
            "A": [{"month": jan, "mrr": 1000.0}, {"month": feb, "mrr": 1200.0}],
            "B": [{"month": jan, "mrr": 2000.0}, {"month": feb, "mrr": 1500.0}],
        }
        result = metrics.revenue_retention(timeline, jan, feb)
        self.assertEqual(
            result["start"] + result["expansion"] - result["contraction"] - result["churn"],
            result["end"],
        )


class SilentDeclinerTests(TestCase):
    def _rows(self, mrrs, utils):
        months = [date(2026, i, 1) for i in range(1, len(mrrs) + 1)]
        return [{"month": m, "mrr": mrr, "seat_utilisation_pct": u, "active_user_pct": None, "tickets_opened": 0}
                for m, mrr, u in zip(months, mrrs, utils)]

    def test_flags_flat_revenue_with_collapsing_usage(self):
        rows = self._rows([1000, 1000, 1000, 1000], [80, 70, 60, 50])
        self.assertTrue(metrics.is_silent_decliner(rows))

    def test_does_not_flag_healthy_growth(self):
        rows = self._rows([1000, 1100, 1200, 1300], [70, 72, 71, 73])
        self.assertFalse(metrics.is_silent_decliner(rows))

    def test_does_not_flag_obvious_decline_revenue_also_dropping(self):
        # Revenue itself is dropping, so this isn't "silent" — it's already visible.
        rows = self._rows([1000, 800, 600, 400], [80, 60, 40, 20])
        self.assertFalse(metrics.is_silent_decliner(rows))


class MomentumRatioAgreementTests(TestCase):
    def test_snapshot_only_and_timeline_derived_agree_when_flat(self):
        account = _account(avg_monthly_revenue_6mo=1000.0, total_revenue_36mo=36000.0)
        snapshot_only_ratio = metrics.momentum_ratio(account)

        months = [date(2023, 1, 1)]
        y, m = 2023, 1
        timeline_rows = []
        for _ in range(36):
            timeline_rows.append({"account_id": "ACC-1", "month": date(y, m, 1), "mrr": 1000.0,
                                   "seat_utilisation_pct": None, "active_user_pct": None, "tickets_opened": 0})
            m += 1
            if m == 13:
                m, y = 1, y + 1

        by_account = group_timeline_by_account(timeline_rows)
        overridden = metrics.apply_timeline_overrides({"ACC-1": _account()}, by_account)
        timeline_derived_ratio = metrics.momentum_ratio(overridden["ACC-1"])

        self.assertAlmostEqual(snapshot_only_ratio, timeline_derived_ratio, places=2)


class SingleSourceOfTruthTests(TestCase):
    def test_timeline_overrides_hand_entered_snapshot_values(self):
        account = _account(avg_monthly_revenue_6mo=99999.0, total_revenue_36mo=999999.0)
        jan = date(2026, 1, 1)
        rows = [{"account_id": "ACC-1", "month": jan, "mrr": 500.0,
                 "seat_utilisation_pct": None, "active_user_pct": None, "tickets_opened": 0}]
        by_account = group_timeline_by_account(rows)
        overridden = metrics.apply_timeline_overrides({"ACC-1": account}, by_account)
        self.assertEqual(overridden["ACC-1"]["avg_monthly_revenue_6mo"], 500.0)
        self.assertEqual(overridden["ACC-1"]["total_revenue_36mo"], 500.0)


class BuildDashboardContextTests(TestCase):
    def test_snapshot_only_context_has_no_timeline_keys(self):
        scored = score_portfolio([metrics.enrich_snapshot_metrics(_account())], today=TODAY)
        ctx = build_dashboard_context(scored, TODAY, timeline_by_account=None)
        self.assertFalse(ctx["has_timeline"])
        self.assertNotIn("chart_arr_bridge", ctx)

    def test_revenue_tiers_are_gold_silver_bronze_and_reconcile(self):
        accounts = [
            {**_account(account_id=f"ACC-{i}", account_name=f"Company {i}"),
             "avg_monthly_revenue_6mo": (10 - i) * 10_000.0}
            for i in range(10)
        ]
        scored = score_portfolio([metrics.enrich_snapshot_metrics(a) for a in accounts], today=TODAY)
        ctx = build_dashboard_context(scored, TODAY, timeline_by_account=None)
        tiers = ctx["chart_revenue_concentration"]["tiers"]
        self.assertEqual([t["tier"] for t in tiers], ["Gold", "Silver", "Bronze"])
        total_arr = sum(a["current_arr"] for a in scored)
        self.assertAlmostEqual(sum(t["arr"] for t in tiers), total_arr, places=2)
        self.assertEqual(sum(t["count"] for t in tiers), len(scored))
        # Gold should hold the single largest account (10 accounts * 20% = ~2, but at least 1).
        self.assertIn("Company 0", tiers[0]["top_accounts"])


class SampleDataDistributionTests(TestCase):
    def setUp(self):
        self.today = date(2026, 7, 2)
        self.snapshot, self.timeline_rows = sample_data.generate_sample(today=self.today)
        self.accounts = list(self.snapshot.values())
        self.total_arr = sum(a["avg_monthly_revenue_6mo"] * 12 for a in self.accounts)

    def test_top_five_accounts_hold_roughly_30_percent_of_arr(self):
        ranked = sorted(self.accounts, key=lambda a: a["avg_monthly_revenue_6mo"] * 12, reverse=True)
        top5_arr = sum(a["avg_monthly_revenue_6mo"] * 12 for a in ranked[:5])
        self.assertAlmostEqual(top5_arr / self.total_arr, sample_data.TOP5_REVENUE_SHARE, delta=0.01)

    def test_two_industries_hold_roughly_half_of_arr(self):
        by_industry = {}
        for a in self.accounts:
            by_industry[a["industry"]] = by_industry.get(a["industry"], 0.0) + a["avg_monthly_revenue_6mo"] * 12
        dominant_sum = sum(v for k, v in by_industry.items() if k in sample_data.DOMINANT_INDUSTRIES)
        self.assertGreaterEqual(dominant_sum / self.total_arr, 0.45)
        self.assertLessEqual(dominant_sum / self.total_arr, 0.60)

    def test_sterling_and_ridgeline_illustrate_risk_vs_health_divergence(self):
        timeline_by_account = group_timeline_by_account(self.timeline_rows)
        overridden = metrics.apply_timeline_overrides(self.snapshot, timeline_by_account)
        enriched = [metrics.enrich_snapshot_metrics(a) for a in overridden.values()]
        scored = score_portfolio(enriched, today=self.today)
        by_name = {a["account_name"]: a for a in scored}

        rank = {"Critical": 0, "At-risk": 1, "Healthy": 2}
        sterling = by_name["Sterling Capital"]
        ridgeline = by_name["Ridgeline Technologies"]

        # Sterling: heavy raw risk signal, but context (fresh long term, no
        # renewal pressure) means final health reads no worse than raw risk.
        self.assertGreaterEqual(rank[sterling["band"]], rank[sterling["risk_band"]])

        # Ridgeline: moderate raw risk, but renewal proximity amplifies it —
        # final health reads worse than the raw signal alone would suggest.
        self.assertLess(rank[ridgeline["band"]], rank[ridgeline["risk_band"]])


class DashboardViewTests(TestCase):
    def _sample_files(self):
        today = date(2026, 7, 2)
        snapshot, timeline_rows = sample_data.generate_sample(today=today)
        snap_csv = sample_data.snapshot_to_csv(snapshot)
        tl_csv = sample_data.timeline_to_csv(timeline_rows)
        return (
            SimpleUploadedFile("snapshot.csv", snap_csv.encode(), content_type="text/csv"),
            SimpleUploadedFile("timeline.csv", tl_csv.encode(), content_type="text/csv"),
        )

    def test_get_renders_upload_form(self):
        resp = self.client.get("/pulse/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Upload your book of business")

    def test_snapshot_only_upload_renders_six_charts_and_two_sections(self):
        snapshot_file, _ = self._sample_files()
        resp = self.client.post("/pulse/", {"snapshot_file": snapshot_file})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        for chart_id in ["pulse-chart-concentration", "pulse-chart-revenue-risk", "pulse-chart-revenue-health",
                          "pulse-chart-renewal-wall", "pulse-chart-industry", "pulse-chart-coverage",
                          "pulse-chart-momentum"]:
            self.assertIn(chart_id, content)
        for timeline_chart_id in ["pulse-chart-arr-bridge", "pulse-chart-health-nrr", "pulse-chart-divergence"]:
            self.assertNotIn(timeline_chart_id, content)
        self.assertNotIn("Download PDF", content)
        self.assertEqual(content.count('class="pulse-section'), 2)

    def test_snapshot_and_timeline_upload_renders_all_ten_charts_and_three_sections(self):
        snapshot_file, timeline_file = self._sample_files()
        resp = self.client.post("/pulse/", {"snapshot_file": snapshot_file, "timeline_file": timeline_file})
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        for chart_id in ["pulse-chart-concentration", "pulse-chart-revenue-risk", "pulse-chart-revenue-health",
                          "pulse-chart-renewal-wall", "pulse-chart-industry", "pulse-chart-coverage",
                          "pulse-chart-momentum", "pulse-chart-arr-bridge", "pulse-chart-health-nrr",
                          "pulse-chart-divergence", "pulse-chart-revenue-group"]:
            self.assertIn(chart_id, content)
        self.assertIn('id="section-timeline"', content)
        self.assertEqual(content.count('class="pulse-section'), 3)

    def test_load_sample_query_param_renders_full_dashboard(self):
        resp = self.client.get("/pulse/?sample=1")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("Portfolio health", content)
        self.assertIn("pulse-chart-arr-bridge", content)

    def test_download_sample_csvs(self):
        snap_resp = self.client.get("/pulse/sample/snapshot.csv")
        tl_resp = self.client.get("/pulse/sample/timeline.csv")
        self.assertEqual(snap_resp.status_code, 200)
        self.assertEqual(tl_resp.status_code, 200)
        self.assertIn("account_id", snap_resp.content.decode().splitlines()[0])
        self.assertIn("account_id", tl_resp.content.decode().splitlines()[0])

    def test_non_csv_upload_shows_validation_error(self):
        bad = SimpleUploadedFile("notes.txt", b"not a csv", content_type="text/plain")
        resp = self.client.post("/pulse/", {"snapshot_file": bad})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context["has_data"])
