from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

from .models import BlogPost


class StaticViewSitemap(Sitemap):
    priority = 0.6
    changefreq = "monthly"

    def items(self):
        return [
            'home',
            'blog',
            'projects',
            'about',
            'nem_dashboard:nem_dashboard',
            'stillpoint:timer',
        ]

    def location(self, item):
        return reverse(item)


class BlogSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return (
            BlogPost.objects
            .filter(status=BlogPost.Status.PUBLISHED, published__lte=timezone.now())
            .order_by('-published')
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('blog_detail', kwargs={'slug': obj.slug})
