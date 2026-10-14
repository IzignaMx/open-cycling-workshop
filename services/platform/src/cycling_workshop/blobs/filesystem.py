from __future__ import annotations

import hashlib
import os
import re
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

_KEY = re.compile(r"([0-9a-f]{2})/([0-9a-f]{64})\Z")
_DIRECTORY_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_CLOEXEC", 0)
)
_FILE_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
)


def _check_directory(fd: int, *, private: bool) -> None:
    details = os.fstat(fd)
    # A root-owned sticky ancestor (e.g. /tmp) is safe for an owned child.
    sticky_root = details.st_uid == 0 and bool(details.st_mode & stat.S_ISVTX)
    if (
        details.st_uid not in (0, os.geteuid())
        or (details.st_mode & 0o022 and (private or not sticky_root))
        or (private and details.st_uid != os.geteuid())
    ):
        raise ValueError("unsafe blob directory ownership or permissions")


def _open_child(parent: int, name: str, *, create: bool) -> int:
    if create:
        try:
            os.mkdir(name, mode=0o700, dir_fd=parent)
            os.fsync(parent)
        except FileExistsError:
            pass
    fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=parent)
    try:
        _check_directory(fd, private=True)
    except BaseException:
        os.close(fd)
        raise
    return fd


class FilesystemBlobStorage:
    """Private immutable content addressing on a trusted POSIX filesystem.

    Directory descriptors and O_NOFOLLOW prevent pathname/symlink races. Root
    and subdirectories must be owned by this runtime and not writable by others.
    Files are fsynced then hard-linked without replacement before directory fsync.
    Same-UID malicious processes/privileged host administrators remain trusted.
    """

    def __init__(self, root: Path, *, create: bool = True) -> None:
        if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise OSError("secure blob storage requires POSIX descriptor support")
        self._root = Path(os.path.abspath(root))
        with self._root_fd(create=create):
            pass

    @contextmanager
    def _root_fd(self, *, create: bool = False) -> Iterator[int]:
        fd = os.open("/", _DIRECTORY_FLAGS)
        try:
            parts = self._root.parts[1:]
            if not parts:
                raise ValueError("invalid blob root")
            for index, part in enumerate(parts):
                _check_directory(fd, private=False)
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                        os.fsync(fd)
                    except FileExistsError:
                        pass
                child = os.open(part, _DIRECTORY_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = child
                if index == len(parts) - 1:
                    _check_directory(fd, private=True)
            yield fd
        finally:
            os.close(fd)

    @staticmethod
    def _key_parts(key: str) -> tuple[str, str]:
        match = _KEY.fullmatch(key)
        if match is None or match[1] != match[2][:2]:
            raise ValueError("invalid blob key")
        return match[1], match[2]

    @staticmethod
    def _read_at(directory: int, digest: str, *, max_bytes: int | None) -> bytes:
        fd = os.open(digest, _FILE_FLAGS, dir_fd=directory)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o022
            ):
                raise ValueError("invalid blob file")
            if max_bytes is not None and info.st_size > max_bytes:
                raise ValueError("blob exceeds byte limit")
            limit = info.st_size if max_bytes is None else max_bytes
            with os.fdopen(fd, "rb", closefd=False) as stream:
                data = stream.read(limit + 1)
            if (
                len(data) != info.st_size
                or len(data) > limit
                or hashlib.sha256(data).hexdigest() != digest
            ):
                raise ValueError("blob integrity failure")
            return data
        finally:
            os.close(fd)

    def put(self, data: bytes, *, content_type: str) -> str:
        del content_type  # Metadata persistence belongs to the owning bounded context.
        digest = hashlib.sha256(data).hexdigest()
        key = f"{digest[:2]}/{digest}"
        with self._root_fd() as root:
            directory = _open_child(root, digest[:2], create=True)
            temporary = f".pending-{secrets.token_hex(16)}"
            try:
                fd = os.open(
                    temporary,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=directory,
                )
                try:
                    with os.fdopen(fd, "wb", closefd=False) as stream:
                        stream.write(data)
                        stream.flush()
                    os.fsync(fd)
                finally:
                    os.close(fd)
                try:
                    os.link(
                        temporary,
                        digest,
                        src_dir_fd=directory,
                        dst_dir_fd=directory,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    existing = self._read_at(directory, digest, max_bytes=len(data))
                    if existing != data:
                        raise ValueError("blob integrity failure") from None
                os.unlink(temporary, dir_fd=directory)
                os.fsync(directory)
            finally:
                try:
                    with suppress(FileNotFoundError):
                        os.unlink(temporary, dir_fd=directory)
                finally:
                    os.close(directory)
        return key

    def get(self, key: str) -> bytes:
        return self._get(key, max_bytes=None)

    def get_bounded(self, key: str, *, max_bytes: int) -> bytes:
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 0:
            raise ValueError("invalid blob byte limit")
        return self._get(key, max_bytes=max_bytes)

    def _get(self, key: str, *, max_bytes: int | None) -> bytes:
        prefix, digest = self._key_parts(key)
        with self._root_fd() as root:
            directory = _open_child(root, prefix, create=False)
            try:
                return self._read_at(directory, digest, max_bytes=max_bytes)
            finally:
                os.close(directory)

    def exists(self, key: str) -> bool:
        prefix, digest = self._key_parts(key)
        try:
            with self._root_fd() as root:
                directory = _open_child(root, prefix, create=False)
                try:
                    fd = os.open(digest, _FILE_FLAGS, dir_fd=directory)
                    try:
                        return stat.S_ISREG(os.fstat(fd).st_mode)
                    finally:
                        os.close(fd)
                finally:
                    os.close(directory)
        except FileNotFoundError:
            return False

    def delete(self, key: str) -> None:
        prefix, digest = self._key_parts(key)
        try:
            with self._root_fd() as root:
                directory = _open_child(root, prefix, create=False)
                try:
                    os.unlink(digest, dir_fd=directory)
                    os.fsync(directory)
                finally:
                    os.close(directory)
        except FileNotFoundError:
            pass
