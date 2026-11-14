
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib.auth.forms import UserCreationForm

# Create your views here.
def index(req):
    # TODO: landing page - wystarczy template i tytuł projektu + liki
    return HttpResponse("Hello world")


def register(request):
    if request.method == "GET":
        form = UserCreationForm()
        return render(request, "register.html", {"form":form})
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("/")
        return render(request, "register.html", {"form":form})

