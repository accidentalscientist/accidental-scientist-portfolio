"""Parse an admin-uploaded AEMO price CSV as soon as it is saved.

Mirrors the fuel-mix dashboard's upload flow so the weekly ritual is the
same muscle memory: download the month's file from AEMO, upload it here.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .ingest import IngestError, parse_price_csv
from .models import PriceDataUpload
from .services import upsert_prices


def _set_result(instance, text):
    # update() rather than save() so this handler does not re-enter itself.
    PriceDataUpload.objects.filter(pk=instance.pk).update(result=text[:2000])


@receiver(post_save, sender=PriceDataUpload)
def parse_price_csv_on_upload(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        raw = instance.csv_file.open('rb').read()
        rows, report = parse_price_csv(raw.decode('utf-8-sig', errors='replace'))
        stored = upsert_prices(rows)
    except IngestError as exc:
        _set_result(instance, f'Import failed: {exc}')
        return
    except Exception as exc:  # a malformed file must never 500 the admin
        _set_result(instance, f'Import error: {exc}')
        return

    if not rows:
        _set_result(instance, 'Import found no usable rows.')
        return

    summary = (
        f"Stored {stored} 30-minute intervals for "
        f"{', '.join(report['regions']) or 'no region'}: "
        f"{report['first']:%Y-%m-%d %H:%M} to {report['last']:%Y-%m-%d %H:%M}. "
        f"Skipped {report['skipped']} rows."
    )
    if report['issues']:
        summary += ' Issues: ' + '; '.join(report['issues'])
    _set_result(instance, summary)
