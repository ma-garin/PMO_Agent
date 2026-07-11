from django import forms

from .models import Engagement


class EngagementForm(forms.ModelForm):
    class Meta:
        model = Engagement
        fields = ["name", "description", "status"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "例: 基幹システム刷新"}
            ),
            "description": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "案件の概要を入力"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
        }


class EngagementLlmSettingsForm(forms.ModelForm):
    class Meta:
        model = Engagement
        fields = ["llm_provider"]
        widgets = {
            "llm_provider": forms.Select(attrs={"class": "form-select"}),
        }
