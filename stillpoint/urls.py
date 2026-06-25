from django.urls import path
from . import views


app_name = "stillpoint"

urlpatterns = [
    path('', views.timer, name='timer'),
]
