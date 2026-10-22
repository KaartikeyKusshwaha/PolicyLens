"""Explicit database drivers and purpose-separated SQLCipher keys. No format fallback."""

import hashlib
import hmac
import sqlite3
from contextlib import closing
from pathlib import Path

from sqlcipher3 import dbapi2 as cipher

from security import SecretBox

DB_ERRORS = (sqlite3.Error, cipher.Error)
INTEGRITY_ERRORS = (sqlite3.IntegrityError, cipher.IntegrityError)
STORAGE_ERRORS = (RuntimeError, OSError, *DB_ERRORS)


def encrypted(settings):
    return settings is not None and settings.database_encryption == "sqlcipher4"


def driver(settings=None):
    return cipher if encrypted(settings) else sqlite3


def database_key(settings, *, create=False):
    master = SecretBox(settings).key(create=create)
    return hmac.new(
        master, b"policylens:database-encryption:v1", hashlib.sha256
    ).digest()


def connect_database(path, settings=None, *, readonly=False):
    path = Path(path).resolve()
    selected = driver(settings)
    first_database = (
        not readonly
        and encrypted(settings)
        and not any(
            p.exists()
            for p in (
                path,
                settings.database_path,
                settings.database_path.parent / "identity.db",
            )
        )
    )
    key = database_key(settings, create=first_database) if encrypted(settings) else None
    connection = selected.connect(
        path.as_uri() + "?mode=ro" if readonly else path, uri=readonly, timeout=15
    )
    try:
        if key is not None:
            version = connection.execute("PRAGMA cipher_version").fetchone()
            if not version or not str(version[0]).startswith("4."):
                raise RuntimeError(
                    "A supported SQLCipher 4 database driver is required."
                )
            # Generated hex is not user SQL. PRAGMA key does not support parameters.
            connection.execute("PRAGMA key=\"x'" + key.hex() + "'\"")
            connection.execute("PRAGMA cipher_memory_security=ON")
            connection.execute("PRAGMA temp_store=MEMORY")
            # Key setup alone does not prove decryption; force a real schema read.
            connection.execute("SELECT count(*) FROM sqlite_master").fetchone()
            if connection.execute("PRAGMA cipher_status").fetchone() != ("1",):
                raise RuntimeError("The database handle is not encrypted.")
        return connection
    except Exception:
        connection.close()
        raise


def descriptor(settings=None):
    if not encrypted(settings):
        return {"scheme": "none"}
    return {
        "scheme": "sqlcipher4",
        "key_fingerprint": hashlib.sha256(database_key(settings)).hexdigest(),
    }


def encryption_status(settings):
    if not encrypted(settings):
        return {
            "configured": False,
            "scheme": "none",
            "scope": "Whole-file database encryption is not enabled by the application.",
        }
    with closing(
        connect_database(settings.database_path, settings, readonly=True)
    ) as connection:
        version = connection.execute("PRAGMA cipher_version").fetchone()[0]
    return {
        "configured": True,
        "verified": True,
        **descriptor(settings),
        "cipher_version": version,
        "scope": "Protects database files against copying without the installation key. Does not protect a compromised running host or plaintext exports.",
    }
