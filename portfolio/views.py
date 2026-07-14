import logging
from types import SimpleNamespace

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse
from .models import Project, BlogPost
from .forms import ContactForm
from django.core.mail import EmailMessage
from django.core.cache import cache
from django.core.paginator import Paginator
from django.conf import settings
from django.templatetags.static import static
import markdown2
from django.utils import timezone
import re

logger = logging.getLogger(__name__)

# Light, invisible contact throttle: max submissions per IP per window.
CONTACT_MAX_PER_WINDOW = 5
CONTACT_WINDOW_SECONDS = 600  # 10 minutes


def _client_ip(request):
    """Best-effort client IP, honouring the proxy header set by Nginx."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def robots_txt(request):
    """Served at /robots.txt — allows crawling and points to the sitemap."""
    from django.http import HttpResponse
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /markdownx/",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")



# Tools with no Project row of their own (standalone apps, not admin-managed
# portfolio entries). One definition here drives both the homepage's daily
# rotation and the "external tool" rows on the Projects page — add a tool
# once here rather than wiring a new template block + view flag for it.
EXTERNAL_TOOLS = [
    {
        'title': 'Life Compass',
        'slug': 'life-compass',
        'url_name': 'life_compass:home',
        'category': Project.Category.SPORT,
        'description': 'A public demo of a local-first strategy and execution dashboard with generic demo data only.',
    },
    {
        'title': 'Portfolio Pulse',
        'slug': 'portfolio-pulse',
        'url_name': 'portfolio_pulse:dashboard',
        'category': Project.Category.COMMERCIAL,
        'description': 'Upload a book of business and get an instant health read: portfolio score, NRR/GRR, renewal risk, and silent decliners, with the scoring fully explained.',
    },
]


def _external_tools():
    """EXTERNAL_TOOLS with URLs resolved, as attribute-access objects so
    templates can treat them the same way as a Project instance."""
    category_labels = dict(Project.Category.choices)
    return [
        SimpleNamespace(
            title=t['title'], slug=t['slug'], category=t['category'],
            category_display=category_labels[t['category']],
            description=t['description'], project_url=reverse(t['url_name']),
        )
        for t in EXTERNAL_TOOLS
    ]


def _homepage_tools():
    # NEM already has its own dedicated hero CTA ("Explore the NEM Dashboard"),
    # so it's excluded here to avoid the homepage pointing at it twice.
    db_tools = list(
        Project.objects.exclude(Q(project_url__isnull=True) | Q(project_url=''))
        .exclude(slug='nem-fuelmix')
        .order_by('slug')
    )
    return db_tools + _external_tools()


def home(request):
    tools = _homepage_tools()
    # Deterministic per-day rotation (not per-visit) — stable all day, changes
    # daily, and needs no stored state.
    current_project = tools[timezone.localdate().toordinal() % len(tools)] if tools else None
    featured_post = BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED,
        is_featured=True,
        published__lte=timezone.now(),
    ).order_by('?').first()
    return render(request, 'portfolio/home.html', {'current_project': current_project, 'featured_post': featured_post})

def all_projects(request):
    projects = Project.objects.all().order_by('-date')
    category = request.GET.get('category', '')
    if category and category in dict(Project.Category.choices):
        projects = projects.filter(category=category)
    else:
        category = ''
    external_tools = [t for t in _external_tools() if not category or t.category == category]
    return render(request, 'portfolio/projects.html', {
        'projects': projects,
        'categories': Project.Category.choices,
        'active_category': category,
        'external_tools': external_tools,
    })

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
    # Replace [[image1]], [[image2]] etc. with <img> tags before rendering.
    # Captions are escaped so a stray "<", "&" etc. displays as text (hygiene).
    from django.utils.html import escape
    content = post.content
    for i, img in enumerate(post.images.all()):
        placeholder = f"[[image{i+1}]]"
        caption = escape(img.caption) if img.caption else ""
        figcaption = f"<figcaption>{caption}</figcaption>" if caption else ""
        img_tag = (
            f'<figure><img src="{img.image.url}" alt="{caption}" '
            f'style="max-width:100%;border-radius:8px;">{figcaption}</figure>'
        )
        content = content.replace(placeholder, img_tag)

    markdown_extras = getattr(settings, "MARKDOWN2_EXTRAS", [])
    post.content_html = markdown2.markdown(content, extras=markdown_extras)
    post.summary_html = markdown2.markdown(post.summary, extras=markdown_extras)

    # Absolute URL for OpenGraph image (falls back to the branded share image)
    if post.image:
        post.image_absolute_url = request.build_absolute_uri(post.image.url)
    else:
        post.image_absolute_url = request.build_absolute_uri(static('images/share-default.png'))

    return render(request, 'portfolio/blog_detail.html', {'post': post, 'include_markdown_css': True})


def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Honeypot: a bot filled the hidden field — pretend success, send nothing.
            if form.cleaned_data.get('website'):
                logger.info("Contact honeypot triggered from %s", _client_ip(request))
                messages.success(request, "Thanks for your message. I'll get back to you soon!")
                return render(request, 'portfolio/contact.html', {'form': ContactForm(), 'redirect': True})

            # Light per-IP rate limit (invisible unless someone is abusing the form).
            ip = _client_ip(request)
            throttle_key = f"contact-throttle:{ip}"
            attempts = cache.get(throttle_key, 0)
            if attempts >= CONTACT_MAX_PER_WINDOW:
                messages.error(request, "You've sent a few messages already; please try again a little later.")
                return render(request, 'portfolio/contact.html', {'form': form})
            cache.set(throttle_key, attempts + 1, CONTACT_WINDOW_SECONDS)

            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']
            full_message = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"

            sent = 0
            try:
                if not settings.CONTACT_EMAIL:
                    raise ValueError("CONTACT_EMAIL is not configured, nowhere to deliver this message.")
                sent = EmailMessage(
                    subject=f"Contact form: {name}",
                    body=full_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[settings.CONTACT_EMAIL],
                    reply_to=[email],
                ).send(fail_silently=False)
            except Exception:
                sent = 0
                logger.exception("Contact form email failed to send")

            if not sent:
                # EmailMessage.send() returns 0 (no exception) when it has no valid
                # recipients — that used to look identical to success from here.
                if not settings.CONTACT_EMAIL:
                    logger.error("Contact form submission dropped: CONTACT_EMAIL is not set.")
                messages.error(
                    request,
                    "Sorry, something went wrong sending your message. "
                    "Please email me directly at contact@accidentalscientist.net.",
                )
                return render(request, 'portfolio/contact.html', {'form': form})

            messages.success(request, "Thanks for your message. I'll get back to you soon!")
            return render(request, 'portfolio/contact.html', {'form': ContactForm(), 'redirect': True})
    else:
        form = ContactForm()

    return render(request, 'portfolio/contact.html', {'form': form})
