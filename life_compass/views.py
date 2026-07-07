from django.shortcuts import render


def home(request):
    return render(request, "life_compass/index.html")


def strategy(request):
    return render(request, "life_compass/strategy.html")


def execution(request):
    return render(request, "life_compass/execution.html")