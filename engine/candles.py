"""Framework-independent, bounded CSV validation and completed-bar aggregation.

Timestamps denote bar OPEN; available_at denotes bar CLOSE. Session dates and
hours are explicit inputs, never inferred as a historical exchange calendar.
"""
import csv
import io
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc
MINUTE = timedelta(minutes=1)
MAX_BYTES = 4 * 1024 * 1024
MAX_ROWS = 20_000
PRICE_MAX = Decimal("9999999999.9999")
FIELDS = ["timestamp", "open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    severity: str = "ERROR"
    row: int | None = None


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    interval: int = 1

    @property
    def available_at(self):
        return self.timestamp + self.interval * MINUTE


@dataclass(frozen=True)
class Session:
    start: datetime
    end: datetime

    @property
    def minutes(self):
        return int((self.end - self.start) / MINUTE)


@dataclass(frozen=True)
class Manifest:
    metadata: dict
    sessions: tuple[Session, ...]
    raw: dict


@dataclass
class QualityResult:
    bars: list[Bar]
    issues: list[Issue]
    expected: int

    @property
    def valid(self):
        return not any(issue.severity == "ERROR" for issue in self.issues)


def price(value):
    result = Decimal(value)
    if (not result.is_finite() or not 0 < result <= PRICE_MAX
            or result != result.quantize(Decimal("0.0001"))):
        raise ValueError("Prices must be positive, finite and at most 4 decimal places.")
    return result


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key}")
        result[key] = value
    return result


