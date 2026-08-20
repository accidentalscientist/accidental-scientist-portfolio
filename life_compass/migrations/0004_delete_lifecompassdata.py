from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('life_compass', '0003_migrate_blob_data'),
    ]

    operations = [
        migrations.DeleteModel(
            name='LifeCompassData',
        ),
    ]
