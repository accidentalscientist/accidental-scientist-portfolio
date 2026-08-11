from django.apps import AppConfig


class GasMonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gas_monitor'
    verbose_name = 'East Coast Gas System Stress Monitor'

    def ready(self):
        from . import signals  # noqa: F401
