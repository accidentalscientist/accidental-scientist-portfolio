from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('projects/', views.all_projects, name='projects'),
    path('projects/<int:id>/', views.project_detail, name='project_detail'),
    path('blog/', views.blog_list, name='blog'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('contact/', views.contact_view, name='contact'),
]