"""Bounded read-only historical ingestion, using existing broker and QA services."""
import csv
import hashlib
import io
import json
import threading
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from brokers.errors import BrokerError
from brokers.services import BrokerReadOnlyClient
from engine.candles import FIELDS
from research.models import DataQualityIssue, HistoricalDownloadJob, InstrumentMasterSnapshot
from research.services import import_candle_bytes, resample_dataset

IST = ZoneInfo("Asia/Kolkata")
INGEST_VERSION = "kite-ingest.1"
MAX_PAYLOAD = 8 * 1024 * 1024
_download_lock = threading.Lock()


def canonical_bytes(value):
    def encode(item):
        if isinstance(item, (datetime, date)):
            return item.isoformat()
        if isinstance(item, Decimal):
            return str(item)
        raise TypeError("Unsupported broker value")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=encode, allow_nan=False).encode()


def archive_payload(raw):
    if len(raw) > MAX_PAYLOAD:
        raise BrokerError("INVALID_MARKET_DATA")
    root = Path(settings.RESEARCH_ARCHIVE_DIR)
    sha = hashlib.sha256(raw).hexdigest()
    target = root / f"kite-{sha}.json"
    try:
        root.mkdir(parents=True, exist_ok=True)
        if target.exists():
            with target.open("rb") as stream:
                if stream.read(MAX_PAYLOAD + 1) != raw:
                    raise BrokerError("INVALID_MARKET_DATA")
            return sha
        used = sum(p.stat().st_size for p in root.iterdir() if p.is_file())
        if used + len(raw) > settings.RESEARCH_ARCHIVE_BUDGET:
            raise BrokerError("ARCHIVE_LIMIT")
        with target.open("xb") as stream:
            stream.write(raw)
    except OSError:
        raise BrokerError("ARCHIVE_LIMIT") from None
    return sha


def read_master(master):
    path = Path(settings.RESEARCH_ARCHIVE_DIR) / f"kite-{master.sha256}.json"
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_PAYLOAD + 1)
        if len(raw) > MAX_PAYLOAD or hashlib.sha256(raw).hexdigest() != master.sha256:
            raise ValueError
        records = json.loads(raw)
        if not isinstance(records, list) or len(records) != master.instrument_count:
            raise ValueError
        return records
    except (OSError, ValueError, TypeError):
        raise BrokerError("INVALID_MARKET_DATA") from None


def eligible(record):
    return (isinstance(record, dict) and record.get("exchange") == "NSE"
            and record.get("segment") in {"NSE", "INDICES"}
            and record.get("instrument_type") in {"EQ", "INDEX"}
            and isinstance(record.get("tradingsymbol"), str)
            and 1 <= len(record["tradingsymbol"]) <= 64)


def sync_instruments(actor=None):
    records = BrokerReadOnlyClient(actor).instruments("NSE")
    if not isinstance(records, list) or not 1 <= len(records) <= 20000 or not any(eligible(r) for r in records):
        raise BrokerError("INVALID_MARKET_DATA")
    try:
        raw = canonical_bytes(records)
    except (ValueError, TypeError):
        raise BrokerError("INVALID_MARKET_DATA") from None
    sha = archive_payload(raw)
    master, created = InstrumentMasterSnapshot.objects.get_or_create(sha256=sha, defaults={
        "exchange": "NSE", "observed_at": timezone.now(), "instrument_count": len(records),
    })
    return master, created


def normal_sessions(start, end, now=None):
    now = now or timezone.now()
    today = now.astimezone(IST).date()
    if type(start) is not date or type(end) is not date or not timedelta(0) <= end - start <= timedelta(days=6) or end >= today or start < today - timedelta(days=90):
        raise BrokerError("INVALID_INPUT")
    sessions = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            sessions.append({"date": day.isoformat(), "open": "09:15", "close": "15:30"})
        day += timedelta(days=1)
    if not sessions:
        raise BrokerError("INVALID_INPUT")
    return sessions


def latest_weekday():
    day = timezone.now().astimezone(IST).date() - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def instrument_metadata(record, master):
    try:
        kind = "INDEX" if record["segment"] == "INDICES" or record["instrument_type"] == "INDEX" else "EQUITY"
        token = int(record["instrument_token"])
        lot = int(record["lot_size"])
        tick = Decimal(str(record["tick_size"]))
        if token <= 0 or not tick.is_finite() or (kind != "INDEX" and (tick <= 0 or lot <= 0)):
            raise ValueError
    except (KeyError, ValueError, TypeError, InvalidOperation, OverflowError):
        raise BrokerError("INVALID_MARKET_DATA") from None
    return {
        "exchange": "NSE", "symbol": record["tradingsymbol"], "kind": kind,
        "snapshot_date": master.observed_at.astimezone(IST).date().isoformat(),
        "token": str(token), "underlying": "", "expiry": None, "strike": None,
        "option_type": "", "lot_size": None if kind == "INDEX" else lot, "tick_size": None if kind == "INDEX" else str(tick),
    }


