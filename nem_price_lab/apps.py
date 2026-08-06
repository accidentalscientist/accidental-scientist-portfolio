from django.apps import AppConfig


class NemPriceLabConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nem_price_lab'
    verbose_name = 'NEM Price Predictor Lab'

    def ready(self):
        from . import signals  # noqa: F401
