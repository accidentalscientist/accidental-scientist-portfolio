from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Project, BlogPost
from .forms import ContactForm
from django.core.mail import send_mail
from django.conf import settings

def home(request):
    projects = Project.objects.order_by('-date')[:2]
    posts = BlogPost.objects.all()[:2]
    return render(request, 'portfolio/home.html', {'projects': projects, 'posts': posts})

def all_projects(request):
    projects = Project.objects.all().order_by('-date')
    return render(request, 'portfolio/projects.html', {'projects': projects})

def project_detail(request, id):
    project = get_object_or_404(Project, id=id)
    return render(request, 'portfolio/project_detail.html', {'project': project})

def blog_list(request):
    posts = BlogPost.objects.all()
    return render(request, 'portfolio/blog.html', {'posts': posts})

def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    return render(request, 'portfolio/blog_detail.html', {'post': post})

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']

            full_message = f"Name: {name}\nEmail: {email}\nMessage:\n{message}"

            send_mail(
                subject=f"Contact Form Submission from {name}",
                message=full_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_EMAIL],
                fail_silently=False,
            )
            return redirect('contact_success')

    else:
        form = ContactForm()
        
    return render(request, 'portfolio/contact.html', {'form': form})

def contact_success(request):
    messages.success(request, "Your message has been sent successfully!")
    return render(request, 'portfolio/contact_success.html')