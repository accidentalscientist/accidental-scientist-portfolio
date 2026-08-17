import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class ContactDeliveryError(RuntimeError):
    """Raised when a saved contact message cannot be sent to Resend."""


def send_contact_notification(contact):
    """Send a saved Contact through Resend and return its provider message ID."""
    if not settings.RESEND_API_KEY:
        raise ContactDeliveryError("RESEND_API_KEY is not configured.")
    if not settings.DEFAULT_FROM_EMAIL:
        raise ContactDeliveryError("DEFAULT_FROM_EMAIL is not configured.")
    if not settings.CONTACT_EMAIL:
        raise ContactDeliveryError("CONTACT_EMAIL is not configured.")

    payload = {
        'from': f'Accidental Scientist Website <{settings.DEFAULT_FROM_EMAIL}>',
        'to': [settings.CONTACT_EMAIL],
        'reply_to': contact.email,
        'subject': f'[Website contact] Message from {contact.name}',
        'text': (
            f'Name: {contact.name}\n'
            f'Email: {contact.email}\n\n'
            f'Message:\n{contact.message}'
        ),
    }
    request = Request(
        settings.RESEND_API_URL,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {settings.RESEND_API_KEY}',
            'Content-Type': 'application/json',
            'Idempotency-Key': f'contact-form-{contact.pk}',
            'User-Agent': 'accidentalscientist-contact/1.0',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=settings.RESEND_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode('utf-8'))
    except HTTPError as exc:
        detail = ''
        try:
            error_result = json.loads(exc.read().decode('utf-8'))
            provider_message = error_result.get('message')
            if isinstance(provider_message, str):
                detail = f': {provider_message}'
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        raise ContactDeliveryError(
            f'Resend rejected the message with HTTP {exc.code}{detail}.'
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise ContactDeliveryError('Resend could not be reached.') from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContactDeliveryError('Resend returned an invalid response.') from exc

    message_id = result.get('id')
    if not message_id:
        raise ContactDeliveryError('Resend did not return a message ID.')
    return message_id
