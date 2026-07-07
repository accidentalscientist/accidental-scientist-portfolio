"""
Parses the two Portfolio Pulse CSV shapes — the Snapshot (one row per
account) and the Timeline (one row per account per month) — into plain
dicts. Pure and Django-free: no persistence, no HTTP.

Tolerant by design: a bad row is skipped and counted rather than aborting
the whole import, except for missing required columns, which fail fast
with an actionable message.
"""
import csv
import io
from datetime import date, datetime

INDUSTRY_CHOICES = [
    "Financial Services", "Logistics & Supply Chain", "Manufacturing",
    "Retail & E-commerce", "Healthcare", "Technology / SaaS",
    "Professional Services", "Media & Marketing",
]
INDUSTRY_FALLBACK = "Other"

SEGMENT_CHOICES = ["Enterprise", "Mid-Market", "SMB"]
SEGMENT_FALLBACK = "Mid-Market"

# ── Snapshot schema ───────────────────────────────────────────────────
SNAPSHOT_REQUIRED_BASE = {
    "account_id", "account_name", "segment", "industry", "csm_owner",
    "customer_since", "contract_start", "renewal_date", "auto_renew",
}
# Required only when no Timeline is uploaded (otherwise computed from it).
SNAPSHOT_REVENUE_FIELDS = {"avg_monthly_revenue_6mo", "total_revenue_36mo"}
SNAPSHOT_OPTIONAL = {
    "product_tier", "seats_purchased", "term_length_months", "entry_arr",
    "last_qbr_date", "tickets_12mo", "pct_high_priority", "days_since_contact",
    "overdue_flag", "seat_utilisation_pct", "active_user_pct",
}

# ── Timeline schema ────────────────────────────────────────────────────
TIMELINE_REQUIRED = {"account_id", "month", "mrr"}
TIMELINE_OPTIONAL = {"seat_utilisation_pct", "active_user_pct", "tickets_opened"}


class ParseResult:
    def __init__(self, rows, errors, skipped=0):
        self.rows = rows
        self.errors = errors
        self.skipped = skipped


def _clean(raw):
    return (raw or "").strip()


def _parse_date(raw):
    raw = _clean(raw)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_month(raw):
    """'YYYY-MM' -> date(year, month, 1), used as a sortable bucket key."""
    raw = _clean(raw)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m").date().replace(day=1)
    except ValueError:
        return None


def _parse_bool(raw):
    raw = _clean(raw).upper()
    if raw in ("TRUE", "1", "YES"):
        return True
    if raw in ("FALSE", "0", "NO"):
        return False
    return None


def _parse_float(raw, lo=None, hi=None):
    raw = _clean(raw)
    if not raw:
        return None
    try:
        val = float(raw.replace(",", "").replace("$", ""))
    except ValueError:
        return None
    if lo is not None:
        val = max(val, lo)
    if hi is not None:
        val = min(val, hi)
    return val


def _parse_int(raw):
    val = _parse_float(raw)
    return int(val) if val is not None else None


