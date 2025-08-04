from django.urls import path
from . import views


app_name = "nem_dashboard"

urlpatterns = [
    path('', views.dashboard, name='nem_dashboard'),
]
