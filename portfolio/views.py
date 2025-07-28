from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Project, BlogPost
from .forms import ContactForm
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.templatetags.static import static
import markdown2
import random
from django.utils import timezone
import re



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
    featured_posts = featured_posts[:4]
    post_list = BlogPost.objects.filter(published__isnull=False).order_by('-published')
    paginator = Paginator(post_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'portfolio/blog.html', {
        'featured_posts': featured_posts,
        'page_obj': page_obj
    })    


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug)
    markdown_extras = getattr(settings, "MARKDOWN2_EXTRAS", [])

    # Replace [[image1]], [[image2]] etc. with <img> tags
    content = post.content
    for i, img in enumerate(post.images.all()):
        placeholder = f"[[image{i+1}]]"
        img_tag = f'<img src="{img.image.url}" alt="{img.caption}" style="max-width:100%;">'
        content = content.replace(placeholder, img_tag)

    # Markdown rendering with extras
    post.content_html = markdown2.markdown(content, extras=markdown_extras)
    post.summary_html = markdown2.markdown(post.summary, extras=markdown_extras)

    # Absolute URL for OpenGraph image
    if post.image:
        post.image_absolute_url = request.build_absolute_uri(post.image.url)
    else:
        post.image_absolute_url = request.build_absolute_uri(static('images/favicon.png'))

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
                reply_to=[email]
            )
            messages.success(request, "Thanks for your message. I'll get back to you soon!")
            form = ContactForm()
            return render(request, 'portfolio/contact.html', {'form': form, 'redirect': True})

    else:
        form = ContactForm() 

    return render(request, 'portfolio/contact.html', {'form': form})


