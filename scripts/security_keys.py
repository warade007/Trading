"""Manage local keys without displaying them. Run exports/imports interactively."""
import argparse
import base64
import getpass
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from config.local_secrets import initialize, load_bundle, save_bundle, vault_path, LocalKeyError


def password_cipher(password, salt):
    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "export", "import", "add-key"])
    parser.add_argument("--file", type=Path)
    args = parser.parse_args()
    if args.action == "init":
        created = initialize()
        print("Local DPAPI vault created." if created else "Existing local DPAPI vault verified; unchanged.")
        print("Vault location:", vault_path())
    elif args.action == "add-key":
        if os.environ.get("BROKER_FERNET_KEYS") is not None:
            raise LocalKeyError("Environment keyring is active; rotate it through its protected environment provider.")
        bundle = load_bundle()
        bundle["broker_keys"].insert(0, Fernet.generate_key().decode())
        save_bundle(bundle, replace=True)
        print("New primary key added; all old keys retained. Next run manage.py rotate_broker_keys.")
    else:
        if not args.file or args.file.resolve().is_relative_to(ROOT):
            raise LocalKeyError("Choose a separate backup path outside the project and database backup.")
        password = getpass.getpass("Separate key-backup passphrase (never enter this in chat): ")
        if len(password) < 16:
            raise LocalKeyError("Use a passphrase with at least 16 characters.")
        if args.action == "export":
            if password != getpass.getpass("Repeat passphrase: "):
                raise LocalKeyError("Passphrases do not match.")
            salt = os.urandom(16)
            encrypted = password_cipher(password, salt).encrypt(json.dumps(load_bundle()).encode()).decode()
            with args.file.open("x", encoding="utf-8") as stream:
                json.dump({"version": 1, "salt": base64.b64encode(salt).decode(), "encrypted": encrypted}, stream)
            print("Encrypted key-only backup saved. Store separately from database backups.")
        else:
            if vault_path().exists():
                raise LocalKeyError("A local vault already exists; refusing to overwrite it.")
            if args.file.stat().st_size > 65536:
                raise LocalKeyError("Invalid key backup size.")
            backup = json.loads(args.file.read_text(encoding="utf-8"))
            if backup["version"] != 1:
                raise LocalKeyError("Unsupported backup format.")
            bundle = json.loads(password_cipher(password, base64.b64decode(backup["salt"])).decrypt(backup["encrypted"]))
            save_bundle(bundle)
            print("Keys restored into this user's Windows DPAPI vault.")


if __name__ == "__main__":
    try:
        main()
    except (LocalKeyError, OSError, ValueError, TypeError, KeyError, UnicodeError, InvalidToken):
        print("Key operation failed. Check the vault/backup path, permissions and passphrase; existing keys were not replaced.", file=sys.stderr)
        sys.exit(1)
