from django.urls import path

from . import views

app_name = 'nem_price_lab'

urlpatterns = [
    path('', views.lab, name='lab'),
]
