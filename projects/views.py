from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from .forms import ProjectForm
from .models import Project


class ProjectSelectView(LoginRequiredMixin, ListView):
    model = Project
    template_name = "projects/select.html"
    context_object_name = "projects"

    def get_queryset(self):
        user = self.request.user
        return (
            Project.objects.filter(Q(owner=user) | Q(members=user))
            .distinct()
            .prefetch_related("members")
        )


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = "projects/project_form.html"
    success_url = reverse_lazy("projects:select")

    def form_valid(self, form):
        form.instance.owner = self.request.user
        response = super().form_valid(form)
        self.object.members.add(self.request.user)
        return response


@login_required
def select_project(request, pk):
    project = get_object_or_404(
        Project.objects.filter(Q(owner=request.user) | Q(members=request.user)),
        pk=pk,
    )
    request.session["current_project_id"] = project.pk
    request.session["current_project_name"] = project.name
    return redirect("dashboard:home")
