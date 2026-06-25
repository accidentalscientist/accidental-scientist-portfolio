from django.contrib import admin
from .models import GuidedMeditation


@admin.register(GuidedMeditation)
class GuidedMeditationAdmin(admin.ModelAdmin):
    list_display = ('title', 'order')
    list_editable = ('order',)
    search_fields = ('title',)
