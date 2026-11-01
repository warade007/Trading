"""Windows current-user DPAPI key vault, outside the project and database.

Never print bundle contents or include them in exception messages.
"""
import ctypes
import hashlib
import json
import os
import secrets
from pathlib import Path


class LocalKeyError(Exception):
    pass


def vault_path():
    if os.name != "nt" or not os.environ.get("LOCALAPPDATA"):
        raise LocalKeyError("Use protected DJANGO_SECRET_KEY and BROKER_FERNET_KEYS environment variables on this platform.")
    identity = hashlib.sha256(str(Path(__file__).resolve().parents[1]).lower().encode()).hexdigest()[:16]
    return Path(os.environ["LOCALAPPDATA"]) / "TradingResearch" / identity / "security.dpapi"


def _dpapi(raw, decrypt=False):
    if os.name != "nt":
        raise LocalKeyError("Windows DPAPI is unavailable.")

    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    function = library.CryptUnprotectData if decrypt else library.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    function.restype = ctypes.c_int
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise LocalKeyError("Local key vault could not be opened by this Windows user.")
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        free = ctypes.WinDLL("kernel32").LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(output.data)


def validate_bundle(bundle):
    from cryptography.fernet import Fernet

    try:
        if not isinstance(bundle["django_secret"], str) or len(bundle["django_secret"]) < 50:
            raise ValueError
        if not isinstance(bundle["broker_keys"], list) or not 1 <= len(bundle["broker_keys"]) <= 32:
            raise ValueError
        for key in bundle["broker_keys"]:
            Fernet(key.encode("ascii"))
        if bundle["django_secret"] in bundle["broker_keys"]:
            raise ValueError
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise LocalKeyError("Invalid local security key bundle.") from None
    return bundle


def load_bundle():
    try:
        return validate_bundle(json.loads(_dpapi(vault_path().read_bytes(), decrypt=True)))
    except (OSError, ValueError, TypeError):
        raise LocalKeyError("Local security keys unavailable. Run scripts/security_keys.py init or restore the separate key backup.") from None


def save_bundle(bundle, replace=False):
    path = vault_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = _dpapi(json.dumps(validate_bundle(bundle)).encode())
    if not replace:
        with path.open("xb") as stream:
            stream.write(blob)
    else:
        temporary = path.with_name("security-" + secrets.token_hex(8) + ".tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(blob)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def initialize():
    from cryptography.fernet import Fernet

    if vault_path().exists():
        load_bundle()  # Never silently regenerate a damaged or inaccessible key.
        return False
    save_bundle({"django_secret": secrets.token_urlsafe(64),
                 "broker_keys": [Fernet.generate_key().decode()]})
    return True


def django_secret():
    value = os.environ.get("DJANGO_SECRET_KEY")
    if value is not None:
        if len(value) < 50:
            raise LocalKeyError("DJANGO_SECRET_KEY must contain at least 50 random characters.")
        return value
    return load_bundle()["django_secret"]


def broker_keys():
    value = os.environ.get("BROKER_FERNET_KEYS")
    if value is not None:
        try:
            return json.loads(value)
        except ValueError:
            raise LocalKeyError("BROKER_FERNET_KEYS must be a JSON array of Fernet keys.") from None
    return load_bundle()["broker_keys"]
