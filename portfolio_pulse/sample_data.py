"""
Deterministic sample portfolio generator — a Snapshot + a matching Timeline
for ~50 accounts, industry-grouped, seeded with named narrative patterns
(healthy expanders, silent decliners, obvious fires, churns, whales, new
accounts) so every chart on the dashboard has real signal on first load.

The Snapshot's revenue fields are computed from the generated Timeline
(never hand-set), the same single-source-of-truth rule real uploads follow.
Runs through the exact same parse -> score -> aggregate pipeline as a real
upload — see views.py's `?sample=1` route.
"""
import csv
import io
import random
from datetime import date, timedelta

SEED = 20260702
TARGET_ACCOUNTS = 50
TARGET_TOTAL_ARR = 5_000_000
TOP5_REVENUE_SHARE = 0.30    # top 5 accounts by ARR carry 30% of the book
DOMINANT_INDUSTRY_SHARE = 0.50
DOMINANT_INDUSTRIES = ["Financial Services", "Technology / SaaS"]
FIXED_INDUSTRY_ACCOUNTS = {
    "Northwind Logistics", "Meridian Retail", "Cobalt Manufacturing",
    "Sterling Capital", "Ridgeline Technologies",
}

NAME_PREFIXES = [
    "Northwind", "Meridian", "Cobalt", "Summit", "Harbor", "Granite", "Silver", "Ironwood",
    "Amber", "Willow", "Redwood", "Vertex", "Anchor", "Orbit", "Vista", "Maple", "Sterling",
    "Nimbus", "Quartz", "Frontier", "Highline", "Cascade", "Alpine", "Sable", "Crestwood",
    "Beacon", "Zephyr", "Palisade", "Ridgeline", "Kestrel", "Overton", "Bayline", "Fernwood",
]

INDUSTRIES = {
    "Financial Services": {
        "suffixes": ["Capital", "Financial", "Trust", "Bancorp"],
        "segment_skew": ["Enterprise", "Enterprise", "Mid-Market"], "ticket_mult": 0.6,
    },
    "Logistics & Supply Chain": {
        "suffixes": ["Logistics", "Freight", "Supply Co"], "segment_skew": ["Enterprise", "Mid-Market", "Mid-Market"],
        "ticket_mult": 1.0,
    },
    "Manufacturing": {
        "suffixes": ["Manufacturing", "Industries", "Works"], "segment_skew": ["SMB", "SMB", "Mid-Market"],
        "ticket_mult": 1.1,
    },
    "Retail & E-commerce": {
        "suffixes": ["Retail", "Commerce", "Mercantile"], "segment_skew": ["Mid-Market", "Mid-Market", "SMB"],
        "ticket_mult": 1.2,
    },
    "Healthcare": {
        "suffixes": ["Health Partners", "Medical Group", "Care Network"],
        "segment_skew": ["Enterprise", "Mid-Market"], "ticket_mult": 0.7,
    },
    "Technology / SaaS": {
        "suffixes": ["Software", "Systems", "Cloud", "Technologies"],
        "segment_skew": ["Mid-Market", "Enterprise"], "ticket_mult": 0.9,
    },
    "Professional Services": {
        "suffixes": ["Consulting", "Advisory", "Partners"], "segment_skew": ["SMB", "Mid-Market"],
        "ticket_mult": 0.8,
    },
    "Media & Marketing": {
        "suffixes": ["Media", "Studios", "Marketing Group"], "segment_skew": ["Mid-Market", "SMB"],
        "ticket_mult": 1.3,
    },
}
INDUSTRY_NAMES = list(INDUSTRIES.keys())

SEATS_RANGE = {"Enterprise": (50, 500), "Mid-Market": (15, 60), "SMB": (3, 15)}
CSM_OWNERS = ["Jordan Reyes", "Jordan Reyes", "Priya Nair"]


def _month_start(d):
    return d.replace(day=1)


def _months_back(anchor_month, n):
    """List of `n` month-start dates ending at (and including) anchor_month."""
    months = []
    y, m = anchor_month.year, anchor_month.month
    for _ in range(n):
        months.append(date(y, m, 1))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(months))