def parse_manifest(raw: bytes) -> Manifest:
    if len(raw) > 65536:
        raise ValueError("Manifest exceeds 64 KiB.")
    data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object)
    required = {
        "format_version", "dataset_label", "source_kind", "source_reference",
        "instrument", "sessions",
    }
    broker = isinstance(data, dict) and data.get("format_version") == 2
    if broker:
        required.add("provenance")
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Manifest requires the documented exact top-level schema.")
    if type(data["format_version"]) is not int or data["format_version"] not in (1, 2):
        raise ValueError("Only manifest format_version 1 or 2 is supported.")
    if broker:
        provenance = data["provenance"]
        if data["source_kind"] != "ZERODHA" or not isinstance(provenance, dict) or set(provenance) != {
            "observed_at", "master_sha256", "response_sha256", "metadata_policy", "session_policy", "ingest_version", "response_representation",
        }:
            raise ValueError("Invalid broker provenance schema.")
        observed = datetime.fromisoformat(provenance["observed_at"])
        if observed.tzinfo is None:
            raise ValueError("Broker observation timestamp must be timezone aware.")
        for key in ("master_sha256", "response_sha256"):
            value = provenance[key]
            if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Invalid broker content hash.")
        if (provenance["metadata_policy"] != "CURRENT_SNAPSHOT_NOT_HISTORICALLY_VERIFIED"
                or provenance["session_policy"] != "NSE_NORMAL_WEEKDAYS_ASSUMED_V1"
                or provenance["ingest_version"] != "kite-ingest.1"
                or provenance["response_representation"] != "SDK_DECODED_CANONICAL_JSON"):
            raise ValueError("Unsupported broker metadata/session policy.")
    elif data["source_kind"] not in ("SYNTHETIC", "USER_SUPPLIED"):
        raise ValueError("Source must be SYNTHETIC or USER_SUPPLIED (never verified as broker data).")
    for key in ("dataset_label", "source_reference"):
        if not isinstance(data[key], str) or not 1 <= len(data[key].strip()) <= 200:
            raise ValueError(f"{key} must contain 1-200 characters.")
    item = data["instrument"]
    if not isinstance(item, dict) or set(item) != {
        "exchange", "symbol", "kind", "snapshot_date", "token", "underlying",
        "expiry", "strike", "option_type", "lot_size", "tick_size",
    }:
        raise ValueError("Instrument requires the documented exact snapshot schema.")
    for key, limit in (("exchange", 16), ("symbol", 64), ("token", 64), ("underlying", 64)):
        if not isinstance(item[key], str) or len(item[key]) > limit:
            raise ValueError(f"Invalid instrument {key}.")
    if not item["exchange"].strip() or not item["symbol"].strip():
        raise ValueError("Exchange and symbol cannot be blank.")
    if item["kind"] not in ("EQUITY", "ETF", "INDEX", "FUTURE", "OPTION"):
        raise ValueError("Unknown instrument kind.")
    if not isinstance(item["option_type"], str) or len(item["option_type"]) > 2:
        raise ValueError("option_type must be a string: CE, PE or empty.")
    snapshot_date = date.fromisoformat(item["snapshot_date"])
    unknown_tick = broker and item["kind"] == "INDEX" and item["tick_size"] is None
    if not unknown_tick and not isinstance(item["tick_size"], str):
        raise ValueError("tick_size must be a decimal string.")
    if not unknown_tick:
        price(item["tick_size"])
    unknown_lot = broker and item["kind"] == "INDEX" and item["lot_size"] is None
    if not unknown_lot and (type(item["lot_size"]) is not int or not 1 <= item["lot_size"] <= 2_147_483_647):
        raise ValueError("lot_size must be a positive integer.")
    if item["expiry"] is not None and not isinstance(item["expiry"], str):
        raise ValueError("expiry must be an ISO date string or null.")
    expiry = date.fromisoformat(item["expiry"]) if item["expiry"] is not None else None
    if item["kind"] in ("OPTION", "FUTURE") and (not expiry or not item["underlying"] or not item["token"]):
        raise ValueError("Derivative snapshots require expiry, underlying and exact token.")
    if item["kind"] == "OPTION":
        if item["option_type"] not in ("CE", "PE") or not isinstance(item["strike"], str):
            raise ValueError("Options require strike and CE/PE.")
        price(item["strike"])
    elif item["strike"] is not None or item["option_type"]:
        raise ValueError("Only options may have strike and option_type.")
    if item["kind"] not in ("OPTION", "FUTURE") and expiry:
        raise ValueError("Only derivatives may have expiry.")
    if not isinstance(data["sessions"], list) or not 1 <= len(data["sessions"]) <= 31:
        raise ValueError("Declare 1-31 explicit session dates per import.")
    sessions = []
    for entry in data["sessions"]:
        if not isinstance(entry, dict) or set(entry) != {"date", "open", "close"}:
            raise ValueError("Each session requires date, open and close.")
        day = date.fromisoformat(entry["date"])
        opening, closing = time.fromisoformat(entry["open"]), time.fromisoformat(entry["close"])
        if any(t.tzinfo or t.second or t.microsecond for t in (opening, closing)) or opening >= closing:
            raise ValueError("Session times must be minute-aligned local times within one date.")
        if (not broker and day < snapshot_date) or (expiry and day > expiry):
            raise ValueError("Session outside instrument snapshot/expiry validity.")
        session = Session(datetime.combine(day, opening, IST).astimezone(UTC),
                          datetime.combine(day, closing, IST).astimezone(UTC))
        if any(s.start.astimezone(IST).date() == day for s in sessions):
            raise ValueError("Duplicate session date.")
        sessions.append(session)
    sessions.sort(key=lambda s: s.start)
    if sum(s.minutes for s in sessions) > MAX_ROWS:
        raise ValueError("Declared sessions exceed the 20,000-minute import budget.")
    return Manifest(item, tuple(sessions), data)


