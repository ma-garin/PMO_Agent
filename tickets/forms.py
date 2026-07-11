from django import forms

from .models import TicketSource


class TicketSourceForm(forms.ModelForm):
    api_token = forms.CharField(
        label="APIトークン",
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
        help_text="入力した場合のみ更新されます。空欄のままなら既存の値を維持します。",
    )

    class Meta:
        model = TicketSource
        fields = [
            "kind",
            "name",
            "base_url",
            "project_key",
            "username",
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
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_token = self.cleaned_data.get("api_token", "")
        if new_token:
            instance.api_token = new_token
        if commit:
            instance.save()
        return instance
