"""Initialize a new local deployment's secret files; never rotate existing secrets."""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path
from urllib.parse import quote


def initialize_secrets(destination: Path, *, include_admin: bool = False) -> None:
    # Exclusive directory creation also refuses symlinks and partially initialized
    # installations. Failure leaves evidence for the operator, never deletes files.
    destination.mkdir(mode=0o700, parents=False, exist_ok=False)
    password = secrets.token_urlsafe(48)
    values = {
        "postgres_password.txt": password,
        "postgres_admin_password.txt": secrets.token_urlsafe(48),
        "auth_secret.txt": secrets.token_urlsafe(64),
        "database_url.txt": (
            f"postgresql+psycopg://ocwp:{quote(password, safe='')}@postgres:5432/ocwp"
        ),
    }
    if include_admin:
        values["admin_password.txt"] = secrets.token_urlsafe(32)
    for name, value in values.items():
        descriptor = os.open(destination / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="New directory; existing paths are refused")
    parser.add_argument(
        "--with-admin", action="store_true", help="Also generate first-admin password"
    )
    args = parser.parse_args()
    initialize_secrets(args.directory, include_admin=args.with_admin)
    if os.name != "posix":
        print("Review native ACLs before use; POSIX permission modes are not enforced here.")
    print("Secret files initialized. Keep them private; this does not start or configure a server.")


if __name__ == "__main__":
    main()
