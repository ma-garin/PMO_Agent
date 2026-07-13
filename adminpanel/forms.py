from django import forms

from engagements.models import Engagement


class AdminEngagementForm(forms.ModelForm):
    class Meta:
        model = Engagement
        fields = [
            "name",
            "description",
            "status",
            "progress",
            "owner",
            "members",
            "monthly_token_limit",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "description": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "progress": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "members": forms.SelectMultiple(attrs={"class": "form-select", "size": 6}),
            "monthly_token_limit": forms.NumberInput(attrs={"class": "form-input", "min": 0, "step": 1000}),
        }

    def clean_progress(self):
        value = self.cleaned_data["progress"]
        if value < 0 or value > 100:
            raise forms.ValidationError("進捗は0〜100の範囲で入力してください。")
        return value
