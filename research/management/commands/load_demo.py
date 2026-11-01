from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from research.services import import_dataset, resample_dataset


class Command(BaseCommand):
    help = "Idempotently load the bundled SYNTHETIC dataset and derive 5m/15m bars."

    def handle(self, *args, **options):
        fixtures = settings.BASE_DIR / "tests" / "fixtures"
        try:
            job, created = import_dataset(fixtures / "synthetic.csv", fixtures / "synthetic.manifest.json")
            if job.status != "ACCEPTED":
                raise ValueError("Synthetic fixture rejected; inspect the quality report.")
            self.stdout.write(f"SYNTHETIC dataset {job.pk}: {job.imported_minutes}/{job.expected_minutes} 1m bars; {'created' if created else 'unchanged'}.")
            for interval in (5, 15):
                count, skipped, _ = resample_dataset(job.pk, interval)
                self.stdout.write(f"{interval}m: {count} complete bars, {skipped} incomplete buckets.")
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
