from django.core.management.base import CommandError
from django.core.management.commands.runserver import Command as DjangoRunserver


class Command(DjangoRunserver):
    help = "Run the research dashboard on IPv4 loopback only."

    def handle(self, *args, **options):
        address = options.get("addrport") or "127.0.0.1:8000"
        if options.get("use_ipv6") or (
            not address.isdecimal() and not address.startswith("127.0.0.1:")
        ):
            raise CommandError("Research server must bind to 127.0.0.1.")
        return super().handle(*args, **options)
