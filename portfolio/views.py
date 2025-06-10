from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Project, BlogPost
from .forms import ContactForm
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
import markdown2
import random
from django.utils import timezone



def home(request):
    projects = Project.objects.order_by('-date')[:2]
    featured_posts = list(BlogPost.objects.filter(is_featured=True, published__lte=timezone.now()))    # only show featured posts that are published
    random.shuffle(featured_posts)
    featured_posts = featured_posts[:3]  
    return render(request, 'portfolio/home.html', {'projects': projects, 'featured_posts': featured_posts})

def all_projects(request):
    projects = Project.objects.all().order_by('-date')
    return render(request, 'portfolio/projects.html', {'projects': projects})

def project_detail(request, id):
    project = get_object_or_404(Project, id=id)
    return render(request, 'portfolio/project_detail.html', {'project': project})

def blog_list(request):
    featured_posts = list(BlogPost.objects.filter(is_featured=True, published__lte=timezone.now()))
    random.shuffle(featured_posts)
    post_list = BlogPost.objects.filter(published__isnull=False).order_by('-published')
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'portfolio/blog.html', {
        'featured_posts': featured_posts,
        'page_obj': page_obj
    })    
    ##### original: before modifications
    #posts = BlogPost.objects.all()
    #return render(request, 'portfolio/blog.html', {'posts': posts})

def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    post.content_html = markdown2.markdown(post.content)
    post.summary_html = markdown2.markdown(post.summary)
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