def candle_csv(records, metadata):
    if not isinstance(records, list) or len(records) > 3000:
        raise BrokerError("INVALID_MARKET_DATA")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(FIELDS)
    try:
        for item in records:
            timestamp = item["date"]
            if not isinstance(timestamp, datetime) or timezone.is_naive(timestamp):
                raise ValueError
            writer.writerow([timestamp.isoformat(), *[str(item[k]) for k in ("open", "high", "low", "close")],
                             "" if metadata["kind"] == "INDEX" else item["volume"]])
    except (KeyError, TypeError, ValueError):
        raise BrokerError("INVALID_MARKET_DATA") from None
    return output.getvalue().encode()


def fetch_history(master_id, symbol, start, end, actor=None):
    sessions = normal_sessions(start, end)
    master = InstrumentMasterSnapshot.objects.filter(pk=master_id, exchange="NSE").first()
    if not master:
        raise BrokerError("CATALOG_REQUIRED")
    matches = [r for r in read_master(master) if eligible(r) and r["tradingsymbol"] == symbol]
    if len(matches) != 1:
        raise BrokerError("INSTRUMENT_NOT_FOUND")
    metadata = instrument_metadata(matches[0], master)
    request_key = hashlib.sha256(canonical_bytes([master.sha256, symbol, start, end, INGEST_VERSION])).hexdigest()
    if not _download_lock.acquire(blocking=False):
        raise BrokerError("DOWNLOAD_BUSY")
    try:
        with transaction.atomic():
            job, created = HistoricalDownloadJob.objects.get_or_create(request_key=request_key, defaults={
                "master": master, "symbol": symbol, "start_date": start, "end_date": end, "initiated_by": actor,
            })
            if not created:
                if job.status in {"COMPLETE", "REJECTED"}:
                    return job, False
                if job.status == "RUNNING" and job.updated_at > timezone.now() - timedelta(minutes=10):
                    raise BrokerError("DOWNLOAD_BUSY")
                job.status, job.error_code = "RUNNING", ""
                job.save(update_fields=["status", "error_code", "updated_at"])
        try:
            from_date = datetime.combine(start, time(9, 15), IST)
            to_date = datetime.combine(end, time(15, 29), IST)
            records = BrokerReadOnlyClient(actor).historical_data(int(metadata["token"]), from_date, to_date, "minute")
            raw = canonical_bytes(records)
            response_sha = archive_payload(raw)
            normalized = candle_csv(records, metadata)
            manifest = {
                "format_version": 2, "dataset_label": f"NSE:{symbol} {start}–{end}", "source_kind": "ZERODHA",
                "source_reference": "https://api.kite.trade/instruments/historical/" + metadata["token"] + "/minute",
                "instrument": metadata, "sessions": sessions,
                "provenance": {"observed_at": timezone.now().isoformat(), "master_sha256": master.sha256,
                    "response_sha256": response_sha, "metadata_policy": "CURRENT_SNAPSHOT_NOT_HISTORICALLY_VERIFIED",
                    "session_policy": "NSE_NORMAL_WEEKDAYS_ASSUMED_V1", "ingest_version": INGEST_VERSION,
                    "response_representation": "SDK_DECODED_CANONICAL_JSON"},
            }
            with transaction.atomic():
                dataset, _ = import_candle_bytes(normalized, canonical_bytes(manifest), broker_download=True)
                job.dataset = dataset
                if dataset.status == "ACCEPTED":
                    snapshot = dataset.snapshot
                    if snapshot.master_id is None:
                        snapshot.master = master
                        snapshot.save(update_fields=["master"])
                    for interval in (5, 15):
                        resample_dataset(dataset.pk, interval)
                    job.status, job.error_code = "COMPLETE", ""
                else:
                    job.status = "REJECTED"
                    job.error_code = "NO_CANDLES" if not records else "DATA_REJECTED"
                job.save(update_fields=["dataset", "status", "error_code", "updated_at"])
            return job, True
        except (BrokerError, ValueError, TypeError, OSError, InvalidOperation) as exc:
            code = exc.code if isinstance(exc, BrokerError) else "INVALID_MARKET_DATA"
            HistoricalDownloadJob.objects.filter(pk=job.pk).update(status="FAILED", error_code=code, updated_at=timezone.now())
            raise BrokerError(code) from None
    finally:
        _download_lock.release()
