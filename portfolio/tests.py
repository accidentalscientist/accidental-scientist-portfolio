import json
import os
import tempfile
from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import BlogPost


@override_settings(ALLOWED_HOSTS=['testserver'])
class PageSmokeTests(TestCase):
    def test_home_ok(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_projects_ok(self):
        self.assertEqual(self.client.get(reverse('projects')).status_code, 200)

    def test_life_compass_ok(self):
        self.assertEqual(self.client.get(reverse('life_compass:home')).status_code, 200)
        self.assertEqual(self.client.get(reverse('life_compass:strategy')).status_code, 200)
        self.assertEqual(self.client.get(reverse('life_compass:execution')).status_code, 200)

    def test_portfolio_pulse_ok(self):
        self.assertEqual(self.client.get(reverse('portfolio_pulse:dashboard')).status_code, 200)

    def test_blog_list_ok(self):
        self.assertEqual(self.client.get(reverse('blog')).status_code, 200)

    def test_about_ok(self):
        self.assertEqual(self.client.get(reverse('about')).status_code, 200)

    def test_contact_redirects_to_about(self):
        self.assertEqual(self.client.get(reverse('contact')).status_code, 301)

    def test_sitemap_and_robots(self):
        self.assertEqual(self.client.get('/sitemap.xml').status_code, 200)
        self.assertEqual(self.client.get('/robots.txt').status_code, 200)


@override_settings(ALLOWED_HOSTS=['testserver'])
class BlogVisibilityTests(TestCase):
    def setUp(self):
        BlogPost.objects.create(
            title="Published", slug="published", summary="s", content="body",
            status=BlogPost.Status.PUBLISHED, published=timezone.now() - timedelta(days=1),
        )
        BlogPost.objects.create(
            title="Draft", slug="draft", summary="s", content="body",
            status=BlogPost.Status.DRAFT, published=timezone.now() - timedelta(days=1),
        )
        BlogPost.objects.create(
            title="Future", slug="future", summary="s", content="body",
            status=BlogPost.Status.PUBLISHED, published=timezone.now() + timedelta(days=5),
        )

    def test_published_detail_ok(self):
        resp = self.client.get(reverse('blog_detail', kwargs={'slug': 'published'}))
        self.assertEqual(resp.status_code, 200)

    def test_draft_hidden(self):
        resp = self.client.get(reverse('blog_detail', kwargs={'slug': 'draft'}))
        self.assertEqual(resp.status_code, 404)

    def test_future_hidden(self):
        resp = self.client.get(reverse('blog_detail', kwargs={'slug': 'future'}))
        self.assertEqual(resp.status_code, 404)


@override_settings(
    ALLOWED_HOSTS=['testserver'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='from@example.com',
    CONTACT_EMAIL='to@example.com',
)
class ContactFormTests(TestCase):
    def _post(self, **extra):
        data = {'name': 'Ada', 'email': 'ada@example.com', 'message': 'Hello there', 'website': ''}
        data.update(extra)
        return self.client.post(reverse('about'), data)

    def test_valid_submission_sends_email(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ['ada@example.com'])

    def test_honeypot_drops_silently(self):
        resp = self._post(website='http://spam.example')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_submission_no_500(self):
        resp = self.client.post(reverse('about'), {'name': '', 'email': 'bad', 'message': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)


class ImportIdempotencyTests(TestCase):
    def test_reimport_updates_by_slug_no_duplicate(self):
        tmp = tempfile.mkdtemp()
        pkg = os.path.join(tmp, 'articles', '01_demo')
        os.makedirs(pkg)
        with open(os.path.join(pkg, 'article.md'), 'w', encoding='utf-8') as f:
            f.write("# Demo\n\nBody.")
        with open(os.path.join(pkg, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump({
                'title': 'Demo article', 'slug': 'demo-article', 'category': 'energy',
                'summary': 'A demo.', 'key_takeaway': 'Idempotent.',
            }, f)

        with override_settings(ELITE_ARTICLES_DIR=tmp):
            call_command('import_elite_articles', '--publish')
            call_command('import_elite_articles', '--publish')

        self.assertEqual(BlogPost.objects.filter(slug='demo-article').count(), 1)