def validate_csv(raw: bytes, manifest: Manifest) -> QualityResult:
    expected = {s.start + i * MINUTE for s in manifest.sessions for i in range(s.minutes)}
    result = QualityResult([], [], len(expected))
    if manifest.raw["source_kind"] == "ZERODHA":
        result.issues.extend([
            Issue("CURRENT_METADATA", "Instrument metadata was observed at download time; historical tick/lot validity is not verified. Current tick alignment is not imposed on historical prices.", "WARNING"),
            Issue("ASSUMED_CALENDAR", "Normal NSE weekday sessions assumed; holidays and special sessions are not certified. Missing weekdays remain gaps; weekends are not assessed.", "WARNING"),
        ])
    if len(raw) > MAX_BYTES:
        result.issues.append(Issue("FILE_LIMIT", "CSV exceeds 4 MiB."))
        return result
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), strict=True)
        if reader.fieldnames != FIELDS:
            raise ValueError("CSV columns must be exactly: " + ",".join(FIELDS))
        seen = set()
        previous = None
        for row_number, row in enumerate(reader, 2):
            if row_number > MAX_ROWS + 1:
                result.issues.append(Issue("ROW_LIMIT", "CSV exceeds 20,000 rows."))
                break
            try:
                if None in row or any(value is None for value in row.values()):
                    raise ValueError("Wrong number of CSV fields.")
                timestamp = datetime.fromisoformat(row["timestamp"])
                if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                    raise ValueError("Timestamp requires explicit UTC or IST offset.")
                timestamp = timestamp.astimezone(UTC)
                if timestamp not in expected:
                    raise ValueError("Timestamp is unaligned or outside declared sessions.")
                if timestamp in seen:
                    raise ValueError("Duplicate timestamp (including equivalent timezone offsets).")
                if previous and timestamp <= previous.timestamp:
                    raise ValueError("CSV must be strictly chronological.")
                prices = [price(row[key]) for key in FIELDS[1:5]]
                opening, high, low, close = prices
                if not low <= min(opening, close) <= max(opening, close) <= high:
                    raise ValueError("Invalid OHLC high/low relationship.")
                tick = price(manifest.metadata["tick_size"]) if manifest.metadata["tick_size"] is not None else None
                if manifest.raw["source_kind"] != "ZERODHA" and tick and any(p % tick for p in prices):
                    raise ValueError("Price not aligned to snapshot tick_size.")
                if manifest.metadata["kind"] == "INDEX":
                    if row["volume"] != "":
                        raise ValueError("Index traded volume must be blank, never invented.")
                    volume = None
                else:
                    if not row["volume"].isascii() or not row["volume"].isdecimal():
                        raise ValueError("Volume must be a nonnegative integer.")
                    volume = int(row["volume"])
                    if volume > 1_000_000_000_000:
                        raise ValueError("Volume exceeds M1 numeric budget.")
                bar = Bar(timestamp, opening, high, low, close, volume)
                if previous and abs(close / previous.close - 1) > Decimal("0.20"):
                    result.issues.append(Issue("PRICE_JUMP", "Close changed over 20%; review, no automatic correction.", "WARNING", row_number))
                result.bars.append(bar)
                seen.add(timestamp)
                previous = bar
            except (ValueError, InvalidOperation, OverflowError) as exc:
                result.issues.append(Issue("INVALID_ROW", str(exc), row=row_number))
        missing = deque(sorted(expected - seen))
        # One issue per contiguous gap: bounded, exact endpoints and minute count.
        while missing:
            start = end = missing.popleft()
            count = 1
            while missing and missing[0] == end + MINUTE:
                end = missing.popleft()
                count += 1
            result.issues.append(Issue("MISSING_BARS", f"{count} missing minute(s): {start.isoformat()} through {end.isoformat()}", "WARNING"))
        if not result.bars:
            result.issues.append(Issue("EMPTY_DATA", "No valid candles found."))
    except (ValueError, UnicodeError, csv.Error) as exc:
        result.issues.append(Issue("INVALID_CSV", str(exc)))
    return result


def resample(bars: list[Bar], sessions: tuple[Session, ...], interval: int):
    """Emit only complete buckets, anchored at each declared session open.

    Never cross a session boundary, bridge a gap or fabricate a trailing bar.
    The caller must use available_at before exposing a bar to a future strategy.
    """
    if interval not in (5, 15):
        raise ValueError("Only 5- and 15-minute outputs are supported.")
    times = [bar.timestamp for bar in bars]
    if times != sorted(set(times)) or any(b.interval != 1 for b in bars):
        raise ValueError("Resampling requires unique chronological 1-minute bars.")
    groups = defaultdict(list)
    for bar in bars:
        session = next((s for s in sessions if s.start <= bar.timestamp < s.end), None)
        if session is None or (bar.timestamp - session.start) % MINUTE:
            raise ValueError("Bar is outside or unaligned with session.")
        start = session.start + int((bar.timestamp - session.start) / MINUTE // interval) * interval * MINUTE
        groups[start].append(bar)
    outputs, issues = [], []
    for session in sessions:
        for offset in range(0, session.minutes, interval):
            start = session.start + offset * MINUTE
            bucket = groups[start]
            if len(bucket) != interval or start + interval * MINUTE > session.end:
                issues.append(Issue("INCOMPLETE_BUCKET", f"Skipped {interval}m bucket at {start.isoformat()}: {len(bucket)}/{interval} minutes.", "WARNING"))
                continue
            volumes = [bar.volume for bar in bucket]
            if any(v is None for v in volumes) and not all(v is None for v in volumes):
                raise ValueError("Cannot mix missing and observed volume in a bucket.")
            outputs.append(Bar(start, bucket[0].open, max(b.high for b in bucket),
                               min(b.low for b in bucket), bucket[-1].close,
                               None if volumes[0] is None else sum(volumes), interval))
    return outputs, issues
