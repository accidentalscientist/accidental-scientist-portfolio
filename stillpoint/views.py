from django.shortcuts import render

from .models import GuidedMeditation


def timer(request):
    guided_sessions = GuidedMeditation.objects.all()
    return render(request, 'stillpoint/timer.html', {
        'guided_sessions': guided_sessions,
    })
