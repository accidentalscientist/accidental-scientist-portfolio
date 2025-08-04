from django.contrib import admin
from .models import FuelDataUpload, FuelGenerationData

admin.site.register(FuelDataUpload)
admin.site.register(FuelGenerationData)


#class FuelAdmin(admin.ModelAdmin):
#    list_display = ('timestamp', 'state', 'fuel_type', 'supply_mw')
#    list_filter = ('state', 'fuel_type', 'timestamp')
#    search_fields = ('fuel_type',)