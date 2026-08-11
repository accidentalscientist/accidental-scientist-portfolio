from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nem_battery_explorer', '0002_battery_data_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='batterydailysummary',
            name='benchmark_energy_value',
            field=models.FloatField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='batterydailysummary',
            name='benchmark_version',
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name='batterydailysummary',
            name='opportunity_capture_ratio',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