class _AccountBuilder:
    """Builds one account's Snapshot fields + Timeline rows from a narrative shape."""

    def __init__(self, rng, account_id, name, industry, segment, today):
        self.rng = rng
        self.account_id = account_id
        self.name = name
        self.industry = industry
        self.segment = segment
        self.today = today
        self.timeline = []
        self.snapshot = {}

    def build_timeline(self, n_months, mrr_path, util_path=None, ticket_base=1.0):
        rng = self.rng
        anchor = _month_start(self.today)
        months = _months_back(anchor, n_months)
        util_path = util_path or (lambda i, n: max(0.0, min(100.0, 55 + rng.uniform(-5, 5))))
        for i, month in enumerate(months):
            mrr = max(0.0, mrr_path(i, n_months) * (1 + rng.uniform(-0.02, 0.02)))
            util = util_path(i, n_months)
            active = max(0.0, min(100.0, util * rng.uniform(0.78, 0.95))) if util else None
            tickets_opened = max(0, round(rng.gauss(ticket_base * INDUSTRIES[self.industry]["ticket_mult"], 0.8)))
            self.timeline.append({
                "account_id": self.account_id, "month": month, "mrr": round(mrr, 2),
                "seat_utilisation_pct": round(util, 1) if util is not None else None,
                "active_user_pct": round(active, 1) if active is not None else None,
                "tickets_opened": tickets_opened,
            })
        return self

    def finalize(self, *, term_length_months=12, auto_renew=True,
                 renewal_in_days=None, last_qbr_days_ago=30, days_since_contact=20,
                 overdue_flag=False, tickets_12mo=None, pct_high_priority=None,
                 product_tier="Growth", contract_start_days_ago=None):
        rng = self.rng
        first_month = self.timeline[0]["month"]
        customer_since = first_month
        # Usually the same event, but a long-tenured account can sign a new
        # term without that resetting how long they've been a customer.
        contract_start = (self.today - timedelta(days=contract_start_days_ago)
                           if contract_start_days_ago is not None else customer_since)

        if renewal_in_days is None:
            renewal_in_days = rng.randint(30, 360)
        renewal_date = self.today + timedelta(days=renewal_in_days)

        last_row = self.timeline[-1]
        recent = self.timeline[-6:]
        window = self.timeline[-36:]
        avg_monthly_revenue_6mo = round(sum(r["mrr"] for r in recent) / len(recent), 2)
        total_revenue_36mo = round(sum(r["mrr"] for r in window), 2)

        entry_mrr = self.timeline[0]["mrr"]
        seats_lo, seats_hi = SEATS_RANGE[self.segment]

        if tickets_12mo is None:
            trailing = self.timeline[-12:]
            tickets_12mo = sum(r["tickets_opened"] for r in trailing)
        if pct_high_priority is None:
            pct_high_priority = round(max(0, min(100, rng.gauss(15, 8))), 1)

        self.snapshot = {
            "account_id": self.account_id, "account_name": self.name, "segment": self.segment,
            "industry": self.industry, "csm_owner": rng.choice(CSM_OWNERS),
            "customer_since": customer_since, "product_tier": product_tier,
            "seats_purchased": rng.randint(seats_lo, seats_hi),
            "contract_start": contract_start, "renewal_date": renewal_date,
            "term_length_months": term_length_months, "auto_renew": auto_renew,
            "entry_arr": round(entry_mrr * 12, 2),
            "last_qbr_date": self.today - timedelta(days=last_qbr_days_ago) if last_qbr_days_ago is not None else None,
            "avg_monthly_revenue_6mo": avg_monthly_revenue_6mo, "total_revenue_36mo": total_revenue_36mo,
            "tickets_12mo": tickets_12mo, "pct_high_priority": pct_high_priority,
            "days_since_contact": days_since_contact, "overdue_flag": overdue_flag,
            "seat_utilisation_pct": last_row["seat_utilisation_pct"], "active_user_pct": last_row["active_user_pct"],
        }
        return self


def _pick_name(rng, industry, used):
    suffixes = INDUSTRIES[industry]["suffixes"]
    while True:
        candidate = f"{rng.choice(NAME_PREFIXES)} {rng.choice(suffixes)}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def _pick_segment(rng, industry):
    return rng.choice(INDUSTRIES[industry]["segment_skew"])


