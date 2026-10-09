"""Authenticated task management; templates escape all user content."""
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .forms import ImportTasksForm, TaskForm
from .models import Task

logger = logging.getLogger(__name__)
LIST_TEMPLATE = "tasks/list.html"


@login_required
@require_http_methods(["GET", "POST"])
def index(request):
    form = TaskForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        task = form.save(commit=False)
        task.owner = request.user
        task.save()
        logger.info("Task %s created by user %s", task.pk, request.user.pk)
        return redirect("list")
    return render(request, LIST_TEMPLATE, {
        "tasks": Task.objects.filter(owner=request.user), "form": form,
        "welcome_message": "Bienvenue sur votre TO DO LIST !",
    })


@login_required
@require_http_methods(["GET", "POST"])
def update_task(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    form = TaskForm(request.POST or None, instance=task)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("list")
    return render(request, "tasks/update_task.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def delete_task(request, pk):
    task = get_object_or_404(Task, pk=pk, owner=request.user)
    if request.method == "POST":
        task.delete()
        return redirect("list")
    return render(request, "tasks/delete.html", {"item": task})


@login_required
@require_GET
def search_tasks(request):
    tasks = Task.objects.filter(owner=request.user, title__icontains=request.GET.get("q", ""))
    return render(request, "tasks/search.html", {"tasks": tasks})


@login_required
@require_http_methods(["GET", "POST"])
def import_tasks(request):
    form = ImportTasksForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        Task.objects.bulk_create([
            Task(title=title, owner=request.user)
            for title in form.cleaned_data["tasks_data"]
        ])
        return redirect("list")
    return render(request, "tasks/import.html", {"form": form})


@login_required
@require_GET
def admin_panel(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Accès réservé au personnel autorisé.")
    return HttpResponse("Bienvenue admin !")


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})
