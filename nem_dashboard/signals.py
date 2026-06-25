import csv
from io import TextIOWrapper
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


def _parse_timestamp(raw):
    for fmt in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


@receiver(post_save, sender=FuelDataUpload)
def parse_csv_on_upload(sender, instance, created, **kwargs):
    if not created:
        return

    file = instance.csv_file.open()
    reader = csv.DictReader(TextIOWrapper(file, encoding='utf-8'))

    rows = []
    seen_timestamps = set()
    for row in reader:
        raw_timestamp = row['DateTime'].strip()
        if not raw_timestamp or not row['Supply'].strip():
            continue  # Skip blanks or bad rows

        timestamp = _parse_timestamp(raw_timestamp)
        if timestamp is None:
            print(f"⚠️ Skipping bad date format: {raw_timestamp}")
            continue

        if timezone.is_naive(timestamp):
            timestamp = timezone.make_aware(timestamp, timezone.get_current_timezone())

        seen_timestamps.add(timestamp)
        rows.append(FuelGenerationData(
            timestamp=timestamp,
            state=row['State'].strip(),
            fuel_type=row['Fuel Type'].strip(),
            supply_mw=float(row['Supply'])
        ))

    # Re-uploading the same snapshot should replace it, not double-count it.
    if seen_timestamps:
        FuelGenerationData.objects.filter(timestamp__in=seen_timestamps).delete()

    FuelGenerationData.objects.bulk_create(rows)