def generate_sample(today=None):
    """Returns (snapshot: dict[account_id -> dict], timeline_rows: list[dict])."""
    today = today or date.today()
    rng = random.Random(SEED)
    used_names = set()
    industries_cycle = INDUSTRY_NAMES * 8
    rng.shuffle(industries_cycle)
    industry_iter = iter(industries_cycle)
    counter = 0

    def next_account_id():
        nonlocal counter
        counter += 1
        return f"ACC-{counter:03d}"

    builders = []

    def new_builder(name=None, industry=None, segment=None):
        industry = industry or next(industry_iter)
        segment = segment or _pick_segment(rng, industry)
        name = name or _pick_name(rng, industry, used_names)
        return _AccountBuilder(rng, next_account_id(), name, industry, segment, today)

    # ── Named narrative seeds ──────────────────────────────────────
    # Healthy expanders: climbing MRR, utilisation saturating, recent QBR.
    expander_names = ["Northwind Logistics", None, None]
    for name in expander_names:
        industry = "Logistics & Supply Chain" if name else None
        b = new_builder(name=name, industry=industry)
        used_names.add(b.name)
        n = rng.randint(24, 36)
        start_mrr = rng.uniform(4000, 15000)
        end_mrr = start_mrr * rng.uniform(1.3, 1.7)
        b.build_timeline(n, lambda i, nn, s=start_mrr, e=end_mrr: s + (e - s) * (i / (nn - 1)),
                          util_path=lambda i, nn: 58 + (92 - 58) * (i / (nn - 1)))
        b.finalize(renewal_in_days=rng.randint(120, 340),
                   last_qbr_days_ago=rng.randint(20, 70), days_since_contact=rng.randint(5, 45),
                   overdue_flag=False, product_tier="Growth")
        builders.append(b)

    # Silent decliners: MRR dead flat, utilisation collapsing, contact/QBR lapsing.
    decliner_names = ["Meridian Retail", None, None]
    for name in decliner_names:
        industry = "Retail & E-commerce" if name else None
        b = new_builder(name=name, industry=industry)
        used_names.add(b.name)
        n = rng.randint(24, 36)
        flat_mrr = rng.uniform(8000, 40000)
        b.build_timeline(n, lambda i, nn, m=flat_mrr: m,
                          util_path=lambda i, nn: 85 - (85 - 38) * max(0, (i - nn * 0.5) / (nn * 0.5)))
        b.finalize(renewal_in_days=rng.randint(60, 250),
                   last_qbr_days_ago=rng.randint(240, 320), days_since_contact=rng.randint(160, 280),
                   overdue_flag=False, tickets_12mo=rng.randint(0, 3), pct_high_priority=0,
                   product_tier="Growth")
        builders.append(b)

    # Obvious fires: downgrade mid-history, overdue, tickets rising, renewal imminent.
    fire_names = ["Cobalt Manufacturing", None, None]
    for name in fire_names:
        industry = "Manufacturing" if name else None
        b = new_builder(name=name, industry=industry)
        used_names.add(b.name)
        n = rng.randint(20, 32)
        start_mrr = rng.uniform(10000, 30000)
        dip_at = int(n * rng.uniform(0.55, 0.75))
        end_mrr = start_mrr * rng.uniform(0.55, 0.75)

        def mrr_path(i, nn, s=start_mrr, e=end_mrr, dip=dip_at):
            return s if i < dip else s + (e - s) * ((i - dip) / max(1, (nn - 1 - dip)))

        b.build_timeline(n, mrr_path, util_path=lambda i, nn: max(15, 60 - i * 0.6))
        b.finalize(renewal_in_days=rng.randint(10, 90),
                   last_qbr_days_ago=rng.randint(200, 300), days_since_contact=rng.randint(30, 130),
                   overdue_flag=True, tickets_12mo=rng.randint(14, 24), pct_high_priority=round(rng.uniform(45, 70), 1),
                   auto_renew=False, product_tier="Starter")
        builders.append(b)

    # Churns: MRR steps to (near) zero at/near the end of the window.
    for _ in range(4):
        b = new_builder()
        n = rng.randint(18, 30)
        start_mrr = rng.uniform(6000, 25000)
        churn_at = n - rng.randint(1, 3)

        def mrr_path(i, nn, s=start_mrr, churn=churn_at):
            return s if i < churn else 0.0

        b.build_timeline(n, mrr_path, util_path=lambda i, nn: max(5, 50 - i * 1.2))
        b.finalize(renewal_in_days=rng.randint(-30, 20),
                   last_qbr_days_ago=rng.randint(250, 400), days_since_contact=rng.randint(180, 400),
                   overdue_flag=rng.random() < 0.5, tickets_12mo=rng.randint(2, 10),
                   auto_renew=False, product_tier="Starter")
        builders.append(b)

    # Clean expansions / contractions — step changes, populate the ARR bridge.
    for _ in range(3):
        b = new_builder()
        n = rng.randint(24, 34)
        start_mrr = rng.uniform(5000, 20000)
        step_at = int(n * rng.uniform(0.5, 0.7))
        end_mrr = start_mrr * rng.uniform(1.2, 1.5)
        util_base = 65 + rng.uniform(-5, 5)
        b.build_timeline(n, lambda i, nn, s=start_mrr, e=end_mrr, st=step_at: s if i < st else e,
                          util_path=lambda i, nn, b=util_base: b + rng.uniform(-2, 2))
        b.finalize(renewal_in_days=rng.randint(60, 300),
                   last_qbr_days_ago=rng.randint(30, 100), days_since_contact=rng.randint(10, 90))
        builders.append(b)

    for _ in range(2):
        b = new_builder()
        n = rng.randint(24, 34)
        start_mrr = rng.uniform(8000, 25000)
        step_at = int(n * rng.uniform(0.5, 0.7))
        end_mrr = start_mrr * rng.uniform(0.65, 0.85)
        util_base = 55 + rng.uniform(-8, 8)
        b.build_timeline(n, lambda i, nn, s=start_mrr, e=end_mrr, st=step_at: s if i < st else e,
                          util_path=lambda i, nn, b=util_base: b + rng.uniform(-2, 2))
        b.finalize(renewal_in_days=rng.randint(30, 200),
                   last_qbr_days_ago=rng.randint(60, 180), days_since_contact=rng.randint(30, 150))
        builders.append(b)

    # Two large, deliberately illustrative accounts — same "big ARR" scale,
    # opposite risk stories, to make the risk-vs-health distinction concrete.

    # Sterling Capital: an established account (long tenure, so no new-logo
    # penalty) that just signed a fresh 3-year term — renewal is nowhere near.
    # Ticket volume is genuinely heavy (raw risk reads elevated), but almost
    # none of it is high-priority, and with no renewal pressure the final
    # health lands meaningfully better than the raw signal alone suggests.
    b = new_builder(name="Sterling Capital", industry="Financial Services", segment="Enterprise")
    used_names.add(b.name)
    n = 36
    start_mrr = rng.uniform(34000, 38000)
    b.build_timeline(n, lambda i, nn, s=start_mrr: s * (1 + 0.008 * i),
                      util_path=lambda i, nn: 74 + rng.uniform(-3, 3))
    b.finalize(term_length_months=36, contract_start_days_ago=45,
               renewal_in_days=36 * 30 - 45, last_qbr_days_ago=25,
               days_since_contact=rng.randint(5, 20), overdue_flag=False,
               tickets_12mo=60, pct_high_priority=60.0,
               auto_renew=True, product_tier="Enterprise")
    builders.append(b)

    # Ridgeline Technologies: established, paying fine, no support noise —
    # but has been dodging QBRs for over a year, contact has gone cold, and
    # renewal is a few weeks out. Pure engagement risk, amplified hard by
    # renewal proximity — raw risk reads moderate, final health reads critical.
    b = new_builder(name="Ridgeline Technologies", industry="Technology / SaaS", segment="Enterprise")
    used_names.add(b.name)
    n = 36
    flat_mrr = rng.uniform(32000, 39000)
    b.build_timeline(n, lambda i, nn, m=flat_mrr: m,
                      util_path=lambda i, nn: max(35, 60 - i * 0.5))
    b.finalize(renewal_in_days=30, last_qbr_days_ago=None,
               days_since_contact=350, overdue_flag=False,
               tickets_12mo=5, pct_high_priority=0.0,
               auto_renew=True, product_tier="Enterprise")
    builders.append(b)

    # New accounts — short tenure, partial (ragged) history.
    for _ in range(3):
        b = new_builder(segment=rng.choice(["Mid-Market", "SMB"]))
        n = rng.randint(2, 5)
        start_mrr = rng.uniform(3000, 12000)
        b.build_timeline(n, lambda i, nn, s=start_mrr: s * (1 + 0.05 * i),
                          util_path=lambda i, nn: 40 + i * 8)
        b.finalize(renewal_in_days=rng.randint(300, 360),
                   last_qbr_days_ago=None, days_since_contact=rng.randint(5, 35),
                   tickets_12mo=rng.randint(0, 4))
        builders.append(b)

    # ── Baseline fillers: stable/healthy accounts to round out the book ──
    while len(builders) < TARGET_ACCOUNTS:
        b = new_builder()
        n = rng.randint(24, 36)
        start_mrr = rng.uniform(2000, 18000)
        end_mrr = start_mrr * rng.uniform(0.95, 1.15)
        util_base = 62 + rng.uniform(-10, 15)
        b.build_timeline(n, lambda i, nn, s=start_mrr, e=end_mrr: s + (e - s) * (i / (nn - 1)),
                          util_path=lambda i, nn, b=util_base: b + rng.uniform(-3, 3))
        b.finalize(renewal_in_days=rng.randint(30, 360),
                   last_qbr_days_ago=rng.randint(20, 200), days_since_contact=rng.randint(5, 170),
                   overdue_flag=rng.random() < 0.05)
        builders.append(b)

    # ── Rescale in two groups so the top 5 accounts land at exactly
    #    TOP5_REVENUE_SHARE of total ARR, instead of one flat scale factor
    #    that would leave the book too evenly spread ──
    def _rescale_group(group, target_total):
        raw_total = sum(b.snapshot["avg_monthly_revenue_6mo"] * 12 for b in group)
        scale = target_total / raw_total if raw_total else 1.0
        for b in group:
            for row in b.timeline:
                row["mrr"] = round(row["mrr"] * scale, 2)
            recent = b.timeline[-6:]
            window = b.timeline[-36:]
            b.snapshot["avg_monthly_revenue_6mo"] = round(sum(r["mrr"] for r in recent) / len(recent), 2)
            b.snapshot["total_revenue_36mo"] = round(sum(r["mrr"] for r in window), 2)
            b.snapshot["entry_arr"] = round(b.snapshot["entry_arr"] * scale, 2)

    ranked = sorted(builders, key=lambda b: b.snapshot["avg_monthly_revenue_6mo"], reverse=True)
    top5, rest = ranked[:5], ranked[5:]
    _rescale_group(top5, TARGET_TOTAL_ARR * TOP5_REVENUE_SHARE)
    _rescale_group(rest, TARGET_TOTAL_ARR * (1 - TOP5_REVENUE_SHARE))

    # ── Concentrate 2 industries at ~DOMINANT_INDUSTRY_SHARE of total ARR,
    #    reassigning the largest reassignable accounts first so the biggest
    #    money clusters in a couple of verticals instead of spreading evenly.
    #    Named-example accounts keep the industry their story is tied to. ──
    dominant_target = TARGET_TOTAL_ARR * DOMINANT_INDUSTRY_SHARE
    dominant_sum = sum(b.snapshot["avg_monthly_revenue_6mo"] * 12 for b in builders
                        if b.snapshot["industry"] in DOMINANT_INDUSTRIES)
    reassignable = sorted(
        (b for b in builders if b.name not in FIXED_INDUSTRY_ACCOUNTS
         and b.snapshot["industry"] not in DOMINANT_INDUSTRIES),
        key=lambda b: b.snapshot["avg_monthly_revenue_6mo"], reverse=True,
    )
    toggle = 0
    for b in reassignable:
        if dominant_sum >= dominant_target:
            break
        b.snapshot["industry"] = DOMINANT_INDUSTRIES[toggle % 2]
        toggle += 1
        dominant_sum += b.snapshot["avg_monthly_revenue_6mo"] * 12

    snapshot = {b.account_id: b.snapshot for b in builders}
    timeline_rows = [row for b in builders for row in b.timeline]
    return snapshot, timeline_rows


