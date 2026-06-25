from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Project, BlogPost
from .forms import ContactForm
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.templatetags.static import static
import markdown2
from django.utils import timezone
import re



def home(request):
    current_project = Project.objects.order_by('-date').first()
    featured_post = BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED,
        is_featured=True,
        published__lte=timezone.now(),
    ).order_by('?').first()
    return render(request, 'portfolio/home.html', {'current_project': current_project, 'featured_post': featured_post})

def all_projects(request):
    projects = Project.objects.all().order_by('-date')
    return render(request, 'portfolio/projects.html', {'projects': projects})

def project_detail(request, slug):
    project = get_object_or_404(Project, slug=slug)
    return render(request, 'portfolio/project_detail.html', {'project': project})

def blog_list(request):
    published_qs = BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED,
        published__lte=timezone.now(),
    )

    category = request.GET.get('category', '')
    if category and category in dict(BlogPost.Category.choices):
        filtered_qs = published_qs.filter(category=category)
    else:
        category = ''
        filtered_qs = published_qs

    featured_post = published_qs.filter(is_featured=True).order_by('?').first()

    # All posts go into the list — the featured post is highlighted above, not removed
    paginator = Paginator(filtered_qs.order_by('-published'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portfolio/blog.html', {
        'featured_post': featured_post,
        'page_obj': page_obj,
        'active_category': category,
        'categories': BlogPost.Category.choices,
        'total_count': filtered_qs.count(),
    })    


def blog_detail(request, slug):
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        status=BlogPost.Status.PUBLISHED,
        published__lte=timezone.now(),
    )
    # Replace [[image1]], [[image2]] etc. with <img> tags before rendering
    content = post.content
    for i, img in enumerate(post.images.all()):
        placeholder = f"[[image{i+1}]]"
        img_tag = f'<figure><img src="{img.image.url}" alt="{img.caption}" style="max-width:100%;border-radius:8px;">{"<figcaption>" + img.caption + "</figcaption>" if img.caption else ""}</figure>'
        content = content.replace(placeholder, img_tag)

    markdown_extras = getattr(settings, "MARKDOWN2_EXTRAS", [])
    post.content_html = markdown2.markdown(content, extras=markdown_extras)
    post.summary_html = markdown2.markdown(post.summary, extras=markdown_extras)

    # Absolute URL for OpenGraph image
    if post.image:
        post.image_absolute_url = request.build_absolute_uri(post.image.url)
    else:
        post.image_absolute_url = request.build_absolute_uri(static('images/favicon.png'))

    return render(request, 'portfolio/blog_detail.html', {'post': post, 'include_markdown_css': True})


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
