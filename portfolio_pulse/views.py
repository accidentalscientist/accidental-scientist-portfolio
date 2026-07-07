from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .aggregate import build_dashboard_context
from .forms import PortfolioUploadForm
from .metrics import apply_timeline_overrides, enrich_snapshot_metrics
from .parsing import group_timeline_by_account, parse_snapshot, parse_timeline
from .sample_data import generate_sample, snapshot_to_csv, timeline_to_csv
from .scoring import score_portfolio


def _run_pipeline(snapshot_accounts, timeline_rows, today):
    """Shared by the real-upload path and the `?sample=1` path, so the
    sample can never diverge from what a real upload actually does.
    """
    timeline_by_account = group_timeline_by_account(timeline_rows) if timeline_rows else {}
    if timeline_by_account:
        snapshot_accounts = apply_timeline_overrides(snapshot_accounts, timeline_by_account)

    enriched = [enrich_snapshot_metrics(a) for a in snapshot_accounts.values()]
    scored = score_portfolio(enriched, today=today)
    return build_dashboard_context(scored, today, timeline_by_account or None)


def dashboard(request):
    today = timezone.localdate()

    if request.method == "GET" and request.GET.get("sample") == "1":
        snapshot_accounts, timeline_rows = generate_sample(today=today)
        context = _run_pipeline(snapshot_accounts, timeline_rows, today)
        context.update({"form": PortfolioUploadForm(), "has_data": True, "parse_errors": [], "loaded_sample": True})
        return render(request, "portfolio_pulse/dashboard.html", context)

    if request.method == "POST":
        form = PortfolioUploadForm(request.POST, request.FILES)
        if form.is_valid():
            timeline_file = form.cleaned_data.get("timeline_file")
            snapshot_accounts, errors = parse_snapshot(
                form.cleaned_data["snapshot_file"], require_revenue_fields=not timeline_file,
            )
            if not snapshot_accounts:
                return render(request, "portfolio_pulse/dashboard.html", {
                    "form": form, "has_data": False,
                    "parse_errors": errors or ["No valid rows found in that Snapshot file."],
                })

            timeline_rows = []
            if timeline_file:
                timeline_rows, timeline_errors, orphan_count = parse_timeline(
                    timeline_file, set(snapshot_accounts.keys()),
                )
                errors = errors + timeline_errors
                if orphan_count:
                    errors.append(f"Timeline: skipped {orphan_count} row(s) with no matching Snapshot account_id.")

            context = _run_pipeline(snapshot_accounts, timeline_rows, today)
            context.update({"form": PortfolioUploadForm(), "has_data": True, "parse_errors": errors})
            return render(request, "portfolio_pulse/dashboard.html", context)
    else:
        form = PortfolioUploadForm()

    return render(request, "portfolio_pulse/dashboard.html", {"form": form, "has_data": False})


def download_sample_snapshot(request):
    snapshot_accounts, _ = generate_sample(today=timezone.localdate())
    response = HttpResponse(snapshot_to_csv(snapshot_accounts), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="portfolio_pulse_sample_snapshot.csv"'
    return response


def download_sample_timeline(request):
    _, timeline_rows = generate_sample(today=timezone.localdate())
    response = HttpResponse(timeline_to_csv(timeline_rows), content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="portfolio_pulse_sample_timeline.csv"'
    return response
