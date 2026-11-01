"""Atomic, idempotent persistence; calculations live in engine/."""
import hashlib
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction

from engine import ENGINE_VERSION
from engine.candles import MAX_BYTES, Issue, parse_manifest, resample, validate_csv
from research.models import Candle, DataIngestJob, DataQualityIssue, Instrument, InstrumentSnapshot


def _read_bounded(path, limit):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError(f"Input exceeds {limit} bytes.")
    return raw


def _store_issues(job, issues):
    DataQualityIssue.objects.bulk_create(
        [DataQualityIssue(dataset=job, **asdict(issue)) for issue in issues], batch_size=250
    )


def _store_bars(job, bars):
    Candle.objects.bulk_create([
        Candle(dataset=job, available_at=bar.available_at, **asdict(bar)) for bar in bars
    ], batch_size=250)


def _archive(raw, csv_hash, canonical_manifest, manifest_hash):
    """Content-addressed raw inputs. Never overwrite or clean up automatically."""
    root = Path(settings.RESEARCH_ARCHIVE_DIR)
    root.mkdir(parents=True, exist_ok=True)
    entries = [(root / f"{csv_hash}.csv", raw), (root / f"{manifest_hash}.json", canonical_manifest)]
    used = sum(path.stat().st_size for path in root.iterdir() if path.is_file())
    required = sum(len(content) for path, content in entries if not path.exists())
    if used + required > settings.RESEARCH_ARCHIVE_BUDGET:
        raise ValueError("Local raw archive exceeds 256 MiB budget; review retained data manually.")
    for path, content in entries:
        try:
            with path.open("xb") as stream:
                stream.write(content)
        except FileExistsError:
            if _read_bounded(path, MAX_BYTES) != content:
                raise ValueError("Existing content-addressed archive is corrupt; import stopped.")


def import_dataset(csv_path, manifest_path):
    raw = _read_bounded(csv_path, MAX_BYTES)
    manifest_raw = _read_bounded(manifest_path, 65536)
    return import_candle_bytes(raw, manifest_raw)


def import_candle_bytes(raw, manifest_raw, *, broker_download=False):
    if len(raw) > MAX_BYTES or len(manifest_raw) > 65536:
        raise ValueError("Input exceeds the import budget.")
    # Validate manifest before any writes. Invalid manifests cannot define provenance.
    try:
        manifest = parse_manifest(manifest_raw)
    except (TypeError, KeyError, InvalidOperation, UnicodeError, OverflowError) as exc:
        raise ValueError(f"Invalid manifest: {exc}") from exc
    if manifest.raw["source_kind"] == "ZERODHA" and not broker_download:
        raise ValueError("ZERODHA provenance can only be created by the broker download workflow.")
    csv_hash = hashlib.sha256(raw).hexdigest()
    canonical_manifest = json.dumps(manifest.raw, sort_keys=True, separators=(",", ":")).encode()
    manifest_hash = hashlib.sha256(canonical_manifest).hexdigest()
    fingerprint = hashlib.sha256(f"{csv_hash}:{manifest_hash}:{ENGINE_VERSION}".encode()).hexdigest()
    _archive(raw, csv_hash, canonical_manifest, manifest_hash)
    existing = DataIngestJob.objects.filter(fingerprint=fingerprint).first()
    if existing:
        return existing, False
    result = validate_csv(raw, manifest)
    meta = manifest.raw
    with transaction.atomic():
        job = DataIngestJob.objects.create(
            fingerprint=fingerprint, csv_sha256=csv_hash, manifest_sha256=manifest_hash,
            manifest=meta, label=meta["dataset_label"], source_kind=meta["source_kind"],
            source_reference=meta["source_reference"], engine_version=ENGINE_VERSION,
            status="ACCEPTED" if result.valid else "REJECTED", expected_minutes=result.expected,
        )
        if result.valid:
            item = manifest.metadata
            # A savepoint ensures snapshot conflicts don't leave partial instruments.
            try:
                with transaction.atomic():
                    instrument, _ = Instrument.objects.get_or_create(
                        exchange=item["exchange"], symbol=item["symbol"], source_kind=meta["source_kind"],
                        defaults={"kind": item["kind"]},
                    )
                    if instrument.kind != item["kind"]:
                        raise ValueError("Instrument kind conflicts with existing identity.")
                    values = {
                        "token": item["token"], "underlying": item["underlying"],
                        "expiry": date.fromisoformat(item["expiry"]) if item["expiry"] else None,
                        "strike": Decimal(item["strike"]) if item["strike"] else None,
                        "option_type": item["option_type"], "lot_size": item["lot_size"],
                        "tick_size": Decimal(item["tick_size"]) if item["tick_size"] is not None else None,
                    }
                    snapshot, _ = InstrumentSnapshot.objects.get_or_create(
                        instrument=instrument, as_of=date.fromisoformat(item["snapshot_date"]), defaults=values
                    )
                    if any(getattr(snapshot, key) != value for key, value in values.items()):
                        raise ValueError("Dated snapshot conflicts with immutable imported metadata.")
                    job.snapshot = snapshot
            except ValueError as exc:
                job.status = "REJECTED"
                result.issues.append(Issue("SNAPSHOT_CONFLICT", str(exc)))
        if job.status == "ACCEPTED":
            _store_bars(job, result.bars)
            job.imported_minutes = len(result.bars)
        job.save()
        _store_issues(job, result.issues)
    return job, True


def resample_dataset(job_id, interval):
    with transaction.atomic():
        job = DataIngestJob.objects.select_for_update().get(pk=job_id)
        if job.status != "ACCEPTED":
            raise ValueError("Only accepted datasets may be resampled.")
        from engine.candles import Bar

        bars = [Bar(c.timestamp, c.open, c.high, c.low, c.close, c.volume)
                for c in job.candles.filter(interval=1)]
        manifest = parse_manifest(json.dumps(job.manifest).encode())
        outputs, issues = resample(bars, manifest.sessions, interval)
        existing = list(job.candles.filter(interval=interval))
        if existing:
            # Do not overwrite derived history or silently accept corruption.
            actual = [Bar(c.timestamp, c.open, c.high, c.low, c.close, c.volume, c.interval) for c in existing]
            if actual != outputs or any(c.available_at != b.available_at for c, b in zip(existing, outputs)):
                raise ValueError("Existing derived bars differ; create a new versioned dataset.")
            return len(existing), len(issues), False
        _store_bars(job, outputs)
        for issue in issues:
            DataQualityIssue.objects.get_or_create(dataset=job, **asdict(issue))
        return len(outputs), len(issues), True
