from django.urls import path
from . import views

app_name = "portfolio_pulse"

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('sample/snapshot.csv', views.download_sample_snapshot, name='download_sample_snapshot'),
    path('sample/timeline.csv', views.download_sample_timeline, name='download_sample_timeline'),
]
