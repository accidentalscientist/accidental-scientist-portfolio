from django.contrib import admin

from .models import (
    Basin, ConnectionPoint, Facility, FlowForecast, FlowObservation, GasDataRefresh,
    LinepackAdequacy, LinepackZone, Location, MissingSubmission, NameplateRating,
    SourceCoverage,
)


@admin.register(GasDataRefresh)
class GasDataRefreshAdmin(admin.ModelAdmin):
    list_display = ('requested_at', 'sources', 'result')
    readonly_fields = ('requested_at', 'result')


@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('facility_id', 'name', 'facility_type', 'operating_state', 'operator_name')
    list_filter = ('facility_type', 'operating_state')
    search_fields = ('name', 'short_name', 'operator_name')


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('location_id', 'name', 'location_type', 'state')
    list_filter = ('location_type', 'state')
    search_fields = ('name',)


@admin.register(ConnectionPoint)
class ConnectionPointAdmin(admin.ModelAdmin):
    list_display = ('connection_point_id', 'name', 'facility', 'flow_direction',
                    'state_name', 'demand_zone')
    list_filter = ('flow_direction', 'state_name')
    search_fields = ('name', 'demand_zone')
    raw_id_fields = ('facility', 'location')


@admin.register(NameplateRating)
class NameplateRatingAdmin(admin.ModelAdmin):
    list_display = ('facility', 'capacity_type', 'capacity_tj', 'effective_date',
                    'receipt_location_name', 'delivery_location_name')
    list_filter = ('capacity_type', 'flow_direction')
    search_fields = ('facility__name',)
    raw_id_fields = ('facility',)
    date_hierarchy = 'effective_date'


@admin.register(Basin)
class BasinAdmin(admin.ModelAdmin):
    list_display = ('basin_id', 'name')


@admin.register(LinepackZone)
class LinepackZoneAdmin(admin.ModelAdmin):
    list_display = ('code', 'operator')
    search_fields = ('code', 'operator')


@admin.register(FlowObservation)
class FlowObservationAdmin(admin.ModelAdmin):
    list_display = ('gas_date', 'facility', 'location', 'demand_tj', 'supply_tj',
                    'held_in_storage_tj', 'source_last_updated')
    list_filter = ('state', 'facility__facility_type')
    date_hierarchy = 'gas_date'
    raw_id_fields = ('facility', 'location')
    search_fields = ('facility__name',)


@admin.register(FlowForecast)
class FlowForecastAdmin(admin.ModelAdmin):
    list_display = ('gas_date', 'facility', 'location', 'demand_tj', 'supply_tj')
    list_filter = ('state',)
    date_hierarchy = 'gas_date'
    raw_id_fields = ('facility', 'location')


@admin.register(LinepackAdequacy)
class LinepackAdequacyAdmin(admin.ModelAdmin):
    list_display = ('gas_date', 'facility', 'flag', 'description')
    list_filter = ('flag',)
    date_hierarchy = 'gas_date'
    raw_id_fields = ('facility',)


@admin.register(MissingSubmission)
class MissingSubmissionAdmin(admin.ModelAdmin):
    list_display = ('gas_date', 'facility', 'connection_point_id')
    date_hierarchy = 'gas_date'
    raw_id_fields = ('facility',)


@admin.register(SourceCoverage)
class SourceCoverageAdmin(admin.ModelAdmin):
    list_display = ('source', 'earliest_gas_date', 'latest_gas_date', 'rows_stored', 'last_run_at')
    readonly_fields = ('source', 'last_run_at', 'earliest_gas_date', 'latest_gas_date',
                       'rows_stored', 'note')
