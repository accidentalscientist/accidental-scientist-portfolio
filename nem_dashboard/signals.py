import csv
from io import TextIOWrapper
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import FuelDataUpload, FuelGenerationData
from datetime import datetime

@receiver(post_save, sender=FuelDataUpload)
def parse_csv_on_upload(sender, instance, created, **kwargs):
    if not created:
        return

    file = instance.csv_file.open()
    reader = csv.DictReader(TextIOWrapper(file, encoding='utf-8'))

    rows = []
    for row in reader:
        raw_timestamp = row['DateTime'].strip()
        if not raw_timestamp or not row['Supply'].strip():
            continue  # Skip blanks or bad rows

        try:
            timestamp = datetime.strptime(raw_timestamp, "%d/%m/%Y %H:%M")
        except ValueError:
            print(f"⚠️ Skipping bad date format: {raw_timestamp}")
            continue

        rows.append(FuelGenerationData(
            timestamp=timestamp,
            state=row['State'].strip(),
            fuel_type=row['Fuel Type'].strip(),
            supply_mw=float(row['Supply'])
        ))

    FuelGenerationData.objects.bulk_create(rows)
