import io
import json
import logging
import os
import re
import tempfile
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection as database
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from kiteconnect import exceptions as kite_errors
import requests

from brokers.crypto import decrypt, encrypt
from brokers.errors import BrokerError
from brokers.logging import SafeRequestFilter
from brokers.models import BrokerAuditLog, BrokerConnection, BrokerSession
from brokers.sdk import _ReadOnlySDK, _SafeTransport
from brokers.services import (BrokerReadOnlyClient, audit, digest, disconnect,
                              expected_expiration, save_configuration)
from config import local_secrets
from scripts.security_keys import password_cipher

KEY = "syntheticapikey123456"
SECRET = "SYNTHETIC_SECRET_NOT_A_REAL_BROKER_SECRET"
TOKEN = "SYNTHETIC_ACCESS_TOKEN_NEVER_DISPLAY"
CALLBACK = "http://127.0.0.1:8001/kite/callback"
HOST = {"HTTP_HOST": "127.0.0.1:8001"}


class BrokerFixture:
    def setUp(self):
        self.primary = Fernet.generate_key().decode()
        self.override = override_settings(BROKER_FERNET_KEYS=[self.primary],
            AUTH_PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
        self.override.enable()
        self.addCleanup(self.override.disable)
        cache.clear()
        self.admin = get_user_model().objects.create_superuser("testadministrator", password="synthetic-local-password")
        self.client.force_login(self.admin)
        self.no_network = patch("requests.sessions.Session.request", side_effect=AssertionError("Automated tests must never contact a broker"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)

    def configure(self):
        return save_configuration(self.admin, {"api_key": KEY, "api_secret": SECRET, "enabled": True, "redirect_url": CALLBACK})

    def activate(self):
        connection = self.configure()
        session = BrokerSession(connection=connection, initiated_by=self.admin, connection_revision=connection.revision,
            status="ACTIVE", login_time=timezone.now(), expected_expiration=timezone.now() + timedelta(hours=2))
        session.set_token(TOKEN)
        session.save()
        return connection, session

    def start_flow(self, sdk):
        sdk.login_url.return_value = "https://kite.zerodha.com/connect/login?v=3&api_key=" + KEY
        response = self.client.post("/settings/broker/login/", **HOST)
        self.assertEqual(response.status_code, 302)
        params = parse_qs(urlsplit(response.url).query)
        return parse_qs(params["redirect_params"][0])["state"][0]

    def callback(self, state, **extra):
        return self.client.get("/kite/callback", {"state": state, "request_token": "synthetic_request_token", "status": "success", **extra}, **HOST)


class EncryptionTests(BrokerFixture, TestCase):
    def test_database_contains_ciphertext_only_and_server_decrypts(self):
        connection, session = self.activate()
        with database.cursor() as cursor:
            cursor.execute("SELECT encrypted_api_secret FROM brokers_brokerconnection")
            stored_secret = cursor.fetchone()[0]
            cursor.execute("SELECT encrypted_access_token FROM brokers_brokersession")
            stored_token = cursor.fetchone()[0]
        self.assertNotIn(SECRET, stored_secret)
        self.assertNotIn(TOKEN, stored_token)
        self.assertTrue(stored_secret.startswith("v1:"))
        self.assertEqual(connection.get_secret(), SECRET)
        self.assertEqual(session.get_token(), TOKEN)

    def test_context_binding_and_tamper_failure(self):
        ciphertext = encrypt(SECRET, "api_secret")
        for value, purpose in ((ciphertext, "access_token"), (ciphertext[:-5] + "abcde", "api_secret"), (SECRET, "api_secret")):
            with self.assertRaises(BrokerError) as caught:
                decrypt(value, purpose)
            self.assertEqual(caught.exception.code, "KEY_UNAVAILABLE")

    def test_models_reject_plaintext_in_encrypted_columns(self):
        with self.assertRaises(BrokerError):
            BrokerConnection.objects.create(encrypted_api_secret=SECRET)

    def test_missing_invalid_and_wrong_keys_fail_without_mutation(self):
        connection = self.configure()
        ciphertext = connection.encrypted_api_secret
        for keys in ([], ["invalid"], [Fernet.generate_key().decode()], [settings.SECRET_KEY]):
            with self.subTest(keys_type=len(keys)), override_settings(BROKER_FERNET_KEYS=keys):
                with self.assertRaises(BrokerError):
                    connection.get_secret()
                response = self.client.post("/settings/broker/", {"api_key": "", "api_secret": "", "enabled": "on", "redirect_url": CALLBACK, "revision": connection.revision}, **HOST)
                self.assertNotContains(response, SECRET)
                connection.refresh_from_db()
                self.assertEqual(connection.encrypted_api_secret, ciphertext)

    def test_rotation_preserves_data_and_old_backups(self):
        connection, session = self.activate()
        original = connection.encrypted_api_secret
        new = Fernet.generate_key().decode()
        with override_settings(BROKER_FERNET_KEYS=[new, self.primary]):
            call_command("rotate_broker_keys", stdout=io.StringIO())
            self.assertEqual(decrypt(original, "api_secret"), SECRET)
        connection.refresh_from_db()
        session.refresh_from_db()
        with override_settings(BROKER_FERNET_KEYS=[new]):
            self.assertEqual(connection.get_secret(), SECRET)
            self.assertEqual(session.get_token(), TOKEN)
        self.assertNotEqual(original, connection.encrypted_api_secret)

    def test_rotation_failure_rolls_back_all_rows(self):
        connection, session = self.activate()
        original = connection.encrypted_api_secret
        BrokerSession.objects.filter(pk=session.pk).update(encrypted_access_token="damaged")
        with self.assertRaises(CommandError):
            call_command("rotate_broker_keys", stdout=io.StringIO())
        connection.refresh_from_db()
        self.assertEqual(connection.encrypted_api_secret, original)


class BrokerPageTests(BrokerFixture, TestCase):
    def test_browser_login_with_csrf_cookie_form_token_and_origin(self):
        browser = Client(enforce_csrf_checks=True)
        response = browser.get("/accounts/login/", **HOST)
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["Cache-Control"], "no-store")
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode())[1]
        old_cookie = browser.cookies[settings.CSRF_COOKIE_NAME].value
        response = browser.post("/accounts/login/", {
            "username": "testadministrator", "password": "synthetic-local-password",
            "csrfmiddlewaretoken": token,
        }, HTTP_ORIGIN="http://127.0.0.1:8001", HTTP_REFERER="http://127.0.0.1:8001/accounts/login/", **HOST)
        self.assertRedirects(response, "/settings/broker/", fetch_redirect_response=False)
        self.assertNotEqual(browser.cookies[settings.CSRF_COOKIE_NAME].value, old_cookie)
        self.assertEqual(browser.get("/settings/broker/", **HOST).status_code, 200)

    def test_csrf_rejects_null_and_cross_origin_even_with_valid_token(self):
        browser = Client(enforce_csrf_checks=True)
        response = browser.get("/accounts/login/", **HOST)
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode())[1]
        for origin in ("null", "https://untrusted.example", "http://127.0.0.1:8002"):
            with self.subTest(origin=origin):
                response = browser.post("/accounts/login/", {"username": "testadministrator", "password": "synthetic-local-password", "csrfmiddlewaretoken": token}, HTTP_ORIGIN=origin, **HOST)
                self.assertEqual(response.status_code, 403)
                self.assertContains(response, "Open a fresh sign-in page", status_code=403)
                self.assertNotIn("_auth_user_id", browser.session)

    def test_missing_or_stale_csrf_token_has_safe_recovery_page(self):
        browser = Client(enforce_csrf_checks=True)
        browser.get("/accounts/login/", **HOST)
        for data in ({}, {"csrfmiddlewaretoken": "a" * 64}):
            response = browser.post("/accounts/login/", {**data, "password": SECRET}, HTTP_ORIGIN="http://127.0.0.1:8001", **HOST)
            self.assertEqual(response.status_code, 403)
            self.assertContains(response, "Please reload and try again", status_code=403)
            self.assertNotContains(response, SECRET, status_code=403)
            self.assertNotContains(response, "DEBUG=True", status_code=403)

    def test_callback_keeps_strict_referrer_policy(self):
        self.assertEqual(self.client.get("/kite/callback", **HOST)["Referrer-Policy"], "no-referrer")

    def test_anonymous_and_nonadministrator_rejected(self):
        self.client.logout()
        response = self.client.get("/settings/broker/", **HOST)
        self.assertRedirects(response, "/accounts/login/", fetch_redirect_response=False)
        user = get_user_model().objects.create_user("ordinary", is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/settings/broker/", **HOST).status_code, 403)
        self.assertEqual(self.client.post("/settings/broker/test/", **HOST).status_code, 403)

    def test_csrf_on_configuration_and_all_mutations(self):
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        for url in ("/settings/broker/", "/settings/broker/login/", "/settings/broker/test/", "/settings/broker/disconnect/", "/settings/broker/delete/", "/accounts/logout/"):
            self.assertEqual(secure.post(url, {}, **HOST).status_code, 403)
        secure.get("/settings/broker/", **HOST)
        csrf = secure.cookies[settings.CSRF_COOKIE_NAME].value
        response = secure.post("/settings/broker/", {"api_key": KEY, "api_secret": SECRET, "redirect_url": CALLBACK, "enabled": "on", "csrfmiddlewaretoken": csrf}, **HOST)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BrokerConnection.objects.get().get_secret(), SECRET)

    def test_secret_and_key_never_redisplayed_even_on_invalid_form(self):
        self.configure()
        for response in (self.client.get("/settings/broker/", **HOST),
                         self.client.post("/settings/broker/", {"api_key": KEY, "api_secret": SECRET, "redirect_url": "https://evil.example/"}, **HOST)):
            self.assertNotContains(response, SECRET)
            self.assertNotContains(response, KEY)
            self.assertNotContains(response, "v1:gAAAA")
            self.assertContains(response, "••••3456")

    def test_blank_secret_preserved_and_replacement_clears_sessions(self):
        connection, session = self.activate()
        ciphertext = connection.encrypted_api_secret
        values = {"api_key": "", "api_secret": "", "redirect_url": CALLBACK, "enabled": "on", "revision": connection.revision}
        self.client.post("/settings/broker/", values, **HOST)
        connection.refresh_from_db()
        self.assertEqual(connection.encrypted_api_secret, ciphertext)
        session.refresh_from_db()
        self.assertEqual(session.status, "ACTIVE")
        replacement = "NEW_SYNTHETIC_SECRET"
        response = self.client.post("/settings/broker/", {**values, "api_secret": replacement}, follow=True, **HOST)
        self.assertNotContains(response, replacement)
        connection.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual(connection.get_secret(), replacement)
        self.assertEqual(session.encrypted_access_token, "")
        self.assertEqual(session.status, "DISCONNECTED")

    def test_redirect_url_is_exact_and_cannot_be_remote(self):
        for url in ("http://127.0.0.1:8001/kite/callback/", "http://localhost:8001/kite/callback", "https://evil.example/kite/callback", CALLBACK + "?x=1"):
            response = self.client.post("/settings/broker/", {"api_key": KEY, "api_secret": SECRET, "redirect_url": url}, **HOST)
            self.assertEqual(response.status_code, 200)
        self.assertFalse(BrokerConnection.objects.exists())

    def test_stale_update_cannot_replace_settings(self):
        self.configure()
        response = self.client.post("/settings/broker/", {"api_key": "newsyntheticapikey", "api_secret": "REPLACEMENT_SECRET", "revision": uuid.uuid4(), "redirect_url": CALLBACK}, **HOST)
        self.assertContains(response, "Settings changed")
        self.assertEqual(BrokerConnection.objects.get().api_key, KEY)

    @patch("brokers.services.make_sdk")
    def test_test_connection_only_reads_profile_and_sanitizes_errors(self, factory):
        self.activate()
        factory.return_value.profile.return_value = {"user_id": "SECRET_ACCOUNT_ID", "access_token": TOKEN}
        response = self.client.post("/settings/broker/test/", follow=True, **HOST)
        self.assertContains(response, "Connection verified")
        self.assertNotContains(response, TOKEN)
        self.assertNotContains(response, "SECRET_ACCOUNT_ID")
        self.assertEqual([c[0] for c in factory.return_value.method_calls], ["profile"])
        factory.return_value.profile.side_effect = Exception(SECRET + TOKEN)
        response = self.client.post("/settings/broker/test/", follow=True, **HOST)
        self.assertNotContains(response, SECRET)
        self.assertNotContains(response, TOKEN)
        self.assertContains(response, "could not complete")
        self.assertNotIn(SECRET, str(list(BrokerAuditLog.objects.values())))

    @patch("brokers.services.make_sdk")
    def test_disconnect_revokes_and_deletes_tokens(self, factory):
        connection, session = self.activate()
        self.client.post("/settings/broker/disconnect/", **HOST)
        factory.return_value.invalidate_access_token.assert_called_once_with()
        session.refresh_from_db()
        connection.refresh_from_db()
        self.assertEqual(session.encrypted_access_token, "")
        self.assertEqual(connection.status, "DISCONNECTED")
        self.assertEqual(connection.get_secret(), SECRET)

    @patch("brokers.services.make_sdk")
    def test_delete_requires_confirmation_and_works_with_unreadable_key(self, factory):
        connection, session = self.activate()
        self.client.post("/settings/broker/delete/", **HOST)
        connection.refresh_from_db()
        self.assertEqual(connection.get_secret(), SECRET)
        with override_settings(BROKER_FERNET_KEYS=[]):
            self.client.post("/settings/broker/delete/", {"confirm": "delete"}, **HOST)
        connection.refresh_from_db()
        session.refresh_from_db()
        self.assertEqual((connection.api_key, connection.encrypted_api_secret, session.encrypted_access_token), ("", "", ""))
        self.assertFalse(connection.enabled)
        factory.assert_not_called()
        self.assertTrue(BrokerAuditLog.objects.filter(event="CREDENTIALS_DELETED").exists())

    def test_admin_login_and_throttle(self):
        self.client.logout()
        for _ in range(10):
            self.client.post("/accounts/login/", {"username": "testadministrator", "password": "wrong"}, **HOST)
        self.assertEqual(self.client.post("/accounts/login/", {}, **HOST).status_code, 429)
        cache.clear()
        response = self.client.post("/accounts/login/", {"username": "testadministrator", "password": "synthetic-local-password"}, **HOST)
        self.assertRedirects(response, "/settings/broker/", fetch_redirect_response=False)


