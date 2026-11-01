import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from research.models import Candle, DataIngestJob, DataQualityIssue, Instrument, InstrumentSnapshot
from research.services import import_dataset, resample_dataset
from tests.helpers import FIXTURES, RAW, encode_rows, metadata, rows


class ImportFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.override = override_settings(RESEARCH_ARCHIVE_DIR=self.root / "raw")
        self.override.enable()
        self.addCleanup(self.override.disable)

    def load(self, raw=RAW, meta=None):
        csv = self.root / "input.csv"
        manifest = self.root / "manifest.json"
        csv.write_bytes(raw)
        manifest.write_text(json.dumps(meta or metadata()), encoding="utf-8")
        return import_dataset(csv, manifest)


class ImportTests(ImportFixture, TestCase):
    def test_idempotent_import_and_resample(self):
        job, created = self.load()
        self.assertTrue(created)
        same, created = self.load()
        self.assertFalse(created)
        self.assertEqual(same.pk, job.pk)
        self.assertEqual((Instrument.objects.count(), InstrumentSnapshot.objects.count(), Candle.objects.count()), (1, 1, 750))
        for interval, count in ((5, 150), (15, 50)):
            self.assertEqual(resample_dataset(job.pk, interval), (count, 0, True))
            self.assertEqual(resample_dataset(job.pk, interval), (count, 0, False))
        self.assertEqual(job.coverage, 100)
        self.assertEqual(Candle.objects.count(), 950)

    def test_raw_and_canonical_manifest_archived_by_hash(self):
        job, _ = self.load()
        self.assertEqual((self.root / "raw" / f"{job.csv_sha256}.csv").read_bytes(), RAW)
        stored = json.loads((self.root / "raw" / f"{job.manifest_sha256}.json").read_bytes())
        self.assertEqual(stored, metadata())

    def test_archive_corruption_never_overwritten(self):
        job, _ = self.load()
        archive = self.root / "raw" / f"{job.csv_sha256}.csv"
        archive.write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "corrupt"):
            self.load()
        self.assertEqual(archive.read_bytes(), b"corrupt")

    def test_archive_budget_prevents_database_write(self):
        with override_settings(RESEARCH_ARCHIVE_BUDGET=1):
            with self.assertRaisesRegex(ValueError, "budget"):
                self.load()
        self.assertEqual(DataIngestJob.objects.count(), 0)

    def test_rejected_row_atomic_and_report_retained(self):
        data = rows()
        data[-1]["low"] = "999"
        job, _ = self.load(encode_rows(data))
        self.assertEqual(job.status, "REJECTED")
        self.assertEqual((Candle.objects.count(), Instrument.objects.count()), (0, 0))
        self.assertTrue(job.issues.filter(code="INVALID_ROW").exists())
        with self.assertRaises(ValueError):
            resample_dataset(job.pk, 5)

    def test_storage_failure_rolls_back_every_database_write(self):
        with patch("research.services._store_bars", side_effect=RuntimeError("injected storage failure")):
            with self.assertRaises(RuntimeError):
                self.load()
        self.assertEqual((DataIngestJob.objects.count(), Candle.objects.count(), Instrument.objects.count(), InstrumentSnapshot.objects.count(), DataQualityIssue.objects.count()), (0, 0, 0, 0, 0))

    def test_gap_report_coverage_and_no_derived_fill(self):
        job, _ = self.load(encode_rows(rows()[1:]))
        self.assertEqual((job.imported_minutes, job.expected_minutes), (749, 750))
        self.assertLess(job.coverage, 100)
        self.assertEqual(resample_dataset(job.pk, 5)[:2], (149, 1))
        self.assertEqual(resample_dataset(job.pk, 5)[2], False)
        self.assertEqual(job.issues.filter(code="INCOMPLETE_BUCKET").count(), 1)

    def test_changed_raw_data_is_a_separate_dataset(self):
        first, _ = self.load()
        data = rows()
        data[0]["volume"] = "0"
        second, _ = self.load(encode_rows(data))
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(first.candles.first().volume, 1000)
        self.assertEqual(second.candles.first().volume, 0)

    def test_synthetic_and_user_supplied_cannot_merge(self):
        demo, _ = self.load()
        meta = metadata()
        meta.update(source_kind="USER_SUPPLIED", source_reference="Local example; rights supplied by owner")
        supplied, _ = self.load(meta=meta)
        self.assertNotEqual(demo.snapshot.instrument_id, supplied.snapshot.instrument_id)
        self.assertEqual((demo.candles.count(), supplied.candles.count()), (750, 750))

    def test_conflicting_snapshot_rejected_without_overwrite(self):
        first, _ = self.load()
        meta = metadata()
        meta["instrument"]["lot_size"] = 2
        rejected, _ = self.load(meta=meta)
        self.assertEqual(rejected.status, "REJECTED")
        self.assertEqual(first.snapshot.lot_size, 1)
        self.assertEqual((InstrumentSnapshot.objects.count(), Candle.objects.count()), (1, 750))
        self.assertTrue(rejected.issues.filter(code="SNAPSHOT_CONFLICT").exists())

    def test_database_rejects_duplicate_and_invalid_bar(self):
        job, _ = self.load()
        candle = job.candles.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            candle.pk = None
            candle.save(force_insert=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Candle.objects.filter(dataset=job).update(low=9999)

    def test_corrupt_derived_history_never_overwritten(self):
        job, _ = self.load()
        resample_dataset(job.pk, 5)
        job.candles.filter(interval=5).update(volume=0)
        with self.assertRaisesRegex(ValueError, "differ"):
            resample_dataset(job.pk, 5)

    def test_manifest_formatting_does_not_duplicate_dataset(self):
        first, _ = self.load()
        manifest = self.root / "manifest.json"
        manifest.write_text(json.dumps(metadata(), indent=4), encoding="utf-8")
        same, created = import_dataset(self.root / "input.csv", manifest)
        self.assertFalse(created)
        self.assertEqual(first.pk, same.pk)

    def test_bad_manifest_fails_without_database_mutation(self):
        for value in (None, [], {}, "bad"):
            with self.subTest(value=value):
                meta = metadata()
                meta["instrument"] = value
                with self.assertRaises(ValueError):
                    self.load(meta=meta)
        self.assertEqual(DataIngestJob.objects.count(), 0)

    def test_management_commands_and_failure_exit(self):
        output = io.StringIO()
        call_command("import_candles", str(FIXTURES / "synthetic.csv"), manifest=str(FIXTURES / "synthetic.manifest.json"), stdout=output)
        self.assertIn("750/750", output.getvalue())
        job = DataIngestJob.objects.get()
        call_command("resample_bars", dataset=job.pk, interval=5, stdout=output)
        self.assertIn("150 x 5m", output.getvalue())
        data = rows()
        data[0]["open"] = "-1"
        self.load(encode_rows(data))
        with self.assertRaises(CommandError):
            call_command("import_candles", str(self.root / "input.csv"), manifest=str(self.root / "manifest.json"), stdout=output)
        with self.assertRaises(CommandError):
            call_command("resample_bars", dataset=99999, interval=5, stdout=output)

    def test_demo_command_repeat_is_safe(self):
        for _ in range(2):
            call_command("load_demo", stdout=io.StringIO())
        self.assertEqual((DataIngestJob.objects.count(), Candle.objects.count()), (1, 950))


class DashboardTests(ImportFixture, TestCase):
    def test_dashboard_empty_then_populated(self):
        response = self.client.get("/", HTTP_HOST="127.0.0.1")
        self.assertContains(response, "RESEARCH ONLY — LIVE ORDERS DISABLED")
        self.assertContains(response, "No dataset loaded")
        job, _ = self.load()
        resample_dataset(job.pk, 5)
        response = self.client.get("/", HTTP_HOST="127.0.0.1")
        self.assertContains(response, "SYNTHETIC DEMO — NOT ACTUAL PERFORMANCE")
        self.assertContains(response, "100.0%")
        self.assertContains(response, job.csv_sha256)
        self.assertContains(response, "<svg")
        self.assertContains(response, "30 Oct 15:29")
        self.assertNotContains(response, "<script")
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])

    def test_source_badges_and_untrusted_labels(self):
        meta = metadata()
        meta.update(source_kind="USER_SUPPLIED", dataset_label="<script>alert(1)</script>")
        job, _ = self.load(meta=meta)
        response = self.client.get(f"/?dataset={job.pk}", HTTP_HOST="127.0.0.1")
        self.assertContains(response, "SOURCE NOT INDEPENDENTLY VERIFIED")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "SYNTHETIC DEMO — NOT ACTUAL PERFORMANCE")

    def test_loopback_host_and_peer_enforced(self):
        self.assertEqual(self.client.get("/", HTTP_HOST="evil.example").status_code, 400)
        self.assertEqual(self.client.get("/", HTTP_HOST="127.0.0.1", REMOTE_ADDR="192.168.1.2", HTTP_X_FORWARDED_FOR="127.0.0.1").status_code, 403)

    def test_write_methods_and_order_routes_absent(self):
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(self.client, method)("/", HTTP_HOST="127.0.0.1").status_code, 405)
        for path in ("/orders/", "/trade/", "/admin/", "/broker/", "/api/orders/"):
            self.assertEqual(self.client.get(path, HTTP_HOST="127.0.0.1").status_code, 404)

    def test_live_environment_variable_cannot_enable_orders(self):
        with patch.dict(os.environ, {"LIVE_TRADING_ENABLED": "true", "RESEARCH_MODE": "false"}):
            self.assertFalse(settings.LIVE_TRADING_ENABLED)
            self.assertTrue(settings.RESEARCH_MODE)

    def test_non_loopback_bind_rejected(self):
        for address in ("0.0.0.0:8000", "192.168.1.1:8000", "[::]:8000"):
            with self.assertRaises(CommandError):
                call_command("runserver", address, use_reloader=False)

    def test_bad_dataset_selector_is_safe(self):
        for query in ("999999", "-1", "abc", "1" * 1000):
            self.assertEqual(self.client.get(f"/?dataset={query}", HTTP_HOST="127.0.0.1").status_code, 200)
