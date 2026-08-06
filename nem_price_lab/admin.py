from django.contrib import admin

from .models import ForecastPoint, ForecastRun, PriceDataUpload, RegionPrice, RegionWeather


@admin.register(PriceDataUpload)
class PriceDataUploadAdmin(admin.ModelAdmin):
    list_display = ('uploaded_at', 'csv_file', 'result')
    readonly_fields = ('uploaded_at', 'result')


@admin.register(RegionPrice)
class RegionPriceAdmin(admin.ModelAdmin):
    list_display = ('interval_end', 'region', 'rrp', 'total_demand')
    list_filter = ('region',)
    date_hierarchy = 'interval_end'


@admin.register(RegionWeather)
class RegionWeatherAdmin(admin.ModelAdmin):
    list_display = ('interval_end', 'region', 'kind', 'temperature_c')
    list_filter = ('region', 'kind')
    date_hierarchy = 'interval_end'


class ForecastPointInline(admin.TabularInline):
    model = ForecastPoint
    extra = 0
    can_delete = False
    readonly_fields = ('interval_end', 'predicted_rrp')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = ('issued_at', 'region', 'model_key', 'horizon_days', 'temperature_source')
    list_filter = ('region', 'model_key', 'temperature_source')
    date_hierarchy = 'issued_at'
    readonly_fields = ('created_at',)
    inlines = [ForecastPointInline]
