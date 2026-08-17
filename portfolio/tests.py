import json
import os
import tempfile
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .email_service import ContactDeliveryError, send_contact_notification
from .models import BlogPost, Contact, Project


@override_settings(ALLOWED_HOSTS=['testserver'])
class PageSmokeTests(TestCase):
    def test_home_ok(self):
        self.assertEqual(self.client.get(reverse('home')).status_code, 200)

    def test_projects_ok(self):
        response = self.client.get(reverse('projects'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NEM Dashboard')
        self.assertContains(response, 'ChargeTrace')
        self.assertContains(response, 'FlowTrace')
        self.assertNotContains(response, 'Live tool')

    def test_nem_suite_is_first_and_database_duplicates_are_hidden(self):
        Project.objects.create(
            title='NEM Fuel Generation Dashboard', slug='nem-fuelmix',
            description='old', project_url='/nem/',
        )
        Project.objects.create(
            title='FlowTrace', slug='east-coast-gas-system-stress-monitor',
            description='old', project_url='/gas/',
        )
        response = self.client.get(reverse('projects'))
        body = response.content.decode()
        self.assertEqual(body.count('>NEM Dashboard<'), 1)
        self.assertEqual(body.count('>FlowTrace<'), 1)
        self.assertLess(body.index('>NEM Dashboard<'), body.index('>World Ledger<'))

    def test_old_energy_urls_redirect_to_nem_suite(self):
        self.assertRedirects(
            self.client.get('/charge-trace/'), '/nem/charge-trace/',
            status_code=301, fetch_redirect_response=False,
        )
        self.assertRedirects(
            self.client.get('/gas/'), '/nem/flow-trace/',
            status_code=301, fetch_redirect_response=False,
        )

    def test_life_compass_ok(self):
        self.assertEqual(self.client.get(reverse('life_compass:home')).status_code, 200)
        self.assertEqual(self.client.get(reverse('life_compass:strategy')).status_code, 200)
        self.assertEqual(self.client.get(reverse('life_compass:execution')).status_code, 200)

    def test_portfolio_pulse_ok(self):
        self.assertEqual(self.client.get(reverse('portfolio_pulse:dashboard')).status_code, 200)

    def test_blog_list_ok(self):
        self.assertEqual(self.client.get(reverse('blog')).status_code, 200)

    def test_about_ok(self):
        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-contact-form')
        self.assertContains(response, 'aria-keyshortcuts="Control+Shift+Enter"')
        self.assertContains(response, 'Ctrl + Shift + Enter')
        self.assertContains(response, 'form.checkValidity()')
        self.assertContains(response, 'form.requestSubmit(submitButton)')

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
    RESEND_API_KEY='re_test_key',
    DEFAULT_FROM_EMAIL='from@example.com',
    CONTACT_EMAIL='to@example.com',
)
class ContactFormTests(TestCase):
    def setUp(self):
        cache.clear()

    def _post(self, **extra):
        data = {'name': 'Ada', 'email': 'ada@example.com', 'message': 'Hello there', 'website': ''}
        data.update(extra)
        return self.client.post(reverse('about'), data)

    @patch('portfolio.views.send_contact_notification', return_value='email_test_id')
    def test_valid_submission_saves_message_and_sends_notification(self, send_notification):
        resp = self._post()
        self.assertRedirects(resp, reverse('contact_success'))
        contact = Contact.objects.get()
        self.assertEqual(contact.email, 'ada@example.com')
        send_notification.assert_called_once_with(contact)

    @patch('portfolio.views.send_contact_notification')
    def test_honeypot_drops_silently(self, send_notification):
        resp = self._post(website='http://spam.example')
        self.assertRedirects(resp, reverse('contact_success'))
        self.assertEqual(Contact.objects.count(), 0)
        send_notification.assert_not_called()

    @patch('portfolio.views.send_contact_notification')
    def test_invalid_submission_no_500(self, send_notification):
        resp = self.client.post(reverse('about'), {'name': '', 'email': 'bad', 'message': ''})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Contact.objects.count(), 0)
        send_notification.assert_not_called()

    @patch(
        'portfolio.views.send_contact_notification',
        side_effect=ContactDeliveryError('provider unavailable'),
    )
    def test_delivery_failure_is_visible_but_message_remains_saved(self, send_notification):
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'something went wrong sending your message')
        self.assertContains(resp, 'alert-danger')
        self.assertEqual(Contact.objects.count(), 1)
        send_notification.assert_called_once()

    def test_success_page_is_a_stable_destination(self):
        resp = self.client.get(reverse('contact_success'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Your message made it through the portal.')
        self.assertContains(resp, 'There is no need to send a duplicate across the multiverse.')
        self.assertContains(resp, 'Explore Infinite Energies')
        self.assertContains(resp, reverse('nem_dashboard:nem_dashboard'))
        self.assertContains(resp, 'Return to Dimension C-137')
        self.assertContains(resp, reverse('about'))
        self.assertNotContains(resp, 'Explore the multiverse')


@override_settings(
    RESEND_API_KEY='re_test_key',
    RESEND_API_URL='https://api.resend.test/emails',
    RESEND_TIMEOUT_SECONDS=7,
    DEFAULT_FROM_EMAIL='hello@example.com',
    CONTACT_EMAIL='hello@example.com',
)
class ResendContactDeliveryTests(SimpleTestCase):
    @patch('portfolio.email_service.urlopen')
    def test_payload_uses_branded_sender_and_visitor_reply_to(self, open_url):
        response = open_url.return_value.__enter__.return_value
        response.read.return_value = b'{"id":"email_123"}'
        contact = SimpleNamespace(
            pk=42,
            name='Ada',
            email='ada@example.com',
            message='Hello there',
        )

        message_id = send_contact_notification(contact)

        self.assertEqual(message_id, 'email_123')
        request = open_url.call_args.args[0]
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(payload['from'], 'Accidental Scientist Website <hello@example.com>')
        self.assertEqual(payload['to'], ['hello@example.com'])
        self.assertEqual(payload['reply_to'], 'ada@example.com')
        self.assertEqual(open_url.call_args.kwargs['timeout'], 7)
        self.assertEqual(request.get_header('Idempotency-key'), 'contact-form-42')

    @override_settings(RESEND_API_KEY='')
    def test_missing_api_key_fails_before_network_request(self):
        contact = SimpleNamespace(pk=42, name='Ada', email='ada@example.com', message='Hello')

        with self.assertRaisesMessage(ContactDeliveryError, 'RESEND_API_KEY is not configured'):
            send_contact_notification(contact)


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