class LoginFlowTests(BrokerFixture, TestCase):
    @patch("brokers.services.make_sdk")
    def test_mock_success_state_binding_encryption_and_replay(self, factory):
        self.configure()
        sdk = factory.return_value
        sdk.generate_session.return_value = {"access_token": TOKEN, "user_name": "Never display", "api_secret": SECRET}
        state = self.start_flow(sdk)
        pending = BrokerSession.objects.get()
        self.assertEqual(pending.state_digest, digest(state))
        self.assertNotIn(state, str(list(BrokerSession.objects.values())))
        response = self.callback(state)
        self.assertRedirects(response, "/settings/broker/", fetch_redirect_response=False)
        self.assertNotIn("request_token", response.url)
        pending.refresh_from_db()
        self.assertEqual(pending.status, "ACTIVE")
        self.assertEqual(pending.get_token(), TOKEN)
        self.assertEqual(pending.state_digest, "")
        self.assertIsNotNone(BrokerConnection.objects.get().last_successful_login)
        self.callback(state)
        sdk.generate_session.assert_called_once_with("synthetic_request_token", SECRET)

    @patch("brokers.services.make_sdk")
    def test_wrong_missing_expired_and_duplicate_state_never_exchange(self, factory):
        self.configure()
        state = self.start_flow(factory.return_value)
        self.callback("x" * 43)
        self.client.get("/kite/callback", {"request_token": "synthetic_request_token"}, **HOST)
        self.callback([state, state])
        BrokerSession.objects.update(expected_expiration=timezone.now() - timedelta(seconds=1))
        self.callback(state)
        factory.return_value.generate_session.assert_not_called()

    @patch("brokers.services.make_sdk")
    def test_flow_cannot_transfer_between_browsers_or_users(self, factory):
        self.configure()
        state = self.start_flow(factory.return_value)
        another = Client()
        another.force_login(self.admin)
        another.get("/kite/callback", {"state": state, "request_token": "synthetic_request_token"}, **HOST)
        other = get_user_model().objects.create_superuser("otheradmin", password="synthetic-other-password")
        another.force_login(other)
        another.get("/kite/callback", {"state": state, "request_token": "synthetic_request_token"}, **HOST)
        factory.return_value.generate_session.assert_not_called()

    @patch("brokers.services.make_sdk")
    def test_config_change_during_exchange_cannot_activate_token(self, factory):
        connection = self.configure()
        state = self.start_flow(factory.return_value)
        def change(*args):
            BrokerConnection.objects.filter(pk=connection.pk).update(revision=uuid.uuid4())
            return {"access_token": TOKEN}
        factory.return_value.generate_session.side_effect = change
        self.callback(state)
        self.assertFalse(BrokerSession.objects.filter(status="ACTIVE").exists())
        self.assertEqual(BrokerSession.objects.get().encrypted_access_token, "")

    @patch("brokers.services.make_sdk")
    def test_login_failure_is_sanitized_and_not_retried(self, factory):
        self.configure()
        state = self.start_flow(factory.return_value)
        factory.return_value.generate_session.side_effect = requests.Timeout(SECRET + TOKEN)
        response = self.callback(state)
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response.url, **HOST)
        self.assertNotContains(page, SECRET)
        self.assertNotContains(page, TOKEN)
        self.assertEqual(BrokerSession.objects.get().status, "FAILED")
        factory.return_value.generate_session.assert_called_once()

    def test_logged_out_callback_discards_sensitive_query(self):
        self.client.logout()
        response = self.callback("x" * 43)
        self.assertEqual(response.url, "/accounts/login/")
        self.assertNotIn("synthetic_request_token", response.url)

    def test_expected_expiry_is_ist_boundary(self):
        ist = ZoneInfo("Asia/Kolkata")
        for hour, day in ((5, 1), (6, 2), (15, 2)):
            expiry = expected_expiration(datetime(2026, 11, 1, hour, tzinfo=ist))
            self.assertEqual((expiry.day, expiry.hour), (day, 6))


