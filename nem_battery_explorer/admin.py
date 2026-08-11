from django.contrib import admin

from .models import (
    BatteryAsset,
    BatteryDailySummary,
    BatteryDataRefresh,
    BatteryDispatchInterval,
    BatteryRegistration,
    RegionPriceInterval,
)


class BatteryRegistrationInline(admin.TabularInline):
    model = BatteryRegistration
    extra = 0
    fields = (
        'duid',
        'direction_model',
        'effective_from',
        'effective_to',
        'power_capacity_mw',
        'storage_capacity_mwh',
        'source_registry_version',
    )


@admin.register(BatteryAsset)
class BatteryAssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'commitment_status', 'is_spike_cohort')
    list_filter = ('region', 'commitment_status', 'is_spike_cohort')
    search_fields = ('name', 'slug', 'owner', 'registrations__duid')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [BatteryRegistrationInline]


@admin.register(BatteryRegistration)
class BatteryRegistrationAdmin(admin.ModelAdmin):
    list_display = (
        'duid',
        'asset',
        'direction_model',
        'effective_from',
        'effective_to',
        'power_capacity_mw',
        'storage_capacity_mwh',
    )
    list_filter = ('direction_model', 'asset__region')
    search_fields = ('duid', 'asset__name', 'unit_name')


@admin.register(BatteryDataRefresh)
class BatteryDataRefreshAdmin(admin.ModelAdmin):
    list_display = (
        'started_at',
        'requested_start',
        'requested_end',
        'completed_through',
        'status',
        'calculation_version',
    )
    list_filter = ('status', 'calculation_version')
    readonly_fields = (
        'started_at',
        'finished_at',
        'source_receipts',
        'warnings',
        'error',
    )


@admin.register(BatteryDailySummary)
class BatteryDailySummaryAdmin(admin.ModelAdmin):
    list_display = (
        'operating_date',
        'asset',
        'quality_status',
        'interval_count',
        'equivalent_cycles',
        'observable_gross_value',
    )
    list_filter = ('quality_status', 'asset__region', 'calculation_version')
    search_fields = ('asset__name',)
    date_hierarchy = 'operating_date'
    readonly_fields = ('calculated_at',)


@admin.register(RegionPriceInterval)
class RegionPriceIntervalAdmin(admin.ModelAdmin):
    list_display = ('interval_end', 'region', 'rrp', 'source_file')
    list_filter = ('region', 'operating_date')
    date_hierarchy = 'operating_date'


@admin.register(BatteryDispatchInterval)
class BatteryDispatchIntervalAdmin(admin.ModelAdmin):
    list_display = (
        'interval_end',
        'registration',
        'scada_mw',
        'energy_storage_mwh',
        'observable_gross_value',
    )
    list_filter = ('operating_date', 'registration__asset__region')
    search_fields = ('registration__duid', 'registration__asset__name')
    date_hierarchy = 'operating_date'
