#!/usr/bin/env python3
"""Compare the one authorized public Pages destination with a reviewed build leaf."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import signal
import stat
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from email.message import Message
from http.client import HTTPException
from pathlib import Path
from types import FrameType
from typing import Any, NamedTuple
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

EXPECTED_URL = "https://izignamx.github.io/open-cycling-workshop/"
PUBLIC_FILES = (
    "index.html",
    "styles.css",
    "screenshots.json",
    "build-info.json",
    "assets/screenshots/banco-default-desktop.png",
    "assets/screenshots/banco-mobile-320.png",
    "assets/screenshots/banco-tablet-touch.png",
    "assets/screenshots/noche-canonical-desktop-full.png",
)
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024
REQUEST_SECONDS = 10


class VerificationError(ValueError):
    """Fixed diagnostic only; remote content is never included."""


class Fetched(NamedTuple):
    status: int
    url: str
    body: bytes


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: Any, code: int, msg: str, headers: Message, newurl: str
    ) -> None:
        return None


@contextmanager
def request_deadline() -> Iterator[None]:
    # Socket timeouts alone reset during slow reads and do not bound DNS. This
    # CLI targets the Linux Actions runner; unsupported contexts fail closed.
    if (
        not hasattr(signal, "setitimer")
        or threading.current_thread() is not threading.main_thread()
    ):
        raise VerificationError("E_DEADLINE")
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise VerificationError("E_DEADLINE")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(_signum: int, _frame: FrameType | None) -> None:
        raise VerificationError("E_TIMEOUT")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, REQUEST_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def public_url(name: str) -> str:
    if name not in PUBLIC_FILES:
        raise VerificationError("E_URL")
    return EXPECTED_URL if name == "index.html" else EXPECTED_URL + name


def fetch_public(url: str) -> Fetched:
    if url not in {public_url(name) for name in PUBLIC_FILES}:
        raise VerificationError("E_URL")
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(
        url, headers={"Accept-Encoding": "identity", "User-Agent": "OCWP-public-site-verifier"}
    )
    try:
        with request_deadline(), opener.open(request, timeout=REQUEST_SECONDS) as response:
            if response.status != 200:
                raise VerificationError("E_HTTP")
            if response.geturl() != url:
                raise VerificationError("E_REDIRECT")
            if response.headers.get("Content-Encoding", "identity") != "identity":
                raise VerificationError("E_ENCODING")
            body = response.read(MAX_FILE_BYTES + 1)
            if len(body) > MAX_FILE_BYTES:
                raise VerificationError("E_SIZE")
            return Fetched(response.status, response.geturl(), body)
    except VerificationError:
        raise
    except HTTPError as exc:
        raise VerificationError("E_HTTP") from exc
    except (OSError, URLError, HTTPException) as exc:
        raise VerificationError("E_NETWORK") from exc


def local_contents(directory: Path) -> dict[str, bytes]:
    directory = Path(directory)
    if any(path.is_symlink() for path in (directory, *directory.absolute().parents)):
        raise VerificationError("E_LOCAL")
    if not directory.is_dir():
        raise VerificationError("E_LOCAL")
    expected = {*PUBLIC_FILES, ".nojekyll", "assets", "assets/screenshots"}
    paths = list(directory.rglob("*"))
    if {str(path.relative_to(directory)) for path in paths} != expected:
        raise VerificationError("E_LOCAL")
    content = {}
    total = 0
    for path in paths:
        if path.is_symlink():
            raise VerificationError("E_LOCAL")
        name = str(path.relative_to(directory))
        if name in {"assets", "assets/screenshots"}:
            if not path.is_dir():
                raise VerificationError("E_LOCAL")
            continue
        if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size > MAX_FILE_BYTES:
            raise VerificationError("E_LOCAL")
        with path.open("rb") as file:
            raw = file.read(MAX_FILE_BYTES + 1)
        total += len(raw)
        if len(raw) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise VerificationError("E_SIZE")
        content[name] = raw
    if content.pop(".nojekyll") != b"":
        raise VerificationError("E_LOCAL")
    return content


def verify(
    url: str, directory: Path, *, fetch: Callable[[str], Fetched] = fetch_public
) -> dict[str, object]:
    if url != EXPECTED_URL:
        raise VerificationError("E_URL")
    try:
        content = local_contents(directory)
        info = json.loads(content["build-info.json"])
        captures = json.loads(content["screenshots.json"])
        source = info["capture_source"]
        status = info["capture_status"]
        if (
            not isinstance(source, str)
            or re.fullmatch(r"[0-9a-f]{40}", source) is None
            or source != captures["source_commit"]
            or status not in ("current-runtime", "historical-runtime")
        ):
            raise VerificationError("E_PROVENANCE")
    except VerificationError:
        raise
    except OSError as exc:
        raise VerificationError("E_LOCAL") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise VerificationError("E_PROVENANCE") from exc
    evidence = {}
    total = 0
    for name in PUBLIC_FILES:
        target = public_url(name)
        response = fetch(target)
        if response.status != 200:
            raise VerificationError("E_HTTP")
        if response.url != target:
            raise VerificationError("E_REDIRECT")
        if not isinstance(response.body, bytes):
            raise VerificationError("E_CONTENT")
        total += len(response.body)
        if len(response.body) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise VerificationError("E_SIZE")
        digest = hashlib.sha256(response.body).hexdigest()
        if digest != hashlib.sha256(content[name]).hexdigest():
            raise VerificationError("E_MISMATCH")
        evidence[name] = {"bytes": len(response.body), "sha256": digest}
    return {
        "verified_url": url,
        "files": evidence,
        "capture_source": source,
        "capture_status": status,
        "nojekyll": "local empty marker; not fetched",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        evidence = verify(args.url, args.directory)
    except VerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
