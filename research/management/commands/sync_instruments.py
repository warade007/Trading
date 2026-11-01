from django.core.management.base import BaseCommand, CommandError
from brokers.errors import BrokerError
from research.historical import sync_instruments


class Command(BaseCommand):
    help = "Read and archive the NSE master using the existing encrypted broker session."

    def handle(self, *args, **options):
        try:
            master, created = sync_instruments()
        except BrokerError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(f"NSE master {master.pk}: {master.instrument_count} records; {'created' if created else 'unchanged'}; SHA-256 {master.sha256}.")
