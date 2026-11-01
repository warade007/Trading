import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from .crypto import encrypt, decrypt, require_envelope


class BrokerConnection(models.Model):
    broker = models.CharField(max_length=16, default="ZERODHA", unique=True, editable=False)
    api_key = models.CharField(max_length=128, blank=True)
    encrypted_api_secret = models.TextField(blank=True, editable=False)
    redirect_url = models.URLField(default="http://127.0.0.1:8001/kite/callback")
    enabled = models.BooleanField(default=False)
    status = models.CharField(max_length=24, default="NOT_CONFIGURED")
    error_code = models.CharField(max_length=32, blank=True)
    revision = models.UUIDField(default=uuid.uuid4, editable=False)
    last_successful_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(broker="ZERODHA"), name="only_zerodha_broker")]

    def __str__(self):
        return "Zerodha research connection"

    @property
    def masked_api_key(self):
        return "••••" + self.api_key[-4:] if len(self.api_key) > 4 else ("••••" if self.api_key else "Not set")

    def set_secret(self, secret):
        self.encrypted_api_secret = encrypt(secret, "api_secret")

    def get_secret(self):
        return decrypt(self.encrypted_api_secret, "api_secret")

    def save(self, *args, **kwargs):
        require_envelope(self.encrypted_api_secret)
        return super().save(*args, **kwargs)


class BrokerSession(models.Model):
    connection = models.ForeignKey(BrokerConnection, on_delete=models.CASCADE, related_name="broker_sessions")
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    encrypted_access_token = models.TextField(blank=True, editable=False)
    status = models.CharField(max_length=24, default="PENDING")
    login_time = models.DateTimeField(null=True)
    expected_expiration = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    state_digest = models.CharField(max_length=64, blank=True, editable=False)
    browser_session_digest = models.CharField(max_length=64, blank=True, editable=False)
    connection_revision = models.UUIDField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["connection"], condition=Q(status="ACTIVE"), name="one_active_broker_session")]

    def __str__(self):
        return f"Broker session {self.pk}: {self.status}"

    def set_token(self, token):
        self.encrypted_access_token = encrypt(token, "access_token")

    def get_token(self):
        return decrypt(self.encrypted_access_token, "access_token")

    def save(self, *args, **kwargs):
        require_envelope(self.encrypted_access_token)
        return super().save(*args, **kwargs)


class BrokerAuditLog(models.Model):
    # Intentionally no free-text, request payload, account identity or token fields.
    connection = models.ForeignKey(BrokerConnection, null=True, on_delete=models.SET_NULL)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    event = models.CharField(max_length=32)
    outcome = models.CharField(max_length=16)
    error_code = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
