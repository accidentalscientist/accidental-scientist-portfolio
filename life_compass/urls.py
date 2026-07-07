from django.urls import path

from . import views


app_name = "life_compass"

urlpatterns = [
    path("", views.home, name="home"),
    path("index.html", views.home, name="index_html"),
    path("strategy.html", views.strategy, name="strategy"),
    path("execution.html", views.execution, name="execution"),
]