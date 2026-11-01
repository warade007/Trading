"""Single research-only broker boundary; no order API methods are exposed."""
import hashlib
import re
import secrets
import time
import uuid
from datetime import datetime, time as day_time, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from kiteconnect import exceptions as kite_errors

from .crypto import keyring
from .errors import BrokerError, MESSAGES
from .models import BrokerConnection, BrokerSession, BrokerAuditLog
from .sdk import make_sdk

EVENTS = {"SETTINGS_SAVED", "CREDENTIALS_DELETED", "LOGIN_STARTED", "LOGIN_SUCCEEDED", "LOGIN_FAILED", "SESSION_EXPIRED", "READ_SUCCEEDED", "READ_FAILED", "DISCONNECTED", "KEYS_ROTATED", "ADMIN_LOGIN_FAILED"}


def audit(connection, actor, event, outcome="SUCCESS", code=""):
    if event not in EVENTS or outcome not in {"SUCCESS", "FAILURE"} or (code and code not in MESSAGES):
        raise ValueError("Audit fields must use safe enumerated values.")
    return BrokerAuditLog.objects.create(connection=connection, actor=actor if actor and actor.is_authenticated else None,
                                         event=event, outcome=outcome, error_code=code)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def expire_sessions(connection):
    count = connection.broker_sessions.filter(status__in=["ACTIVE", "PENDING", "EXCHANGING"], expected_expiration__lte=timezone.now()).update(
        status="EXPIRED", encrypted_access_token="", state_digest="", browser_session_digest="")
    if count and not connection.broker_sessions.filter(status="ACTIVE").exists():
        connection.status = "LOGIN_REQUIRED"
        connection.error_code = "SESSION_EXPIRED"
        connection.save(update_fields=["status", "error_code", "updated_at"])
        audit(connection, None, "SESSION_EXPIRED")


@sensitive_variables()
def save_configuration(actor, values):
    keyring()  # Fail closed even on blank-secret updates when the key is missing.
    with transaction.atomic():
        connection, created = BrokerConnection.objects.get_or_create(broker="ZERODHA")
        connection = BrokerConnection.objects.select_for_update().get(pk=connection.pk)
        submitted = values.get("revision")
        if not created and submitted != connection.revision:
            raise BrokerError("CONFIG_CHANGED")
        api_key = values["api_key"] or connection.api_key
        secret = values["api_secret"]
        if not api_key or (not secret and not connection.encrypted_api_secret):
            raise BrokerError("NOT_CONFIGURED")
        if not secret:
            connection.get_secret()  # Validate decryptability, preserving exact ciphertext.
        changed = bool(secret) or api_key != connection.api_key or values["enabled"] != connection.enabled or values["redirect_url"] != connection.redirect_url
        connection.api_key = api_key
        if secret:
            connection.set_secret(secret)
        connection.redirect_url = values["redirect_url"]
        connection.enabled = values["enabled"]
        if changed:
            connection.revision = uuid.uuid4()
            connection.broker_sessions.update(status="DISCONNECTED", encrypted_access_token="", state_digest="", browser_session_digest="")
            connection.status = "LOGIN_REQUIRED" if connection.enabled else "DISABLED"
        connection.error_code = ""
        connection.save()
        audit(connection, actor, "SETTINGS_SAVED")
    return connection


def configured_connection():
    connection = BrokerConnection.objects.filter(broker="ZERODHA").first()
    if not connection or not connection.enabled or not connection.api_key or not connection.encrypted_api_secret:
        raise BrokerError("NOT_CONFIGURED")
    return connection


def record_error(connection, actor, code, event="READ_FAILED"):
    BrokerConnection.objects.filter(pk=connection.pk).update(error_code=code)
    audit(connection, actor, event, "FAILURE", code)


