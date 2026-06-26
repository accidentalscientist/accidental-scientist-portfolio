from django.contrib import admin

from .models import FuelDataUpload, FuelGenerationData


@admin.register(FuelDataUpload)
class FuelDataUploadAdmin(admin.ModelAdmin):
    list_display = ('uploaded_at', 'csv_file', 'result')
    readonly_fields = ('uploaded_at', 'result')


@admin.register(FuelGenerationData)
class FuelGenerationDataAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'state', 'fuel_type', 'supply_mw')
    list_filter = ('state', 'fuel_type')
    search_fields = ('fuel_type', 'state')
