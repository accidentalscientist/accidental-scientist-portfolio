import logging
from datetime import date
from types import SimpleNamespace

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse
from .models import Project, BlogPost, Contact
from .forms import ContactForm
from .email_service import ContactDeliveryError, send_contact_notification
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
    """Served at /robots.txt: allows crawling and points to the sitemap."""
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
# portfolio entries). `updated_on` is deliberately catalogue metadata rather
# than visible copy: it gives the Projects page a stable editorial sort order
# without pretending a code deploy is a substantive project update.
EXTERNAL_TOOLS = [
    {
        'title': 'World Ledger',
        'slug': 'world-ledger',
        'url_name': 'world_lens:dashboard',
        'category': Project.Category.DATA,
        'description': 'Rank economic power and future potential, change the strategic weights, and see exactly which national strengths and constraints drive the result.',
        'status_label': 'Live rankings',
        'updated_on': date(2026, 8, 9),
    },
    {
        'title': 'Life Compass',
        'slug': 'life-compass',
        'url_name': 'life_compass:home',
        'category': Project.Category.SPORT,
        'description': 'Turn long-term priorities into a practical weekly operating system, with a privacy-first public demo built entirely from generic data.',
        'status_label': 'Live demo',
        'updated_on': date(2026, 8, 8),
    },
    {
        'title': 'Portfolio Pulse',
        'slug': 'portfolio-pulse',
        'url_name': 'portfolio_pulse:dashboard',
        'category': Project.Category.COMMERCIAL,
        'description': 'Upload a book of business and get an instant health read: portfolio score, NRR/GRR, renewal risk, and silent decliners, with the scoring fully explained.',
        'status_label': 'Live upload',
        'updated_on': date(2026, 8, 7),
    },
]

NEM_SUITE = {
    'title': 'NEM Dashboard',
    'category': Project.Category.ENERGY,
    'description': (
        "One home for Australia's eastern energy market: generation, wholesale prices, "
        'battery dispatch and east-coast gas-system conditions.'
    ),
    'status_label': 'Live markets',
    'url_name': 'nem_dashboard:nem_dashboard',
    'children': [
        {
            'title': 'Price Predictor Lab',
            'description': 'Test week-ahead NEM price forecasts against transparent baselines and the results that subsequently cleared.',
            'status_label': 'Live forecasts',
            'url_name': 'nem_price_lab:lab',
        },
        {
            'title': 'ChargeTrace',
            'description': 'Trace grid-battery dispatch, stored energy and observable energy and FCAS value across weekly and 90-day views.',
            'status_label': 'Live dispatch',
            'url_name': 'nem_battery_explorer:explorer',
        },
        {
            'title': 'FlowTrace',
            'description': 'Follow east-coast gas production, pipelines, storage, demand and emerging system pressure from public AEMO data.',
            'status_label': 'Live flows',
            'url_name': 'gas_monitor:monitor',
        },
    ],
}

PROJECT_PRESENTATION = {
    'stillpoint': {
        'description': 'Set a quiet meditation timer, keep your own silence in Master mode, or follow a simple audio guide in Guide-me mode.',
        'status_label': 'Live timer',
    },
}

NEM_DATABASE_SLUGS = {'nem-fuelmix', 'east-coast-gas-system-stress-monitor'}


def _external_tools():
    """EXTERNAL_TOOLS with URLs resolved, as attribute-access objects so
    templates can treat them the same way as a Project instance."""
    category_labels = dict(Project.Category.choices)
    return [
        SimpleNamespace(
            title=t['title'], slug=t['slug'], category=t['category'],
            category_display=category_labels[t['category']],
            description=t['description'], project_url=reverse(t['url_name']),
            status_label=t['status_label'], updated_on=t['updated_on'],
        )
        for t in EXTERNAL_TOOLS
    ]


def _nem_suite():
    category_labels = dict(Project.Category.choices)
    children = [
        SimpleNamespace(**item, project_url=reverse(item['url_name']))
        for item in NEM_SUITE['children']
    ]
    return SimpleNamespace(
        title=NEM_SUITE['title'],
        category=NEM_SUITE['category'],
        category_display=category_labels[NEM_SUITE['category']],
        description=NEM_SUITE['description'],
        status_label=NEM_SUITE['status_label'],
        project_url=reverse(NEM_SUITE['url_name']),
        children=children,
    )


