from django.utils.timezone import now

def inject_now(request):
    return {'now': now()}
# This context processor injects the current date and time into the context of all templates.

def global_site_info(request):
    return {
        'now': now(),
        'site_name': "Accidental Scientist",
        'site_tagline': "Exploring Data, Energy, and Football",
        'contact_email': "contact@accidentalscientist.net",
        'github_url': "https://github.com/accidentalscientist",
    }