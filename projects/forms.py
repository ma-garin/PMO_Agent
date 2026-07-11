from django import forms

from .models import Project


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "status"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "例: 基幹システム刷新"}
            ),
            "description": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "プロジェクトの概要を入力"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
        }
