from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class AdministratorAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff or not user.is_superuser:
            raise ValidationError("Administrator access is required.", code="invalid_login")


class BrokerSettingsForm(forms.Form):
    api_key = forms.RegexField(r"^[A-Za-z0-9]{8,128}$", required=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Leave blank to keep the saved API key.")
    api_secret = forms.CharField(required=False, min_length=8, max_length=512, strip=False,
        widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password"}),
        help_text="Never displayed after saving. Leave blank to keep the saved secret.")
    redirect_url = forms.URLField(initial="http://127.0.0.1:8001/kite/callback")
    enabled = forms.BooleanField(required=False, label="Enable read-only broker access")
    revision = forms.UUIDField(required=False, widget=forms.HiddenInput)

    def clean_redirect_url(self):
        value = self.cleaned_data["redirect_url"]
        if value != settings.BROKER_CALLBACK_URL:
            raise ValidationError("Use exactly " + settings.BROKER_CALLBACK_URL)
        return value

    def clean_api_secret(self):
        value = self.cleaned_data["api_secret"]
        if value and (value != value.strip() or not value.isascii() or not value.isprintable()):
            raise ValidationError("Enter the secret exactly, without whitespace or control characters.")
        return value
