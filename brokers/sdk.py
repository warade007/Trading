"""Private official-SDK adapter. Every outgoing request is allowlisted twice."""
import re
import threading
import time
from urllib.parse import urlsplit

import requests
from kiteconnect import KiteConnect

from .errors import BrokerError

_lock = threading.Lock()
_last_request = 0.0


def pace():
    # One local Django worker: deliberately slower than all documented read limits.
    global _last_request
    with _lock:
        wait = 1.05 - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()


class _SafeTransport(requests.Session):
    def __init__(self):
        super().__init__()
        self.trust_env = False  # No implicit proxy, netrc credentials or alternate CA.

    def request(self, method, url, **kwargs):
        parsed = urlsplit(url)
        read_path = re.fullmatch(r"/(user/profile|quote|instruments(?:/[A-Z]+|/historical/[0-9]+/(?:minute|3minute|5minute|10minute|15minute|30minute|60minute|day))?)", parsed.path)
        auth_path = parsed.path == "/session/token" and method in {"POST", "DELETE"}
        if parsed.scheme != "https" or parsed.netloc != "api.kite.trade" or parsed.query or parsed.fragment or not ((method == "GET" and read_path) or auth_path):
            raise BrokerError("OPERATION_BLOCKED")
        kwargs.update(verify=True, allow_redirects=False, timeout=(3.05, 10), proxies={})
        pace()
        response = super().request(method, url, **kwargs)
        if 300 <= response.status_code < 400:
            response.close()
            raise BrokerError("API_ERROR")
        return response


class _ReadOnlySDK(KiteConnect):
    PERMITTED = {
        ("api.token", "POST"), ("api.token.invalidate", "DELETE"),
        ("user.profile", "GET"), ("market.instruments.all", "GET"),
        ("market.instruments", "GET"), ("market.historical", "GET"), ("market.quote", "GET"),
    }

    def __init__(self, api_key, access_token=None):
        super().__init__(api_key=api_key, access_token=access_token, root="https://api.kite.trade", debug=False, timeout=10, disable_ssl=False)
        self.reqsession.close()
        self.reqsession = _SafeTransport()

    def _request(self, route, method, **kwargs):
        if (route, method) not in self.PERMITTED:
            raise BrokerError("OPERATION_BLOCKED")
        return super()._request(route, method, **kwargs)


def make_sdk(api_key, access_token=None):
    return _ReadOnlySDK(api_key, access_token)
