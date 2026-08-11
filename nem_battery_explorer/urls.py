from django.urls import path

from . import views


app_name = 'nem_battery_explorer'

urlpatterns = [
    path('', views.explorer, name='explorer'),
    path('guide/', views.guide, name='guide'),
]
