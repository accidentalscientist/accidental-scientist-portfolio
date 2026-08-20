import json

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .models import GuidedMeditation, StillpointSession

MAX_SESSIONS_RETURNED = 500


def timer(request):
    guided_sessions = GuidedMeditation.objects.all()
    return render(request, 'stillpoint/timer.html', {
        'guided_sessions': guided_sessions,
    })


@csrf_protect
@require_http_methods(["GET", "POST"])
def sessions(request):
    """Server-side session log for signed-in users only — anonymous
    visitors keep the existing localStorage-only demo behaviour, so this
    view is a no-op (not a 403) for them rather than requiring login.
    """
    if not request.user.is_authenticated:
        if request.method == "POST":
            return JsonResponse({"status": "skipped"})
        return JsonResponse({"sessions": []})

    if request.method == "POST":
        try:
            payload = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid JSON."}, status=400)

        completed_at = parse_datetime(payload.get("completedAt") or "")
        duration_seconds = payload.get("durationSeconds")
        mode = payload.get("mode")
        if not completed_at or not isinstance(duration_seconds, (int, float)) or mode not in ('master', 'student'):
            return JsonResponse({"error": "Invalid session payload."}, status=400)

        guided_session = None
        guided_session_id = payload.get("guidedSessionId")
        if guided_session_id:
            guided_session = GuidedMeditation.objects.filter(pk=guided_session_id).first()

        StillpointSession.objects.create(
            user=request.user,
            completed_at=completed_at,
            duration_seconds=max(0, int(duration_seconds)),
            mode=mode,
            guided_session=guided_session,
        )
        return JsonResponse({"status": "ok"})

    queryset = StillpointSession.objects.filter(user=request.user)[:MAX_SESSIONS_RETURNED]
    return JsonResponse({
        "sessions": [
            {
                "completedAt": session.completed_at.isoformat(),
                "durationSeconds": session.duration_seconds,
                "mode": session.mode,
                "guidedSessionTitle": session.guided_session.title if session.guided_session_id else None,
            }
            for session in queryset
        ],
    })
