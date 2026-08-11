from django.urls import path

from . import views

app_name = 'gas_monitor'

urlpatterns = [
    path('', views.monitor, name='monitor'),
]
