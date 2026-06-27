from django.conf import settings
from django.utils.timezone import now

# Single source of truth for the site version (shown only in local/dev).
SITE_VERSION = "2.7.3"


def inject_now(request):
    return {'now': now()}
# This context processor injects the current date and time into the context of all templates.

def global_site_info(request):
    return {
        'now': now(),
        'site_name': "Accidental Scientist",
        'site_tagline': "Energy transition · Data · Human performance · Society",
        'contact_email': "contact@accidentalscientist.net",
        'github_url': "https://github.com/accidentalscientist",
        'debug_mode': settings.DEBUG,
        'site_version': SITE_VERSION,
    }