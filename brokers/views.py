import functools

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_POST

from .crypto import keyring
from .errors import BrokerError, MESSAGES
from .forms import AdministratorAuthenticationForm, BrokerSettingsForm
from .models import BrokerConnection, BrokerAuditLog
from .services import (BrokerReadOnlyClient, audit, complete_login, disconnect,
                       expire_sessions, record_error, save_configuration, start_login)


def administrator(view):
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("administrator_login")  # Never copy callback query into next=.
        if not request.user.is_active or not request.user.is_staff or not request.user.is_superuser:
            return HttpResponseForbidden("Administrator access is required.")
        return view(request, *args, **kwargs)
    return wrapped


class AdministratorLoginView(LoginView):
    template_name = "brokers/login.html"
    authentication_form = AdministratorAuthenticationForm
    redirect_authenticated_user = False

    def get_success_url(self):
        return reverse("broker_settings")

    def post(self, request, *args, **kwargs):
        # Bounded local password guessing. No usernames/passwords stored in counters.
        if cache.get("administrator_login_failures", 0) >= 10:
            return HttpResponse("Too many attempts. Wait five minutes before trying again.", status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        cache.add("administrator_login_failures", 0, 300)
        cache.incr("administrator_login_failures")
        audit(None, None, "ADMIN_LOGIN_FAILED", "FAILURE")
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete("administrator_login_failures")
        return super().form_valid(form)


@require_POST
def administrator_logout(request):
    logout(request)
    return redirect("administrator_login")


@administrator
@sensitive_post_parameters()
@sensitive_variables()
def broker_settings(request):
    connection = BrokerConnection.objects.filter(broker="ZERODHA").first()
    if connection:
        expire_sessions(connection)
    initial = {"redirect_url": connection.redirect_url, "enabled": connection.enabled, "revision": connection.revision} if connection else {}
    form = BrokerSettingsForm(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            save_configuration(request.user, form.cleaned_data)
        except BrokerError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Broker settings saved. Secrets remain hidden.")
            return redirect("broker_settings")
    key_error = ""
    try:
        keyring()
    except BrokerError as exc:
        key_error = str(exc)
    session = connection.broker_sessions.filter(status="ACTIVE").first() if connection else None
    return render(request, "brokers/settings.html", {
        "form": form, "masked_api_key": connection.masked_api_key if connection else "Not set",
        "has_secret": bool(connection and connection.encrypted_api_secret),
        "connection_status": connection.status if connection else "NOT_CONFIGURED",
        "last_login": connection.last_successful_login if connection else None,
        "expiry": session.expected_expiration if session else None,
        "error_detail": MESSAGES.get(connection.error_code, "") if connection else "",
        "key_error": key_error,
        # Never pass a credential-bearing model instance to the template.
        "audit_events": BrokerAuditLog.objects.values("event", "outcome", "error_code", "created_at")[:20],
    })


@administrator
@require_POST
def test_connection(request):
    try:
        BrokerReadOnlyClient(request.user).profile()  # No account data retained or rendered.
    except BrokerError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Connection verified using the read-only profile endpoint. No orders were submitted.")
    return redirect("broker_settings")


@administrator
@require_POST
def login_zerodha(request):
    try:
        url = start_login(request)
    except BrokerError as exc:
        messages.error(request, str(exc))
        return redirect("broker_settings")
    return HttpResponseRedirect(url)


@administrator
@require_GET
@sensitive_variables()
def kite_callback(request):
    try:
        complete_login(request)
    except BrokerError as exc:
        connection = BrokerConnection.objects.filter(broker="ZERODHA").first()
        if connection:
            record_error(connection, request.user, exc.code, event="LOGIN_FAILED")
        else:
            audit(None, request.user, "LOGIN_FAILED", "FAILURE", exc.code)
        messages.error(request, str(exc))
    else:
        messages.success(request, "Zerodha connected for research-only access. Your access token is encrypted on this computer.")
    # Remove token/state from the address bar immediately; never render or retain them.
    return redirect("broker_settings")


@administrator
@require_POST
def disconnect_broker(request):
    code = disconnect(request.user)
    if code:
        messages.warning(request, MESSAGES[code])
    else:
        messages.success(request, "Broker disconnected. Stored access tokens and pending logins were removed.")
    return redirect("broker_settings")


@administrator
@require_POST
def delete_credentials(request):
    if request.POST.get("confirm") != "delete":
        messages.error(request, "Select the confirmation checkbox to delete credentials.")
    else:
        code = disconnect(request.user, delete=True)
        messages.warning(request, MESSAGES[code]) if code else messages.success(request, "Saved broker credentials and access tokens deleted. Safe audit history retained.")
    return redirect("broker_settings")
