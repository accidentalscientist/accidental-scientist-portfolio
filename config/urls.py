"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import RedirectView

from portfolio.sitemaps import StaticViewSitemap, BlogSitemap
from portfolio.views import robots_txt

sitemaps = {
    'static': StaticViewSitemap,
    'blog': BlogSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('markdownx/', include('markdownx.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps},
         name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt),
    path('', include('portfolio.urls')),
    # The more specific route comes first. nem_dashboard only defines '', so
    # today this would resolve either way, but ordering it explicitly means a
    # future catch-all in nem_dashboard cannot silently shadow the lab.
    path('nem/price-lab/', include('nem_price_lab.urls', namespace='nem_price_lab')),
    path('nem/', include('nem_dashboard.urls', namespace='nem_dashboard')),
    path('stillpoint/', include('stillpoint.urls', namespace='stillpoint')),
    path('pulse/', include('portfolio_pulse.urls', namespace='portfolio_pulse')),
    path('life-compass/', include('life_compass.urls', namespace='life_compass')),
    path('world-ledger/', include('world_lens.urls', namespace='world_lens')),
    path('world-lens/', RedirectView.as_view(pattern_name='world_lens:dashboard', permanent=True)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
