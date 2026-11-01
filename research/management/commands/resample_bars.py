from django.core.management.base import BaseCommand, CommandError
from research.models import DataIngestJob
from research.services import resample_dataset


class Command(BaseCommand):
    help = "Derive complete session-anchored 5m/15m bars from an accepted dataset."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", required=True, type=int)
        parser.add_argument("--interval", required=True, type=int, choices=[5, 15])

    def handle(self, *args, **options):
        try:
            count, skipped, created = resample_dataset(options["dataset"], options["interval"])
        except (ValueError, DataIngestJob.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Dataset {options['dataset']}: {count} x {options['interval']}m bars; "
                          f"{skipped} incomplete buckets; {'created' if created else 'unchanged'}.")