class ReadOnlyServiceTests(BrokerFixture, TestCase):
    @patch("brokers.services.make_sdk")
    def test_invalid_broker_session_clears_ciphertext(self, factory):
        connection, session = self.activate()
        factory.return_value.profile.side_effect = kite_errors.TokenException(SECRET)
        with self.assertRaises(BrokerError) as caught:
            BrokerReadOnlyClient(self.admin).profile()
        self.assertEqual(caught.exception.code, "SESSION_EXPIRED")
        session.refresh_from_db()
        self.assertEqual((session.status, session.encrypted_access_token), ("EXPIRED", ""))
        factory.return_value.profile.assert_called_once()

    @patch("brokers.services.make_sdk")
    def test_locally_expired_session_never_contacts_broker(self, factory):
        connection, session = self.activate()
        BrokerSession.objects.filter(pk=session.pk).update(expected_expiration=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(BrokerError):
            BrokerReadOnlyClient().profile()
        factory.assert_not_called()
        session.refresh_from_db()
        self.assertEqual(session.encrypted_access_token, "")

    @patch("brokers.services.make_sdk")
    def test_profile_instruments_history_quotes_and_depth_only(self, factory):
        self.activate()
        sdk = factory.return_value
        sdk.profile.return_value = {"broker": "ZERODHA"}
        sdk.instruments.return_value = [{"instrument_token": 123}]
        sdk.historical_data.return_value = [{"open": 100}]
        sdk.quote.return_value = {"NSE:DEMO": {"depth": {"buy": [], "sell": []}}, "NSE:NIFTY 50": {}}
        client = BrokerReadOnlyClient(self.admin)
        self.assertEqual(client.profile(), {"broker": "ZERODHA"})
        self.assertEqual(client.instruments("NSE"), [{"instrument_token": 123}])
        now = timezone.now()
        self.assertEqual(client.historical_data(123, now - timedelta(days=1), now), [{"open": 100}])
        self.assertIn("NSE:DEMO", client.quotes(["NSE:DEMO"]))
        self.assertIsNone(client.market_depth(["NSE:NIFTY 50"])["NSE:NIFTY 50"])
        self.assertEqual({c[0] for c in sdk.method_calls}, {"profile", "instruments", "historical_data", "quote"})
        self.assertFalse(hasattr(client, "place_order"))
        self.assertFalse(hasattr(client, "modify_order"))
        self.assertFalse(hasattr(client, "cancel_order"))

    @patch("brokers.services.time.sleep")
    @patch("brokers.services.make_sdk")
    def test_safe_get_retry_and_rate_limit_are_bounded(self, factory, sleep):
        self.activate()
        sdk = factory.return_value
        sdk.profile.side_effect = [requests.Timeout(SECRET), {"broker": "ZERODHA"}]
        self.assertEqual(BrokerReadOnlyClient().profile(), {"broker": "ZERODHA"})
        self.assertEqual(sdk.profile.call_count, 2)
        sdk.profile.reset_mock()
        sdk.profile.side_effect = kite_errors.GeneralException(TOKEN, code=429)
        with self.assertRaises(BrokerError) as caught:
            BrokerReadOnlyClient().profile()
        self.assertEqual(caught.exception.code, "RATE_LIMITED")
        self.assertEqual(sdk.profile.call_count, 2)

    def test_invalid_market_inputs_fail_before_network(self):
        client = BrokerReadOnlyClient()
        for invoke in (lambda: client.instruments("../orders"), lambda: client.quotes(["bad"]),
                       lambda: client.historical_data(1, datetime.now(), datetime.now()),
                       lambda: client.historical_data(-1, timezone.now(), timezone.now())):
            with self.assertRaises(BrokerError):
                invoke()


class TransportSafetyTests(SimpleTestCase):
    def test_official_sdk_allowed_endpoint_wiring_with_mock_transport(self):
        sdk = _ReadOnlySDK(KEY, TOKEN)
        reply = requests.Response()
        reply.status_code = 200
        reply.headers["content-type"] = "application/json"
        reply._content = json.dumps({"status": "success", "data": {"broker": "ZERODHA"}}).encode()
        with patch("brokers.sdk.pace"), patch("requests.Session.request", return_value=reply) as outgoing:
            self.assertEqual(sdk.profile(), {"broker": "ZERODHA"})
            self.assertEqual(outgoing.call_args.args[:2], ("GET", "https://api.kite.trade/user/profile"))
            self.assertIn("Authorization", outgoing.call_args.kwargs["headers"])
            self.assertFalse(outgoing.call_args.kwargs["allow_redirects"])
            reply._content = b'{"status":"success","data":true}'
            sdk.invalidate_access_token()
            self.assertEqual(outgoing.call_args.args[:2], ("DELETE", "https://api.kite.trade/session/token"))

    def test_sdk_blocks_every_nonallowlisted_route_before_transport(self):
        sdk = _ReadOnlySDK(KEY)
        with patch.object(sdk.reqsession, "request") as outgoing:
            for route in sdk._routes:
                for method in ("GET", "POST", "PUT", "DELETE"):
                    if (route, method) not in sdk.PERMITTED:
                        with self.assertRaises(BrokerError):
                            sdk._request(route, method)
            outgoing.assert_not_called()

    def test_transport_blocks_orders_arbitrary_hosts_and_redirects(self):
        transport = _SafeTransport()
        with patch("requests.Session.request") as outgoing:
            for method, url in (("POST", "https://api.kite.trade/orders/regular"), ("PUT", "https://api.kite.trade/session/token"),
                                ("GET", "https://evil.example/user/profile"), ("GET", "http://api.kite.trade/user/profile"),
                                ("GET", "https://api.kite.trade/user/profile?access_token=bad")):
                with self.assertRaises(BrokerError):
                    transport.request(method, url)
            outgoing.assert_not_called()
        with patch("brokers.sdk.pace"), patch("requests.Session.request", return_value=Mock(status_code=302)) as outgoing:
            with self.assertRaises(BrokerError):
                transport.request("GET", "https://api.kite.trade/user/profile", allow_redirects=True, verify=False)
            self.assertFalse(outgoing.call_args.kwargs["allow_redirects"])
            self.assertTrue(outgoing.call_args.kwargs["verify"])
            self.assertFalse(transport.trust_env)

    def test_log_filter_removes_callback_query_and_exception_secrets(self):
        record = logging.LogRecord("django.server", logging.ERROR, "", 1,
            "GET /kite/callback?request_token=%s&state=%s", (TOKEN, SECRET), (Exception, Exception(SECRET), None))
        record.status_code = 302
        SafeRequestFilter().filter(record)
        self.assertNotIn(TOKEN, record.getMessage())
        self.assertNotIn(SECRET, record.getMessage())
        self.assertIsNone(record.exc_info)

    def test_audit_rejects_free_text_payloads(self):
        with self.assertRaises(ValueError):
            audit(None, None, TOKEN)


class LocalKeyBackupTests(SimpleTestCase):
    def test_encrypted_key_backup_roundtrip(self):
        salt = os.urandom(16)
        cipher = password_cipher("synthetic backup test passphrase", salt)
        sealed = cipher.encrypt(b"synthetic key bundle")
        self.assertNotIn(b"synthetic key bundle", sealed)
        self.assertEqual(password_cipher("synthetic backup test passphrase", salt).decrypt(sealed), b"synthetic key bundle")

    def test_dpapi_initialize_is_idempotent_and_corruption_fails_closed(self):
        if os.name != "nt":
            self.skipTest("Windows DPAPI test")
        with tempfile.TemporaryDirectory() as directory, patch("config.local_secrets.vault_path", return_value=Path(directory) / "keys.dpapi"):
            self.assertTrue(local_secrets.initialize())
            bundle = local_secrets.load_bundle()
            blob = local_secrets.vault_path().read_bytes()
            self.assertNotIn(bundle["broker_keys"][0].encode(), blob)
            self.assertNotIn(bundle["django_secret"].encode(), blob)
            self.assertFalse(local_secrets.initialize())
            self.assertEqual(local_secrets.load_bundle(), bundle)
            local_secrets.vault_path().write_bytes(b"damaged")
            with self.assertRaises(local_secrets.LocalKeyError):
                local_secrets.initialize()
            self.assertEqual(local_secrets.vault_path().read_bytes(), b"damaged")
