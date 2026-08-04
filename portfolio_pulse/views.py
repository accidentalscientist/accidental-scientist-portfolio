from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .aggregate import build_dashboard_context
from .forms import PortfolioUploadForm
from .metrics import apply_timeline_overrides, enrich_snapshot_metrics
from .parsing import group_timeline_by_account, parse_snapshot, parse_timeline
from .sample_data import generate_sample, snapshot_to_csv, timeline_to_csv
from .scoring import DEFAULT_HEALTH_MODEL, HEALTH_MODELS, score_portfolio


def _valid_health_model(model_id):
    return model_id if model_id in HEALTH_MODELS else DEFAULT_HEALTH_MODEL


def _health_model_context(model_id):
    selected_model = _valid_health_model(model_id)
    return {
        "selected_health_model": {
            "id": selected_model,
            **HEALTH_MODELS[selected_model],
        },
        "health_model_options": [
            {"id": available_id, **model}
            for available_id, model in HEALTH_MODELS.items()
        ],
    }


def _run_pipeline(snapshot_accounts, timeline_rows, today, health_model=DEFAULT_HEALTH_MODEL):
    """Shared by the real-upload path and the `?sample=1` path, so the
    sample can never diverge from what a real upload actually does.
    """
    timeline_by_account = group_timeline_by_account(timeline_rows) if timeline_rows else {}
    if timeline_by_account:
        snapshot_accounts = apply_timeline_overrides(snapshot_accounts, timeline_by_account)

    enriched = [enrich_snapshot_metrics(a) for a in snapshot_accounts.values()]
    selected_model = _valid_health_model(health_model)
    scored = score_portfolio(enriched, today=today, model=selected_model)
    context = build_dashboard_context(scored, today, timeline_by_account or None)
    context.update(_health_model_context(selected_model))
    return context


def dashboard(request):
    today = timezone.localdate()

    if request.method == "GET" and request.GET.get("sample") == "ready":
        health_model = _valid_health_model(request.GET.get("health_model"))
        context = {
            "form": PortfolioUploadForm(initial={"health_model": health_model}),
            "has_data": False,
            "parse_errors": [],
            "sample_ready": True,
        }
        context.update(_health_model_context(health_model))
        return render(request, "portfolio_pulse/dashboard.html", context)

    if request.method == "GET" and request.GET.get("sample") == "1":
        health_model = _valid_health_model(request.GET.get("health_model"))
        snapshot_accounts, timeline_rows = generate_sample(today=today)
        context = _run_pipeline(snapshot_accounts, timeline_rows, today, health_model)
        context.update({
            "form": PortfolioUploadForm(initial={"health_model": health_model}),
            "has_data": True,
            "parse_errors": [],
            "loaded_sample": True,
        })
        return render(request, "portfolio_pulse/dashboard.html", context)

    if request.method == "POST":
        form = PortfolioUploadForm(request.POST, request.FILES)
        if form.is_valid():
            health_model = _valid_health_model(form.cleaned_data.get("health_model"))
            timeline_file = form.cleaned_data.get("timeline_file")
            snapshot_accounts, errors = parse_snapshot(
                form.cleaned_data["snapshot_file"], require_revenue_fields=not timeline_file,
            )
            if not snapshot_accounts:
                context = {
                    "form": form, "has_data": False,
                    "parse_errors": errors or ["No valid rows found in that Snapshot file."],
                }
                context.update(_health_model_context(health_model))
                return render(request, "portfolio_pulse/dashboard.html", context)

            timeline_rows = []
            if timeline_file:
                timeline_rows, timeline_errors, orphan_count = parse_timeline(
                    timeline_file, set(snapshot_accounts.keys()),
                )
                errors = errors + timeline_errors
                if orphan_count:
                    errors.append(f"Timeline: skipped {orphan_count} row(s) with no matching Snapshot account_id.")

            context = _run_pipeline(snapshot_accounts, timeline_rows, today, health_model)
            context.update({
                "form": PortfolioUploadForm(initial={"health_model": health_model}),
                "has_data": True,
                "parse_errors": errors,
            })
            return render(request, "portfolio_pulse/dashboard.html", context)
    else:
        form = PortfolioUploadForm()

    model_id = _valid_health_model(request.POST.get("health_model"))
    context = {"form": form, "has_data": False}
    context.update(_health_model_context(model_id))
    return render(request, "portfolio_pulse/dashboard.html", context)


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
