from django.shortcuts import render, get_object_or_404
from .models import Project, BlogPost

def home(request):
    projects = Project.objects.order_by('-date')[:2]
    posts = BlogPost.objects.all()[:2]
    return render(request, 'portfolio/home.html', {'projects': projects, 'posts': posts})


def all_projects(request):
    projects = Project.objects.all().order_by('-date')
    return render(request, 'portfolio/projects.html', {'projects': projects})

def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(request, 'portfolio/project_detail.html', {'project': project})

def blog_list(request):
    posts = BlogPost.objects.all()
    return render(request, 'portfolio/blog.html', {'posts': posts})


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    return render(request, 'portfolio/blog_detail.html', {'post': post})