# ── CSV serialisation (for the "Download sample CSV" links) ───────────

SNAPSHOT_COLUMNS = [
    "account_id", "account_name", "segment", "industry", "csm_owner", "customer_since",
    "product_tier", "seats_purchased", "contract_start", "renewal_date", "term_length_months",
    "auto_renew", "entry_arr", "last_qbr_date", "avg_monthly_revenue_6mo", "total_revenue_36mo",
    "tickets_12mo", "pct_high_priority", "days_since_contact", "overdue_flag",
    "seat_utilisation_pct", "active_user_pct",
]
TIMELINE_COLUMNS = ["account_id", "month", "mrr", "seat_utilisation_pct", "active_user_pct", "tickets_opened"]


def _csv_value(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, date):
        return v.strftime("%Y-%m-%d")
    return v


def snapshot_to_csv(snapshot):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(SNAPSHOT_COLUMNS)
    for account in snapshot.values():
        writer.writerow([_csv_value(account.get(c)) for c in SNAPSHOT_COLUMNS])
    return buf.getvalue()


def timeline_to_csv(timeline_rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(TIMELINE_COLUMNS)
    for row in timeline_rows:
        values = [_csv_value(row.get(c)) for c in TIMELINE_COLUMNS]
        values[1] = row["month"].strftime("%Y-%m")  # month formatted as YYYY-MM, not YYYY-MM-DD
        writer.writerow(values)
    return buf.getvalue()
