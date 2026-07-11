from django import forms

from .models import TicketSource


class TicketSourceForm(forms.ModelForm):
    class Meta:
        model = TicketSource
        fields = [
            "kind",
            "name",
            "base_url",
            "project_key",
            "username",
            "api_token",
            "is_active",
        ]
        widgets = {
            "kind": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "例: 顧客JIRA"}
            ),
            "base_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://your-domain.atlassian.net",
                }
            ),
            "project_key": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "例: PROJ"}
            ),
            "username": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "APIユーザー名またはメール"}
            ),
            "api_token": forms.PasswordInput(attrs={"class": "form-input"}),
        }
