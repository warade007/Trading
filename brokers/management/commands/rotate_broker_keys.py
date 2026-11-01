from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from brokers.errors import BrokerError
from brokers.models import BrokerConnection, BrokerSession
from brokers.services import audit


class Command(BaseCommand):
    help = "Atomically re-encrypt credentials using the current primary key; retain old keys for backups."

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                for connection in BrokerConnection.objects.select_for_update():
                    if connection.encrypted_api_secret:
                        connection.set_secret(connection.get_secret())
                        connection.save(update_fields=["encrypted_api_secret", "updated_at"])
                for session in BrokerSession.objects.select_for_update().exclude(encrypted_access_token=""):
                    session.set_token(session.get_token())
                    session.save(update_fields=["encrypted_access_token", "updated_at"])
                audit(None, None, "KEYS_ROTATED")
        except BrokerError as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write("Broker ciphertext re-encrypted successfully. No keys or tokens displayed.")
