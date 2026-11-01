from django.http import HttpResponse, HttpResponseForbidden, HttpResponseNotAllowed


class LocalReadOnlyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check both the peer and Host. Never trust forwarded headers.
        if request.META.get("REMOTE_ADDR") != "127.0.0.1":
            return HttpResponseForbidden("Local research access only.")
        request.get_host()
        writable = request.path in {"/accounts/login/", "/accounts/logout/", "/settings/broker/", "/settings/broker/test/", "/settings/broker/login/", "/settings/broker/disconnect/", "/settings/broker/delete/"}
        if request.method not in {"GET", "HEAD"} and not (request.method == "POST" and writable):
            return HttpResponseNotAllowed(["GET", "HEAD"])
        response = self.get_response(request)
        if response.status_code >= 500 and request.path.startswith(("/settings/broker", "/kite/", "/accounts/")):
            response = HttpResponse("Broker request could not be completed. No credentials are displayed. Try again or review the safe audit log.", status=500)
        response["Content-Security-Policy"] = (
            "default-src 'none'; style-src 'unsafe-inline'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self' https://kite.zerodha.com"
        )
        response["Referrer-Policy"] = "no-referrer"
        response["Cache-Control"] = "no-store"
        return response
