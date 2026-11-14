from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.functions import Lower
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import CategoryForm, CategoryListForm, DeviceForm, DeviceListForm
from .models import Category, Device


@login_required
def index(request):
    return render(request, "index.html")


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = UserCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("login")
    return render(request, "register.html", {"form": form})


@login_required
@require_http_methods(["GET"])
def category_list(request):
    form_data = request.GET.copy()
    form_data["per_page"] = form_data.get("per_page") or "25"
    form = CategoryListForm(form_data)
    categories = Category.objects.order_by(Lower("name"), "pk").prefetch_related(
        "allowed_sub_components"
    )
    if form.is_valid():
        filters = form.cleaned_data
        if filters["q"]:
            categories = categories.filter(name__icontains=filters["q"])
        if filters["components"]:
            categories = categories.filter(
                allowed_sub_components__isnull=filters["components"] == "no"
            ).distinct()
        if filters["sort"] == "-name":
            categories = categories.order_by(Lower("name").desc(), "pk")
    else:
        categories = categories.none()
    page = Paginator(categories, form.cleaned_data.get("per_page", 25)).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "categories/list.html",
        {
            "categories": page,
            "page_obj": page,
            "filter_form": form,
            "filters_active": bool(
                request.GET.get("q") or request.GET.get("components")
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def category_create(request):
    form = CategoryForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        category = form.save()
        messages.success(request, f"Dodano kategorię „{category.name}”.")
        return redirect("category_list")
    return render(
        request, "categories/form.html", {"form": form, "title": "Dodaj kategorię"}
    )


@login_required
@require_http_methods(["GET", "POST"])
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk)
    form = CategoryForm(
        request.POST if request.method == "POST" else None, instance=category
    )
    if request.method == "POST" and form.is_valid():
        category = form.save()
        messages.success(request, f"Zapisano kategorię „{category.name}”.")
        return redirect("category_list")
    return render(
        request, "categories/form.html", {"form": form, "title": "Edytuj kategorię"}
    )


@login_required
@require_http_methods(["GET", "POST"])
def category_delete(request, pk):
    with transaction.atomic():
        categories = Category.objects.all()
        if request.method == "POST":
            categories = categories.select_for_update()
        category = get_object_or_404(categories, pk=pk)
        in_use = category.device_set.exists() or category.parametermodel_set.exists()
        if request.method == "POST" and not in_use:
            name = category.name
            category.delete()
            messages.success(request, f"Usunięto kategorię „{name}”.")
            return redirect("category_list")
        return render(
            request,
            "categories/confirm_delete.html",
            {
                "category": category,
                "in_use": in_use,
                "parent_categories": Category.objects.filter(
                    allowed_sub_components=category
                ).order_by("name", "pk"),
            },
            status=409 if request.method == "POST" else 200,
        )


@login_required
@require_http_methods(["GET"])
def device_list(request):
    form_data = request.GET.copy()
    form_data["per_page"] = form_data.get("per_page") or "25"
    form = DeviceListForm(form_data)
    devices = (
        Device.objects.select_related("category")
        .prefetch_related("components")
        .order_by(Lower("name"), "pk")
    )
    if form.is_valid():
        filters = form.cleaned_data
        if filters["q"]:
            devices = devices.filter(name__icontains=filters["q"])
        if filters["category"]:
            devices = devices.filter(category=filters["category"])
        if filters["components"]:
            devices = devices.filter(
                components__isnull=filters["components"] == "no"
            ).distinct()
        ordering = {
            "name": [Lower("name"), "pk"],
            "-name": [Lower("name").desc(), "pk"],
            "category": [Lower("category__name"), Lower("name"), "pk"],
            "-category": [Lower("category__name").desc(), Lower("name"), "pk"],
        }
        devices = devices.order_by(*ordering[filters["sort"] or "name"])
    else:
        devices = devices.none()
    page = Paginator(devices, form.cleaned_data.get("per_page", 25)).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "devices/list.html",
        {
            "devices": page,
            "page_obj": page,
            "filter_form": form,
            "filters_active": any(
                request.GET.get(key) for key in ("q", "category", "components")
            ),
        },
    )


@login_required
@require_http_methods(["GET"])
def device_detail(request, pk):
    device = get_object_or_404(Device.objects.select_related("category"), pk=pk)
    return render(
        request,
        "devices/detail.html",
        {
            "device": device,
            "components": device.components.select_related("category").order_by(
                "name", "pk"
            ),
            "parent_devices": Device.objects.filter(components=device).order_by(
                "name", "pk"
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_create(request):
    form = DeviceForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            device = form.save()
        messages.success(request, f"Dodano urządzenie „{device.name}”.")
        return redirect("device_detail", pk=device.pk)
    return render(
        request, "devices/form.html", {"form": form, "title": "Dodaj urządzenie"}
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_update(request, pk):
    device = get_object_or_404(Device, pk=pk)
    form = DeviceForm(
        request.POST if request.method == "POST" else None, instance=device
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            device = form.save()
        messages.success(request, f"Zapisano urządzenie „{device.name}”.")
        return redirect("device_detail", pk=device.pk)
    return render(
        request, "devices/form.html", {"form": form, "title": "Edytuj urządzenie"}
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_delete(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if request.method == "POST":
        name = device.name
        device.delete()
        messages.success(request, f"Usunięto urządzenie „{name}”.")
        return redirect("device_list")
    return render(
        request,
        "devices/confirm_delete.html",
        {
            "device": device,
            "parent_devices": Device.objects.filter(components=device).order_by(
                "name", "pk"
            ),
            "related_records": {
                "Przydziały": device.devicelease_set.count(),
                "Naprawy": device.devicerepair_set.count(),
                "Parametry": device.parametermodel_set.count(),
                "Lokalizacje": device.devicelocation_set.count(),
            },
        },
    )
