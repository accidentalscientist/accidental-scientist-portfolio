from django.apps import AppConfig

class NemDashboardConfig(AppConfig):
    name = 'nem_dashboard'

    def ready(self):
        import nem_dashboard.signals
