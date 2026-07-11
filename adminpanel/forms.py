from django import forms
from django.contrib.auth.models import User


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="初期パスワード",
        widget=forms.PasswordInput(attrs={"class": "form-input"}),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "is_staff"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-input"}),
            "email": forms.EmailInput(attrs={"class": "form-input"}),
            "is_staff": forms.CheckboxInput(),
        }

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
