from django.core.management.base import BaseCommand, CommandError
from research.services import import_dataset


class Command(BaseCommand):
    help = "Validate and atomically import a local CSV with a provenance/session manifest."

    def add_arguments(self, parser):
        parser.add_argument("csv")
        parser.add_argument("--manifest", required=True)

    def handle(self, *args, **options):
        try:
            job, created = import_dataset(options["csv"], options["manifest"])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(f"Dataset {job.pk}: {job.status}; {job.source_kind}; "
                          f"{job.imported_minutes}/{job.expected_minutes} minutes ({job.coverage}%); "
                          f"{'created' if created else 'unchanged'}; issues={job.issues.count()}")
        for issue in job.issues.all()[:20]:
            self.stdout.write(f"{issue.severity} {issue.code}: {issue.message}")
        if job.status == "REJECTED":
            raise CommandError("Import rejected; no candles written. Quality report retained.")
