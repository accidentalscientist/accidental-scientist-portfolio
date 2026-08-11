"""Admin-triggered refresh.

Mirrors the fuel-mix dashboard's post_save receiver, with one difference:
there is no uploaded file to parse, because every Bulletin Board report is
a public HTTP GET the server can make itself.

All three source groups are small enough to fetch inside the request. The
full weekly refresh is eleven reports and a few megabytes; the flow file
is the largest single piece at roughly 600 KB. Backfilling from the
archive is a different matter — tens of megabytes over many files — and
belongs in a management command run over SSH, not behind a Save button.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from . import services
from .models import GasDataRefresh

RUNNERS = {
    GasDataRefresh.Sources.WEEKLY: services.ingest_weekly,
    GasDataRefresh.Sources.TIME_SERIES: services.ingest_time_series,
    GasDataRefresh.Sources.REFERENCE: services.ingest_reference,
}


@receiver(post_save, sender=GasDataRefresh)
def run_refresh_on_create(sender, instance, created, **kwargs):
    if not created:
        return

    runner = RUNNERS.get(instance.sources, services.ingest_weekly)

    try:
        reports = runner()
        summary = services.summarise(reports)
        if any(r.get('error') for r in reports):
            summary = 'Completed with failures.\n' + summary
        summary = _append_margin(summary)
    except Exception as exc:  # never let a source problem 500 the admin save
        services.record_refresh(instance.pk, f'Refresh error: {exc}')
        return

    services.record_refresh(instance.pk, summary)


def _append_margin(summary):
    """Tell the operator how long until the next refresh is actually due.

    The rolling window means "when must I do this again" is the operative
    question after any refresh, and the answer belongs where the result is
    read rather than in a runbook nobody opens.
    """
    lines = []
    for row in services.coverage_report():
        if row['loses_data_if_skipped'] and row['days_until_loss'] is not None:
            lines.append(f"{row['source']}: current to {row['latest_gas_date']}, "
                         f"{row['days_until_loss']} days before the window drops data.")

    gaps = services.gas_day_gaps()
    if gaps:
        lines.append(f'Missing gas days: {len(gaps)} — run check_gas_coverage.')

    return summary + '\n\n' + '\n'.join(lines) if lines else summary
