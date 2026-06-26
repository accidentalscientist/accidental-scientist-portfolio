from django.urls import path
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('projects/', views.all_projects, name='projects'),
    path('projects/<slug:slug>/', views.project_detail, name='project_detail'),
    path('blog/', views.blog_list, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('about/', views.contact_view, name='about'),
    # Keep the old /contact/ working; send it to the canonical /about/.
    path('contact/', RedirectView.as_view(pattern_name='about', permanent=True), name='contact'),
]
