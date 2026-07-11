from django.contrib import admin

from .models import MemberAlias


@admin.register(MemberAlias)
class MemberAliasAdmin(admin.ModelAdmin):
    list_display = ("external_name", "user", "engagement")
