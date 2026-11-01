from datetime import date
from django.core.management.base import BaseCommand, CommandError
from brokers.errors import BrokerError
from research.historical import fetch_history
from research.models import InstrumentMasterSnapshot


class Command(BaseCommand):
    help = "Fetch a bounded completed NSE 1m period and derive 5m/15m research bars."

    def add_arguments(self, parser):
        parser.add_argument("--symbol", default="NIFTY 50")
        parser.add_argument("--start", required=True, type=date.fromisoformat)
        parser.add_argument("--end", required=True, type=date.fromisoformat)
        parser.add_argument("--master", type=int)

    def handle(self, *args, **options):
        master = InstrumentMasterSnapshot.objects.order_by("-observed_at", "-id").first()
        master_id = options["master"] or (master.pk if master else None)
        try:
            job, created = fetch_history(master_id, options["symbol"], options["start"], options["end"])
        except BrokerError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(f"Download {job.pk}: {job.status}; {'requested' if created else 'unchanged'}; dataset {job.dataset_id}.")
        if job.dataset:
            self.stdout.write(f"{job.dataset.imported_minutes}/{job.dataset.expected_minutes} 1m candles; issues {job.dataset.issues.count()}; dashboard http://127.0.0.1:8001/?dataset={job.dataset_id}")
        if job.status != "COMPLETE":
            raise CommandError("No validated dataset accepted; inspect the historical data quality report.")
