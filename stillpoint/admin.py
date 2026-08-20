from django.contrib import admin
from .models import GuidedMeditation, StillpointSession


@admin.register(GuidedMeditation)
class GuidedMeditationAdmin(admin.ModelAdmin):
    list_display = ('title', 'order')
    list_editable = ('order',)
    search_fields = ('title',)


@admin.register(StillpointSession)
class StillpointSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'completed_at', 'duration_seconds', 'mode', 'guided_session')
    list_filter = ('mode', 'user')
    date_hierarchy = 'completed_at'
