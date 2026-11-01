import json
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from unittest import TestCase

from engine.candles import IST, MAX_BYTES, parse_manifest, resample, validate_csv
from tests.helpers import RAW, encode_rows, metadata, rows


class ValidationTests(TestCase):
    def setUp(self):
        self.manifest = parse_manifest(json.dumps(metadata()).encode())

    def validate(self, items):
        return validate_csv(encode_rows(items), self.manifest)

    def test_full_fixture_and_timezone_normalization(self):
        result = validate_csv(RAW, self.manifest)
        self.assertTrue(result.valid)
        self.assertEqual(result.issues, [])
        self.assertEqual((len(result.bars), result.expected), (750, 750))
        self.assertEqual(result.bars[0].timestamp.isoformat(), "2026-10-29T03:45:00+00:00")

    def test_invalid_prices_volume_and_timestamps(self):
        cases = [
            ("open", "-1"), ("open", "0"), ("open", "NaN"), ("open", "Infinity"),
            ("open", "1E999999"), ("open", "100.00001"), ("open", "100.01"),
            ("high", "1"), ("low", "999"), ("volume", "-1"), ("volume", "1.1"),
            ("volume", "NaN"), ("volume", "1000000000001"), ("volume", ""),
            ("timestamp", "2026-10-29T09:15:00"),
            ("timestamp", "2026-10-29T09:15:01+05:30"),
            ("timestamp", "2026-10-29T09:14:00+05:30"),
            ("timestamp", "2026-10-29T15:30:00+05:30"),
        ]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                data = rows()
                data[0][key] = value
                result = self.validate(data)
                self.assertFalse(result.valid)
                self.assertEqual(result.issues[0].row, 2)

    def test_duplicate_equivalent_offsets_rejected(self):
        data = rows()
        duplicate = dict(data[0], timestamp="2026-10-29T03:45:00+00:00")
        data.insert(1, duplicate)
        self.assertFalse(self.validate(data).valid)

    def test_out_of_order_rejected(self):
        data = rows()
        data[0], data[1] = data[1], data[0]
        self.assertFalse(self.validate(data).valid)

    def test_missing_first_middle_last_minutes(self):
        data = rows()
        result = self.validate([r for i, r in enumerate(data) if i not in (0, 32, 749)])
        self.assertTrue(result.valid)
        self.assertEqual(result.expected, 750)
        self.assertEqual(len(result.bars), 747)
        self.assertEqual(sum(i.code == "MISSING_BARS" for i in result.issues), 3)

    def test_entire_declared_session_missing(self):
        result = self.validate(rows()[:375])
        self.assertTrue(result.valid)
        self.assertEqual(result.expected, 750)
        self.assertIn("375 missing minute(s)", result.issues[0].message)

    def test_empty_wrong_columns_and_encoding(self):
        for raw in (b"", b"timestamp,open\n", b"\xff", RAW.split(b"\n")[0] + b"\n", RAW.replace(b"volume", b"Volume", 1)):
            with self.subTest(raw=raw[:30]):
                self.assertFalse(validate_csv(raw, self.manifest).valid)

    def test_extra_and_missing_columns(self):
        lines = RAW.splitlines()
        for first in (lines[1] + b",extra", lines[1].rsplit(b",", 1)[0]):
            self.assertFalse(validate_csv(b"\n".join([lines[0], first, *lines[2:]]), self.manifest).valid)

    def test_file_size_limit(self):
        result = validate_csv(b" " * (MAX_BYTES + 1), self.manifest)
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "FILE_LIMIT")

    def test_zero_volume_is_observed_not_missing(self):
        data = rows()
        data[0]["volume"] = "0"
        result = self.validate(data)
        self.assertTrue(result.valid)
        self.assertEqual(result.bars[0].volume, 0)
        self.assertEqual(result.issues, [])

    def test_index_volume_must_be_unknown(self):
        meta = metadata()
        meta["instrument"]["kind"] = "INDEX"
        manifest = parse_manifest(json.dumps(meta).encode())
        self.assertFalse(validate_csv(RAW, manifest).valid)
        data = rows()
        for row in data:
            row["volume"] = ""
        result = validate_csv(encode_rows(data), manifest)
        self.assertTrue(result.valid)
        derived, _ = resample(result.bars, manifest.sessions, 15)
        self.assertTrue(all(b.volume is None for b in derived))

    def test_price_outlier_flagged_not_changed(self):
        data = rows()
        data[0].update(open="200", high="201", low="199", close="200")
        result = self.validate(data)
        self.assertTrue(result.valid)
        self.assertTrue(any(i.code == "PRICE_JUMP" for i in result.issues))
        self.assertEqual(result.bars[0].close, Decimal(200))