@sensitive_variables()
def start_login(request):
    connection = configured_connection()
    connection.get_secret()
    if request.build_absolute_uri("/kite/callback") != connection.redirect_url:
        raise BrokerError("INVALID_INPUT")
    if not request.session.session_key:
        request.session.save()
    state = secrets.token_urlsafe(32)
    with transaction.atomic():
        connection = BrokerConnection.objects.select_for_update().get(pk=connection.pk)
        if not connection.enabled or not connection.api_key or not connection.encrypted_api_secret:
            raise BrokerError("NOT_CONFIGURED")
        connection.broker_sessions.filter(status__in=["PENDING", "EXCHANGING"]).update(status="SUPERSEDED", state_digest="", browser_session_digest="")
        BrokerSession.objects.create(connection=connection, initiated_by=request.user,
            connection_revision=connection.revision, state_digest=digest(state),
            browser_session_digest=digest(request.session.session_key),
            expected_expiration=timezone.now() + timedelta(minutes=10))
        audit(connection, request.user, "LOGIN_STARTED")
    # Official redirect_params round-trips a state parameter to the registered URL.
    return make_sdk(connection.api_key).login_url() + "&" + urlencode({"redirect_params": urlencode({"state": state})})


def expected_expiration(now):
    local = now.astimezone(ZoneInfo("Asia/Kolkata"))
    # Conservative: expire at the next 06:00 IST boundary, even for pre-06:00 logins.
    expiry = datetime.combine(local.date(), day_time(6), local.tzinfo)
    if expiry <= local:
        expiry += timedelta(days=1)
    return expiry


@sensitive_variables()
def complete_login(request):
    state, token = request.GET.get("state", ""), request.GET.get("request_token", "")
    if (len(request.GET.getlist("state")) != 1 or len(request.GET.getlist("request_token")) != 1
            or not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", state)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,512}", token)
            or not request.session.session_key or request.GET.get("status", "success") != "success"):
        raise BrokerError("FLOW_INVALID")
    connection = configured_connection()
    with transaction.atomic():
        flow = BrokerSession.objects.select_for_update().filter(connection=connection, state_digest=digest(state), status="PENDING", initiated_by=request.user).first()
        if (not flow or not secrets.compare_digest(flow.browser_session_digest, digest(request.session.session_key))
                or flow.expected_expiration <= timezone.now() or flow.connection_revision != connection.revision):
            raise BrokerError("FLOW_INVALID")
        # Conditional claim also protects single-use state on SQLite (no row locks).
        claimed = BrokerSession.objects.filter(pk=flow.pk, status="PENDING").update(status="EXCHANGING", state_digest="")
        if claimed != 1:
            raise BrokerError("FLOW_INVALID")
    try:
        payload = _invoke(make_sdk(connection.api_key), "generate_session", token, connection.get_secret(), retry=False)
        access_token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(access_token, str) or not 8 <= len(access_token) <= 2048:
            raise BrokerError("AUTH_FAILED")
        now = timezone.now()
        with transaction.atomic():
            fresh = BrokerConnection.objects.select_for_update().get(pk=connection.pk)
            flow.refresh_from_db()
            if not fresh.enabled or fresh.revision != flow.connection_revision or flow.status != "EXCHANGING" or flow.expected_expiration <= now:
                raise BrokerError("CONFIG_CHANGED")
            fresh.broker_sessions.filter(status="ACTIVE").update(status="SUPERSEDED", encrypted_access_token="")
            flow.set_token(access_token)
            flow.login_time = now
            flow.expected_expiration = expected_expiration(now)
            flow.status = "ACTIVE"
            flow.browser_session_digest = ""
            flow.save()
            fresh.status, fresh.error_code, fresh.last_successful_login = "CONNECTED", "", now
            fresh.save(update_fields=["status", "error_code", "last_successful_login", "updated_at"])
            audit(fresh, request.user, "LOGIN_SUCCEEDED")
    except BrokerError:
        BrokerSession.objects.filter(pk=flow.pk).update(status="FAILED", encrypted_access_token="", state_digest="", browser_session_digest="")
        raise


@sensitive_variables()
def _invoke(client, method, *args, retry=True, **kwargs):
    # No arbitrary operation supplied by browser/user input ever reaches this boundary.
    if method not in {"generate_session", "invalidate_access_token", "profile", "instruments", "historical_data", "quote"}:
        raise BrokerError("OPERATION_BLOCKED")
    for attempt in range(2 if retry else 1):
        try:
            return getattr(client, method)(*args, **kwargs)
        except BrokerError:
            raise
        except kite_errors.TokenException:
            raise BrokerError("SESSION_EXPIRED") from None
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code == 429:
                safe_code, transient = "RATE_LIMITED", True
            elif isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError, kite_errors.NetworkException)) or code in (500, 502, 503, 504):
                safe_code, transient = "NETWORK_ERROR", True
            else:
                safe_code, transient = "API_ERROR", False
            if retry and transient and attempt == 0:
                time.sleep(1.1)
                continue
            raise BrokerError(safe_code) from None


