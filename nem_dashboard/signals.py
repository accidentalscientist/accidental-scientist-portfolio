import csv
import io
from datetime import datetime

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import FuelDataUpload, FuelGenerationData

# AEMO exports come in a couple of flavours — 24-hour and 12-hour am/pm.
TIMESTAMP_FORMATS = (
    "%d/%m/%Y %H:%M",        # 28/07/2025 17:55
    "%d/%m/%Y %I:%M %p",     # 25/06/2026 10:10 am
    "%d/%m/%Y %I:%M%p",      # 25/06/2026 10:10am
)
REQUIRED_COLUMNS = {"DateTime", "State", "Fuel Type", "Supply"}


def _parse_timestamp(raw):
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _set_result(instance, text):
    # Use update() so we don't re-trigger this post_save handler.
    FuelDataUpload.objects.filter(pk=instance.pk).update(result=text[:2000])


@receiver(post_save, sender=FuelDataUpload)
def parse_csv_on_upload(sender, instance, created, **kwargs):
    if not created:
        return

    imported = 0
    skipped = 0
    errors = []
    rows = []
    seen_timestamps = set()

    try:
        raw = instance.csv_file.open('rb').read()
        text = raw.decode('utf-8-sig', errors='replace')
        reader = csv.DictReader(io.StringIO(text))

        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            _set_result(instance, f"Import failed: missing columns: {', '.join(sorted(missing))}")
            return

        for line_no, row in enumerate(reader, start=2):
            raw_ts = (row.get('DateTime') or '').strip()
            raw_supply = (row.get('Supply') or '').strip()
            if not raw_ts or not raw_supply:
                skipped += 1
                continue

            ts = _parse_timestamp(raw_ts)
            if ts is None:
                skipped += 1
                if len(errors) < 10:
                    errors.append(f"line {line_no}: bad date '{raw_ts}'")
                continue

            try:
                supply = float(raw_supply)
            except ValueError:
                skipped += 1
                if len(errors) < 10:
                    errors.append(f"line {line_no}: non-numeric supply '{raw_supply}'")
                continue

            if timezone.is_naive(ts):
                ts = timezone.make_aware(ts, timezone.get_current_timezone())

            seen_timestamps.add(ts)
            rows.append(FuelGenerationData(
                timestamp=ts,
                state=(row.get('State') or '').strip(),
                fuel_type=(row.get('Fuel Type') or '').strip(),
                supply_mw=supply,
            ))
            imported += 1

        # Re-uploading the same snapshot replaces it rather than double-counting.
        if seen_timestamps:
            FuelGenerationData.objects.filter(timestamp__in=seen_timestamps).delete()
        FuelGenerationData.objects.bulk_create(rows)

    except Exception as exc:  # never let a bad file 500 the admin save
        _set_result(instance, f"Import error: {exc}")
        return

    summary = f"Imported {imported} rows, skipped {skipped}."
    if errors:
        summary += " Issues: " + "; ".join(errors)
    _set_result(instance, summary)