def parse_snapshot(file_obj, require_revenue_fields=True):
    """Returns (accounts: dict[account_id -> dict], errors: list[str])."""
    raw = file_obj.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))

    headers = set(reader.fieldnames or [])
    required = set(SNAPSHOT_REQUIRED_BASE)
    if require_revenue_fields:
        required |= SNAPSHOT_REVENUE_FIELDS
    missing = required - headers
    if missing:
        return {}, [f"Snapshot is missing required column(s): {', '.join(sorted(missing))}"]

    accounts = {}
    errors = []
    for line_no, row in enumerate(reader, start=2):
        account_id = _clean(row.get("account_id"))
        name = _clean(row.get("account_name"))
        if not account_id or not name:
            errors.append(f"Snapshot line {line_no}: missing account_id or account_name")
            continue

        customer_since = _parse_date(row.get("customer_since"))
        contract_start = _parse_date(row.get("contract_start"))
        renewal_date = _parse_date(row.get("renewal_date"))
        auto_renew = _parse_bool(row.get("auto_renew"))
        if None in (customer_since, contract_start, renewal_date, auto_renew):
            errors.append(f"Snapshot line {line_no}: bad date or auto_renew value for '{name}'")
            continue

        segment = _clean(row.get("segment"))
        if segment not in SEGMENT_CHOICES:
            segment = SEGMENT_FALLBACK

        industry = _clean(row.get("industry"))
        if industry not in INDUSTRY_CHOICES:
            industry = INDUSTRY_FALLBACK

        avg_monthly_revenue_6mo = _parse_float(row.get("avg_monthly_revenue_6mo"), lo=0)
        total_revenue_36mo = _parse_float(row.get("total_revenue_36mo"), lo=0)
        if require_revenue_fields and (avg_monthly_revenue_6mo is None or total_revenue_36mo is None):
            errors.append(f"Snapshot line {line_no}: non-numeric revenue field for '{name}'")
            continue

        accounts[account_id] = {
            "account_id": account_id,
            "account_name": name,
            "segment": segment,
            "industry": industry,
            "csm_owner": _clean(row.get("csm_owner")),
            "customer_since": customer_since,
            "product_tier": _clean(row.get("product_tier")) or None,
            "seats_purchased": _parse_int(row.get("seats_purchased")),
            "contract_start": contract_start,
            "renewal_date": renewal_date,
            "term_length_months": _parse_int(row.get("term_length_months")),
            "auto_renew": auto_renew,
            "entry_arr": _parse_float(row.get("entry_arr"), lo=0),
            "last_qbr_date": _parse_date(row.get("last_qbr_date")),
            "avg_monthly_revenue_6mo": avg_monthly_revenue_6mo,
            "total_revenue_36mo": total_revenue_36mo,
            "tickets_12mo": _parse_int(row.get("tickets_12mo")),
            "pct_high_priority": _parse_float(row.get("pct_high_priority"), lo=0, hi=100),
            "days_since_contact": _parse_int(row.get("days_since_contact")),
            "overdue_flag": _parse_bool(row.get("overdue_flag")),
            "seat_utilisation_pct": _parse_float(row.get("seat_utilisation_pct"), lo=0, hi=100),
            "active_user_pct": _parse_float(row.get("active_user_pct"), lo=0, hi=100),
        }

    return accounts, errors[:20]


def parse_timeline(file_obj, known_account_ids):
    """Returns (rows: list[dict], errors: list[str], orphan_count: int)."""
    raw = file_obj.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))

    headers = set(reader.fieldnames or [])
    missing = TIMELINE_REQUIRED - headers
    if missing:
        return [], [f"Timeline is missing required column(s): {', '.join(sorted(missing))}"], 0

    rows = []
    errors = []
    orphan_count = 0
    for line_no, row in enumerate(reader, start=2):
        account_id = _clean(row.get("account_id"))
        month = _parse_month(row.get("month"))
        mrr = _parse_float(row.get("mrr"), lo=0)

        if not account_id or month is None or mrr is None:
            errors.append(f"Timeline line {line_no}: bad account_id/month/mrr")
            continue
        if account_id not in known_account_ids:
            orphan_count += 1
            continue

        rows.append({
            "account_id": account_id,
            "month": month,
            "mrr": mrr,
            "seat_utilisation_pct": _parse_float(row.get("seat_utilisation_pct"), lo=0, hi=100),
            "active_user_pct": _parse_float(row.get("active_user_pct"), lo=0, hi=100),
            "tickets_opened": _parse_int(row.get("tickets_opened")),
        })

    return rows, errors[:20], orphan_count


def group_timeline_by_account(timeline_rows):
    """dict[account_id -> list[row]], each account's rows sorted by month."""
    by_account = {}
    for row in timeline_rows:
        by_account.setdefault(row["account_id"], []).append(row)
    for rows in by_account.values():
        rows.sort(key=lambda r: r["month"])
    return by_account
