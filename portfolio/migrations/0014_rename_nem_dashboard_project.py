from django.db import migrations


def rename_nem_dashboard(apps, schema_editor):
    Project = apps.get_model('portfolio', 'Project')
    Project.objects.filter(slug='nem-fuelmix').update(
        title='NEM Dashboard',
        description=(
            "One home for Australia's eastern energy market: generation, wholesale prices, "
            'battery dispatch and east-coast gas-system conditions.'
        ),
        project_url='/nem/',
    )
    Project.objects.filter(slug='east-coast-gas-system-stress-monitor').update(
        project_url='/nem/flow-trace/',
    )


def restore_previous_names(apps, schema_editor):
    Project = apps.get_model('portfolio', 'Project')
    Project.objects.filter(slug='nem-fuelmix').update(
        title='NEM Fuel Generation Dashboard',
        description='A great and beautiful fuelmix nem data dashboard',
        project_url='/nem/',
    )
    Project.objects.filter(slug='east-coast-gas-system-stress-monitor').update(
        project_url='/gas/',
    )


class Migration(migrations.Migration):
    dependencies = [('portfolio', '0013_alter_blogpost_category_alter_project_category')]

    operations = [migrations.RunPython(rename_nem_dashboard, restore_previous_names)]
