from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('portfolio', '0014_rename_nem_dashboard_project')]

    operations = [
        migrations.AddField(
            model_name='project',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
