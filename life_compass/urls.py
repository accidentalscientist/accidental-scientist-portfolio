from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


app_name = "life_compass"

urlpatterns = [
    path("", views.home, name="home"),
    path("strategy/", views.strategy, name="strategy"),
    path("execution/", views.execution, name="execution"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="life_compass/login.html", redirect_authenticated_user=True),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="/projects/"), name="logout"),
    path("api/data/", views.sync_data, name="sync_data"),
]
