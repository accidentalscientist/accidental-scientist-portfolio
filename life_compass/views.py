import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import LifeCompassData

# Generous but bounded — a real strategy+execution export is a few KB; this
# just stops an abusive or corrupt payload from growing the row unbounded.
MAX_PAYLOAD_BYTES = 512_000


def home(request):
    return render(request, "life_compass/index.html")


def strategy(request):
    return render(request, "life_compass/strategy.html")


def execution(request):
    return render(request, "life_compass/execution.html")


@login_required(login_url='life_compass:login')
@csrf_protect
@require_http_methods(["GET", "POST"])
def sync_data(request):
    """The frontend's entire lifeCompass.* localStorage export, as one blob,
    scoped to the logged-in user only — never visible to anonymous visitors
    or to any other account.
    """
    obj, _ = LifeCompassData.objects.get_or_create(user=request.user)

    if request.method == "POST":
        if len(request.body) > MAX_PAYLOAD_BYTES:
            return JsonResponse({"error": "Payload too large."}, status=413)
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON."}, status=400)
        data = payload.get("data")
        if not isinstance(data, dict):
            return JsonResponse({"error": "Expected a 'data' object."}, status=400)
        obj.data = data
        obj.save(update_fields=["data", "updated_at"])
        return JsonResponse({"status": "ok"})

    return JsonResponse({"data": obj.data})
