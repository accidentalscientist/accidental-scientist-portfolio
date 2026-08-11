from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('nem_dashboard', '0003_fueldataupload_result_alter_fueldataupload_csv_file')]

    operations = [
        migrations.AddConstraint(
            model_name='fuelgenerationdata',
            constraint=models.UniqueConstraint(
                fields=('timestamp', 'state', 'fuel_type'),
                name='uniq_fuel_generation_interval',
            ),
        ),
        migrations.AddIndex(
            model_name='fuelgenerationdata',
            index=models.Index(fields=['timestamp'], name='nem_dashboa_timesta_d8c4d0_idx'),
        ),
    ]
