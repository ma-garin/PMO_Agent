from django import forms
from django.contrib.auth.models import User


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(
        label="初期パスワード",
        # autocomplete=new-password: ブラウザが管理者自身の既存パスワードを
        # 新規ユーザー作成フォームへ自動挿入するのを防ぐ。
        widget=forms.PasswordInput(attrs={"class": "form-input", "autocomplete": "new-password"}),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password", "is_staff"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-input", "autocomplete": "off"}),
            "email": forms.EmailInput(attrs={"class": "form-input", "autocomplete": "off"}),
            "is_staff": forms.CheckboxInput(),
        }

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user
