from django.contrib import admin

from .models import AgentProposal, AgentRun, AgentSettings


@admin.register(AgentSettings)
class AgentSettingsAdmin(admin.ModelAdmin):
    list_display = ("engagement", "enabled", "max_llm_calls_per_day")


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("engagement", "trigger", "status", "findings_count", "proposals_count", "started_at")
    list_filter = ("trigger", "status")


@admin.register(AgentProposal)
class AgentProposalAdmin(admin.ModelAdmin):
    list_display = ("engagement", "kind", "status", "title", "created_at")
    list_filter = ("kind", "status")