class BrokerReadOnlyClient:
    """Public internal service: profile, instruments, candles, quotes and depth only."""
    def __init__(self, actor=None):
        self.actor = actor

    @sensitive_variables()
    def _read(self, method, *args, **kwargs):
        connection = configured_connection()
        expire_sessions(connection)
        session = connection.broker_sessions.filter(status="ACTIVE").first()
        if not session:
            raise BrokerError("LOGIN_REQUIRED")
        try:
            result = _invoke(make_sdk(connection.api_key, session.get_token()), method, *args, **kwargs)
        except BrokerError as exc:
            if exc.code == "SESSION_EXPIRED":
                session.status, session.encrypted_access_token = "EXPIRED", ""
                session.save(update_fields=["status", "encrypted_access_token", "updated_at"])
                BrokerConnection.objects.filter(pk=connection.pk).update(status="LOGIN_REQUIRED")
            record_error(connection, self.actor, exc.code)
            raise
        if not BrokerSession.objects.filter(pk=session.pk, status="ACTIVE", connection__revision=connection.revision, connection__enabled=True).exists():
            raise BrokerError("CONFIG_CHANGED")
        BrokerConnection.objects.filter(pk=connection.pk, revision=connection.revision).update(error_code="", status="CONNECTED")
        audit(connection, self.actor, "READ_SUCCEEDED")
        return result

    def profile(self):
        return self._read("profile")

    def instruments(self, exchange=None):
        if exchange is not None and exchange not in {"NSE", "BSE", "NFO", "BFO", "CDS", "BCD", "MCX"}:
            raise BrokerError("INVALID_INPUT")
        return self._read("instruments", exchange)

    def historical_data(self, instrument_token, from_date, to_date, interval="minute", oi=False):
        if type(instrument_token) is not int or instrument_token <= 0 or interval not in {"minute", "3minute", "5minute", "10minute", "15minute", "30minute", "60minute", "day"}:
            raise BrokerError("INVALID_INPUT")
        if not isinstance(from_date, datetime) or not isinstance(to_date, datetime) or timezone.is_naive(from_date) or timezone.is_naive(to_date) or not timedelta(0) < to_date - from_date <= timedelta(days=30):
            raise BrokerError("INVALID_INPUT")
        ist = ZoneInfo("Asia/Kolkata")
        return self._read("historical_data", instrument_token, from_date.astimezone(ist), to_date.astimezone(ist), interval, continuous=False, oi=bool(oi))

    def quotes(self, instruments):
        if not isinstance(instruments, (list, tuple)) or not 1 <= len(instruments) <= 100 or any(not isinstance(i, str) or not re.fullmatch(r"[A-Z]{3}:[A-Za-z0-9 &_.-]{1,64}", i) for i in instruments):
            raise BrokerError("INVALID_INPUT")
        return self._read("quote", list(instruments))

    def market_depth(self, instruments):
        return {symbol: value.get("depth") for symbol, value in self.quotes(instruments).items()}


@sensitive_variables()
def disconnect(actor, delete=False):
    connection = BrokerConnection.objects.filter(broker="ZERODHA").first()
    if not connection:
        return ""
    failed = False
    active = connection.broker_sessions.filter(status="ACTIVE").first()
    if active:
        try:
            _invoke(make_sdk(connection.api_key, active.get_token()), "invalidate_access_token", retry=False)
        except BrokerError:
            failed = True
    with transaction.atomic():
        connection = BrokerConnection.objects.select_for_update().get(pk=connection.pk)
        connection.broker_sessions.update(status="DISCONNECTED", encrypted_access_token="", state_digest="", browser_session_digest="")
        connection.status = "NOT_CONFIGURED" if delete else "DISCONNECTED"
        connection.error_code = "DISCONNECT_LOCAL" if failed else ""
        connection.revision = uuid.uuid4()
        if delete:
            connection.api_key, connection.encrypted_api_secret, connection.enabled = "", "", False
        connection.save()
        audit(connection, actor, "CREDENTIALS_DELETED" if delete else "DISCONNECTED", "FAILURE" if failed else "SUCCESS", connection.error_code)
    return connection.error_code
