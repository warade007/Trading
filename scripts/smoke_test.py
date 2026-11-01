"""Exercise the actual local HTTP server; terminate only the child we start."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}/"
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from research.models import DataIngestJob
    demo_id = DataIngestJob.objects.filter(source_kind="SYNTHETIC", status="ACCEPTED").order_by("-id").values_list("id", flat=True).first()
    if demo_id is None:
        raise RuntimeError("Run load_demo before the smoke test.")
    url = f"{base}?dataset={demo_id}"
    opener = build_opener(ProxyHandler({}))
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Server exited before readiness.")
            try:
                with opener.open(url, timeout=2) as response:
                    html = response.read().decode("utf-8")
                    if response.status != 200:
                        raise RuntimeError(f"Unexpected status: {response.status}")
                break
            except URLError:
                time.sleep(0.2)
        else:
            raise RuntimeError("Server did not become ready within 20 seconds.")
        for required in ("RESEARCH ONLY — LIVE ORDERS DISABLED", "SYNTHETIC DEMO — NOT ACTUAL PERFORMANCE", "100.0%", "<svg"):
            if required not in html:
                raise RuntimeError(f"Missing dashboard content: {required}; run load_demo first.")
        for request, expected in (
            (Request(url, method="POST", data=b""), 405),
            (Request(url, headers={"Host": "untrusted.example"}), 400),
            (Request(base + "orders/"), 404),
        ):
            try:
                opener.open(request, timeout=2).close()
            except HTTPError as exc:
                if exc.code != expected:
                    raise RuntimeError(f"Expected {expected}, got {exc.code}") from exc
            else:
                raise RuntimeError(f"Expected rejection {expected}")
        print(f"PASS: HTTP 200, safety/demo labels, coverage, chart; POST 405; invalid Host 400; orders route 404 ({url}).")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
