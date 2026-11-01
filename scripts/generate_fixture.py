"""Reproduce the bundled artificial dataset; no randomness, network or market data."""
import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def generate():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    days = ["2026-10-29", "2026-10-30"]
    manifest = {
        "format_version": 1,
        "dataset_label": "SYNTHETIC-DEMO-EQUITY-v1",
        "source_kind": "SYNTHETIC",
        "source_reference": "scripts/generate_fixture.py v1; deterministic integer formula; no random seed",
        "instrument": {
            "exchange": "DEMO_NSE", "symbol": "SYNTH-EQ", "kind": "EQUITY",
            "snapshot_date": days[0], "token": "synthetic-equity-v1", "underlying": "",
            "expiry": None, "strike": None, "option_type": "", "lot_size": 1, "tick_size": "0.05",
        },
        "sessions": [{"date": day, "open": "09:15", "close": "15:30"} for day in days],
    }
    (FIXTURES / "synthetic.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (FIXTURES / "synthetic.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for day_index, day in enumerate(days):
            start = datetime.fromisoformat(day + "T09:15:00+05:30")
            for minute in range(375):
                opening = Decimal("100") + Decimal(day_index) + Decimal(minute % 60) * Decimal("0.05")
                close = opening + Decimal((minute % 5) - 2) * Decimal("0.05")
                writer.writerow([(start + timedelta(minutes=minute)).isoformat(),
                                 opening, max(opening, close) + Decimal("0.10"),
                                 min(opening, close) - Decimal("0.10"), close,
                                 1000 + (minute * 37) % 500])


if __name__ == "__main__":
    generate()
    print("Reproduced SYNTHETIC v1 fixtures: 750 minute bars; no actual market data.")