class ManifestTests(TestCase):
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            parse_manifest(b'{"format_version":1,"format_version":1}')

    def test_invalid_manifest_contracts_and_sessions(self):
        mutations = [
            lambda m: m.update(source_kind="BROKER_VERIFIED"),
            lambda m: m.update(format_version=2),
            lambda m: m.update(sessions=[]),
            lambda m: m["sessions"].append(m["sessions"][0]),
            lambda m: m["sessions"][0].update(close="09:00"),
            lambda m: m["sessions"][0].update(open="09:15:01"),
            lambda m: m["sessions"][0].update(open="09:15+05:30"),
            lambda m: m["instrument"].update(snapshot_date="2026-10-30"),
            lambda m: m["instrument"].update(lot_size=0),
            lambda m: m["instrument"].update(tick_size="0"),
            lambda m: m["instrument"].update(kind="OPTION"),
            lambda m: m["instrument"].update(strike="100"),
            lambda m: m["instrument"].update(option_type=None),
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                meta = metadata()
                mutation(meta)
                with self.assertRaises(ValueError):
                    parse_manifest(json.dumps(meta).encode())

    def test_option_identity_and_expiry(self):
        meta = metadata()
        meta["instrument"].update(kind="OPTION", underlying="SYNTH-INDEX", expiry="2026-10-30", strike="100", option_type="CE")
        self.assertEqual(parse_manifest(json.dumps(meta).encode()).metadata["option_type"], "CE")
        meta["instrument"]["expiry"] = "2026-10-29"
        with self.assertRaises(ValueError):
            parse_manifest(json.dumps(meta).encode())

    def test_explicit_special_session_supported_no_inferred_calendar(self):
        meta = metadata()
        meta["sessions"] = [{"date": "2026-10-31", "open": "18:00", "close": "19:00"}]
        manifest = parse_manifest(json.dumps(meta).encode())
        self.assertEqual(manifest.sessions[0].minutes, 60)


class ResamplingTests(TestCase):
    def setUp(self):
        self.manifest = parse_manifest(json.dumps(metadata()).encode())
        self.bars = validate_csv(RAW, self.manifest).bars

    def test_exact_ohlcv_and_first_anchor(self):
        for interval, count in ((5, 150), (15, 50)):
            with self.subTest(interval=interval):
                derived, issues = resample(self.bars, self.manifest.sessions, interval)
                self.assertEqual((len(derived), issues), (count, []))
                source = self.bars[:interval]
                first = derived[0]
                self.assertEqual(first.timestamp.astimezone(IST).strftime("%H:%M"), "09:15")
                self.assertEqual((first.open, first.high, first.low, first.close, first.volume),
                                 (source[0].open, max(b.high for b in source), min(b.low for b in source), source[-1].close, sum(b.volume for b in source)))
                self.assertEqual(first.available_at, first.timestamp + timedelta(minutes=interval))
                self.assertEqual(resample(self.bars, self.manifest.sessions, interval), (derived, issues))

    def test_close_and_no_cross_day_buckets(self):
        for interval in (5, 15):
            derived, _ = resample(self.bars, self.manifest.sessions, interval)
            for bar in derived:
                self.assertEqual(bar.timestamp.astimezone(IST).date(), bar.available_at.astimezone(IST).date())
                self.assertLessEqual(bar.available_at.astimezone(IST).strftime("%H:%M"), "15:30")
            self.assertEqual(derived[-1].available_at.astimezone(IST).strftime("%H:%M"), "15:30")
            self.assertEqual(derived[-1].timestamp.astimezone(IST).strftime("%H:%M"), "15:25" if interval == 5 else "15:15")

    def test_missing_minute_skips_affected_bucket(self):
        bars = self.bars[:7] + self.bars[8:]
        for interval, count in ((5, 149), (15, 49)):
            derived, issues = resample(bars, self.manifest.sessions, interval)
            self.assertEqual((len(derived), len(issues)), (count, 1))
            self.assertEqual(issues[0].code, "INCOMPLETE_BUCKET")

    def test_partial_session_tail_never_emitted(self):
        session = replace(self.manifest.sessions[0], end=self.manifest.sessions[0].start + timedelta(minutes=17))
        derived, issues = resample(self.bars[:17], (session,), 15)
        self.assertEqual((len(derived), len(issues)), (1, 1))

    def test_invalid_inputs_rejected(self):
        for bars, interval in ((self.bars, 3), (self.bars[::-1], 5), ([self.bars[0]] * 2, 5),
                               ([replace(self.bars[0], interval=5)], 5),
                               ([replace(self.bars[0], timestamp=self.bars[0].timestamp - timedelta(minutes=1))], 5)):
            with self.subTest(interval=interval, count=len(bars)):
                with self.assertRaises(ValueError):
                    resample(bars, self.manifest.sessions, interval)
