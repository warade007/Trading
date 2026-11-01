import csv
import io
import json
from copy import deepcopy
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
RAW = (FIXTURES / "synthetic.csv").read_bytes()
MANIFEST = json.loads((FIXTURES / "synthetic.manifest.json").read_text(encoding="utf-8"))


def metadata():
    return deepcopy(MANIFEST)


def rows():
    return list(csv.DictReader(io.StringIO(RAW.decode())))


def encode_rows(items):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=["timestamp", "open", "high", "low", "close", "volume"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(items)
    return stream.getvalue().encode()
