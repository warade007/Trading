import io
import json
import tempfile
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase, override_settings

from brokers.errors import BrokerError
from engine.candles import parse_manifest
from research.historical import canonical_bytes, fetch_history, normal_sessions, read_master, sync_instruments
from research.models import Candle, DataIngestJob, HistoricalDownloadJob, Instrument, InstrumentMasterSnapshot
from research.services import import_candle_bytes
from tests.helpers import rows

NOW = datetime(2026, 11, 1, 12, tzinfo=dt_timezone.utc)
DAY = date(2026, 10, 30)
HOST = {"HTTP_HOST": "127.0.0.1:8001"}
MASTER = [
    {"exchange": "NSE", "tradingsymbol": "NIFTY 50", "segment": "INDICES", "instrument_type": "EQ", "instrument_token": 111, "lot_size": 0, "tick_size": 0},
    {"exchange": "NSE", "tradingsymbol": "DEMO-EQ", "segment": "NSE", "instrument_type": "EQ", "instrument_token": 222, "lot_size": 1, "tick_size": 0.05},
]


def candles():
    return [{"date": datetime.fromisoformat(row["timestamp"].replace("2026-10-29", DAY.isoformat())),
             **{field: Decimal(row[field]) for field in ("open", "high", "low", "close")}, "volume": int(row["volume"])}
            for row in rows()[:375]]


class HistoricalTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings_override = override_settings(RESEARCH_ARCHIVE_DIR=self.root / "raw", AUTH_PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.clock = patch("research.historical.timezone.now", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.network = patch("requests.sessions.Session.request", side_effect=AssertionError("Broker tests must be mocked"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.factory = patch("research.historical.BrokerReadOnlyClient")
        self.broker = self.factory.start().return_value
        self.addCleanup(self.factory.stop)
        self.broker.instruments.return_value = deepcopy(MASTER)
        self.broker.historical_data.return_value = candles()
        self.master, _ = sync_instruments()
        self.admin = get_user_model().objects.create_superuser("historyadmin", password="synthetic-history-password")
        self.client.force_login(self.admin)

    def fetch(self, symbol="NIFTY 50", start=DAY, end=DAY):
        return fetch_history(self.master.pk, symbol, start, end, self.admin)

    def test_master_is_hashed_archived_and_repeat_sync_is_idempotent(self):
        same, created = sync_instruments()
        self.assertFalse(created)
        self.assertEqual(same.pk, self.master.pk)
        self.assertEqual(read_master(self.master), MASTER)
        self.assertEqual(InstrumentMasterSnapshot.objects.count(), 1)

    def test_index_history_persists_ohlc_without_invented_volume(self):
        job, created = self.fetch()
        self.assertTrue(created)
        self.assertEqual(job.status, "COMPLETE")
        dataset = job.dataset
        self.assertEqual(dataset.source_kind, "ZERODHA")
        self.assertEqual((dataset.imported_minutes, dataset.expected_minutes), (375, 375))
        self.assertEqual(dataset.candles.filter(interval=1).count(), 375)
        self.assertEqual(dataset.candles.filter(interval=5).count(), 75)
        self.assertEqual(dataset.candles.filter(interval=15).count(), 25)
        self.assertFalse(dataset.candles.exclude(volume=None).exists())
        self.assertIsNone(dataset.snapshot.tick_size)
        self.assertIsNone(dataset.snapshot.lot_size)
        self.assertEqual(dataset.snapshot.master_id, self.master.pk)
        self.assertEqual(dataset.snapshot.as_of, NOW.date())
        self.assertEqual(dataset.manifest["instrument"]["snapshot_date"], NOW.date().isoformat())
        self.assertEqual(dataset.issues.count(), 2)  # Explicit metadata/calendar limitations.
        self.assertEqual(dataset.candles.filter(interval=15).last().available_at.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).strftime('%H:%M'), '15:30')
        call = self.broker.historical_data.call_args
        self.assertEqual(call.args[0], 111)
        self.assertEqual(call.args[1].strftime('%H:%M'), '09:15')
        self.assertEqual(call.args[2].strftime('%H:%M'), '15:29')
        self.assertEqual(call.args[3], 'minute')

    def test_repeat_success_does_not_refetch_or_duplicate(self):
        first, _ = self.fetch()
        second, created = self.fetch()
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual((DataIngestJob.objects.count(), Candle.objects.count()), (1, 475))
        self.broker.historical_data.assert_called_once()

    def test_equity_volume_is_preserved(self):
        job, _ = self.fetch("DEMO-EQ")
        self.assertEqual(job.dataset.snapshot.instrument.kind, "EQUITY")
        self.assertEqual(job.dataset.candles.filter(interval=1).first().volume, 1000)
        self.assertEqual(job.dataset.candles.filter(interval=5).first().volume, sum(c["volume"] for c in candles()[:5]))

    def test_missing_minute_is_flagged_and_never_filled(self):
        self.broker.historical_data.return_value = candles()[1:]
        job, _ = self.fetch()
        self.assertEqual(job.status, "COMPLETE")
        self.assertEqual(job.dataset.imported_minutes, 374)
        self.assertTrue(job.dataset.issues.filter(code="MISSING_BARS").exists())
        self.assertEqual(job.dataset.candles.filter(interval=5).count(), 74)
        self.assertEqual(job.dataset.candles.filter(interval=15).count(), 24)

    def test_entire_missing_weekday_remains_a_coverage_gap(self):
        job, _ = self.fetch(start=DAY - timedelta(days=1))
        self.assertEqual((job.dataset.imported_minutes, job.dataset.expected_minutes), (375, 750))
        self.assertEqual(job.dataset.coverage, 50)
        self.assertTrue(job.dataset.issues.filter(code="MISSING_BARS", message__contains="375 missing").exists())

    def test_duplicate_or_outside_session_response_is_rejected_atomically(self):
        data = candles()
        self.broker.historical_data.return_value = data + [data[0]]
        job, _ = self.fetch()
        self.assertEqual(job.status, "REJECTED")
        self.assertEqual(job.dataset.status, "REJECTED")
        self.assertEqual(Candle.objects.count(), 0)
        self.assertEqual(Instrument.objects.count(), 0)

    def test_empty_response_retains_rejected_quality_report(self):
        self.broker.historical_data.return_value = []
        job, _ = self.fetch()
        self.assertEqual((job.status, job.error_code), ("REJECTED", "NO_CANDLES"))
        self.assertTrue(job.dataset.issues.filter(code="EMPTY_DATA").exists())
        self.assertEqual(Candle.objects.count(), 0)

    def test_naive_timestamp_fails_and_records_no_candles(self):
        data = candles()
        data[0]["date"] = data[0]["date"].replace(tzinfo=None)
        self.broker.historical_data.return_value = data
        with self.assertRaises(BrokerError):
            self.fetch()
        self.assertEqual(HistoricalDownloadJob.objects.get().status, "FAILED")
        self.assertEqual(Candle.objects.count(), 0)

    def test_broker_error_is_sanitized_and_retry_reuses_job(self):
        self.broker.historical_data.side_effect = BrokerError("SESSION_EXPIRED")
        with self.assertRaises(BrokerError):
            self.fetch()
        job = HistoricalDownloadJob.objects.get()
        self.assertEqual((job.status, job.error_code), ("FAILED", "SESSION_EXPIRED"))
        self.broker.historical_data.side_effect = None
        same, _ = self.fetch()
        self.assertEqual((same.pk, same.status), (job.pk, "COMPLETE"))

    def test_derived_storage_failure_rolls_back_dataset_and_marks_failed(self):
        with patch("research.historical.resample_dataset", side_effect=ValueError("storage")):
            with self.assertRaises(BrokerError):
                self.fetch()
        self.assertEqual((Candle.objects.count(), DataIngestJob.objects.count(), Instrument.objects.count()), (0, 0, 0))
        self.assertEqual(HistoricalDownloadJob.objects.get().status, "FAILED")

    def test_broker_provenance_cannot_be_imported_as_an_arbitrary_local_csv(self):
        job, _ = self.fetch()
        with self.assertRaisesRegex(ValueError, "broker download workflow"):
            import_candle_bytes(b"timestamp,open,high,low,close,volume\n", canonical_bytes(job.dataset.manifest))

    def test_broker_manifest_policy_and_hashes_are_strict(self):
        job, _ = self.fetch()
        for key, value in (("master_sha256", "not-a-hash"), ("metadata_policy", "VERIFIED"), ("observed_at", "2026-11-01T12:00:00")):
            manifest = deepcopy(job.dataset.manifest)
            manifest["provenance"][key] = value
            with self.assertRaises(ValueError):
                parse_manifest(canonical_bytes(manifest))

    def test_corrupt_master_cannot_be_used(self):
        path = self.root / "raw" / f"kite-{self.master.sha256}.json"
        path.write_bytes(b"corrupt")
        with self.assertRaises(BrokerError):
            self.fetch()
        self.broker.historical_data.assert_not_called()

    def test_archive_budget_prevents_ingestion(self):
        with override_settings(RESEARCH_ARCHIVE_BUDGET=1):
            with self.assertRaises(BrokerError) as caught:
                self.fetch()
        self.assertEqual(caught.exception.code, "ARCHIVE_LIMIT")
        self.assertEqual(Candle.objects.count(), 0)

    def test_missing_instrument_or_master_does_not_call_history(self):
        for master, symbol in ((999, "NIFTY 50"), (self.master.pk, "NONEXISTENT")):
            with self.assertRaises(BrokerError):
                fetch_history(master, symbol, DAY, DAY)
        self.broker.historical_data.assert_not_called()

    def test_view_is_authenticated_csrf_protected_and_get_is_offline(self):
        self.client.logout()
        self.assertRedirects(self.client.get('/historical/', **HOST), '/accounts/login/', fetch_redirect_response=False)
        self.client.force_login(self.admin)
        self.broker.reset_mock()
        response = self.client.get('/historical/', **HOST)
        self.assertContains(response, 'NIFTY 50')
        self.broker.historical_data.assert_not_called()
        self.broker.instruments.assert_not_called()
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        for url in ('/historical/sync/', '/historical/fetch/'):
            self.assertEqual(browser.post(url, {}, **HOST).status_code, 403)

    def test_view_download_and_real_dataset_label(self):
        response = self.client.post('/historical/fetch/', {'master_id': self.master.pk, 'symbol': 'NIFTY 50', 'start_date': DAY, 'end_date': DAY}, **HOST)
        self.assertRedirects(response, '/historical/', fetch_redirect_response=False)
        job = HistoricalDownloadJob.objects.get()
        response = self.client.get('/?dataset='+str(job.dataset_id), **HOST)
        self.assertContains(response, 'ZERODHA HISTORICAL DATA — NOT STRATEGY PERFORMANCE')
        self.assertNotContains(response, 'SYNTHETIC DEMO — NOT ACTUAL PERFORMANCE')
        self.assertContains(response, 'Unavailable')

    def test_command_uses_only_read_only_instrument_and_history_calls(self):
        output = io.StringIO()
        call_command('fetch_candles', symbol='NIFTY 50', start=DAY, end=DAY, stdout=output)
        self.assertIn('COMPLETE', output.getvalue())
        self.assertEqual({call[0] for call in self.broker.method_calls}, {'instruments', 'historical_data'})


class HistoricalSessionTests(SimpleTestCase):
    def test_future_current_old_and_oversized_ranges_rejected(self):
        for start, end in ((date(2026,11,1),date(2026,11,1)), (DAY,DAY-timedelta(days=1)),
                           (DAY-timedelta(days=7),DAY), (DAY-timedelta(days=100),DAY-timedelta(days=100)),
                           (date(2026,10,31),date(2026,10,31))):
            with self.subTest(start=start,end=end), self.assertRaises(BrokerError):
                normal_sessions(start,end,NOW)

    def test_weekends_are_explicitly_outside_assumed_normal_sessions(self):
        sessions = normal_sessions(date(2026,10,29),date(2026,10,31),NOW)
        self.assertEqual([s['date'] for s in sessions], ['2026-10-29','2026-10-30'])