def _catalogue_project(project):
    presentation = PROJECT_PRESENTATION.get(project.slug, {})
    return SimpleNamespace(
        title=project.title,
        slug=project.slug,
        category=project.category,
        category_display=project.get_category_display(),
        description=presentation.get('description', project.description),
        project_url=project.project_url or reverse('project_detail', kwargs={'slug': project.slug}),
        status_label=presentation.get('status_label', 'Live tool' if project.project_url else 'Project'),
        updated_on=presentation.get(
            'updated_on',
            project.updated_at.date() if project.updated_at else project.date,
        ),
    )


def _homepage_tools():
    # NEM already has its own dedicated hero CTA ("Explore the NEM Dashboard"),
    # so it's excluded here to avoid the homepage pointing at it twice.
    db_tools = list(
        Project.objects.exclude(Q(project_url__isnull=True) | Q(project_url=''))
        .exclude(slug__in=NEM_DATABASE_SLUGS)
        .order_by('slug')
    )
    return db_tools + _external_tools()


def home(request):
    tools = _homepage_tools()
    # Deterministic per-day rotation (not per-visit): stable all day, changes
    # daily, and needs no stored state.
    current_project = tools[timezone.localdate().toordinal() % len(tools)] if tools else None
    featured_post = BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED,
        is_featured=True,
        published__lte=timezone.now(),
    ).order_by('?').first()
    return render(request, 'portfolio/home.html', {'current_project': current_project, 'featured_post': featured_post})

def all_projects(request):
    category = request.GET.get('category', '')
    if category not in dict(Project.Category.choices):
        category = ''

    database_tools = [
        _catalogue_project(project)
        for project in Project.objects.exclude(slug__in=NEM_DATABASE_SLUGS)
        if not category or project.category == category
    ]
    external_tools = [t for t in _external_tools() if not category or t.category == category]
    projects = sorted(database_tools + external_tools, key=lambda item: item.updated_on, reverse=True)
    nem_suite = _nem_suite() if not category or category == Project.Category.ENERGY else None

    return render(request, 'portfolio/projects.html', {
        'projects': projects,
        'categories': Project.Category.choices,
        'active_category': category,
        'nem_suite': nem_suite,
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

    featured_posts = list(published_qs.filter(is_featured=True).order_by('?')[:2])

    # All posts go into the list: the featured posts are highlighted above, not removed
    paginator = Paginator(filtered_qs.order_by('-published'), 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portfolio/blog.html', {
        'featured_posts': featured_posts,
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
    # No visible <figcaption>: every article already follows each image placeholder
    # with its own "Figure N. ..." caption line in the markdown body, so injecting
    # a second caption here duplicated it. Caption text is kept as alt text only.
    from django.utils.html import escape
    content = post.content
    for i, img in enumerate(post.images.all()):
        placeholder = f"[[image{i+1}]]"
        caption = escape(img.caption) if img.caption else ""
        expand_label = f"Expand image: {caption}" if caption else "Expand article image"
        img_tag = (
            f'<figure class="article-figure">'
            f'<button type="button" class="article-image-trigger" '
            f'aria-label="{expand_label}">'
            f'<img src="{img.image.url}" alt="{caption}" loading="lazy">'
            f'</button></figure>'
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
            # Honeypot: a bot filled the hidden field, pretend success, send nothing.
            if form.cleaned_data.get('website'):
                logger.info("Contact honeypot triggered from %s", _client_ip(request))
                return redirect('contact_success')

            # Light per-IP rate limit (invisible unless someone is abusing the form).
            ip = _client_ip(request)
            throttle_key = f"contact-throttle:{ip}"
            attempts = cache.get(throttle_key, 0)
            if attempts >= CONTACT_MAX_PER_WINDOW:
                messages.error(request, "You've sent a few messages already; please try again a little later.")
                return render(request, 'portfolio/contact.html', {'form': form})
            cache.set(throttle_key, attempts + 1, CONTACT_WINDOW_SECONDS)

            contact = Contact.objects.create(
                name=form.cleaned_data['name'],
                email=form.cleaned_data['email'],
                message=form.cleaned_data['message'],
            )

            try:
                delivery_id = send_contact_notification(contact)
                logger.info(
                    "Contact form message %s accepted by Resend as %s",
                    contact.pk,
                    delivery_id,
                )
            except ContactDeliveryError:
                logger.exception(
                    "Contact form message %s was saved but its notification failed",
                    contact.pk,
                )
                messages.error(
                    request,
                    "Sorry, something went wrong sending your message. "
                    "Please email me directly at hello@accidentalscientist.net.",
                )
                return render(request, 'portfolio/contact.html', {'form': form})

            return redirect('contact_success')
    else:
        form = ContactForm()

    return render(request, 'portfolio/contact.html', {'form': form})


def contact_success(request):
    return render(request, 'portfolio/contact_success.html')
