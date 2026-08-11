from datetime import datetime, timezone

from django.db import migrations


KNOWN_UPDATES = {
    'stillpoint': datetime(2026, 8, 4, 0, 0, tzinfo=timezone.utc),
    'nem-fuelmix': datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc),
    'east-coast-gas-system-stress-monitor': datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc),
}


def seed_known_updates(apps, schema_editor):
    Project = apps.get_model('portfolio', 'Project')
    for slug, updated_at in KNOWN_UPDATES.items():
        Project.objects.filter(slug=slug).update(updated_at=updated_at)


class Migration(migrations.Migration):
    dependencies = [('portfolio', '0015_project_updated_at')]

    operations = [migrations.RunPython(seed_known_updates, migrations.RunPython.noop)]
