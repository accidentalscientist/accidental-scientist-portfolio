from django.urls import path

from . import views

app_name = 'world_lens'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
