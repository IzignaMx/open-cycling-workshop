import hashlib
from pathlib import Path

import pytest
from cycling_workshop.blobs.filesystem import FilesystemBlobStorage


def test_existing_digest_is_checked_and_never_overwritten(tmp_path: Path) -> None:
    storage = FilesystemBlobStorage(tmp_path)
    key = storage.put(b"original", content_type="image/png")
    (tmp_path / key).write_bytes(b"corruption")
    with pytest.raises(ValueError):
        storage.put(b"original", content_type="image/png")
    assert (tmp_path / key).read_bytes() == b"corruption"


def test_bounded_read_rejects_oversize_before_allocation(tmp_path: Path) -> None:
    storage = FilesystemBlobStorage(tmp_path)
    key = storage.put(b"original", content_type="image/png")
    with pytest.raises(ValueError):
        storage.get_bounded(key, max_bytes=2)


def test_symlink_prefix_refused(tmp_path: Path) -> None:
    root = tmp_path / "assets"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    prefix = hashlib.sha256(b"original").hexdigest()[:2]
    (root / prefix).symlink_to(outside, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        FilesystemBlobStorage(root).put(b"original", content_type="image/png")
    assert list(outside.iterdir()) == []


def test_duplicate_publish_is_atomic_across_threads(tmp_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    storage = FilesystemBlobStorage(tmp_path)
    with ThreadPoolExecutor(max_workers=16) as pool:
        keys = list(
            pool.map(lambda _: storage.put(b"same" * 65536, content_type="image/png"), range(32))
        )
    assert len(set(keys)) == 1
    assert storage.get(keys[0]) == b"same" * 65536
    assert not list(tmp_path.rglob(".pending-*"))


@pytest.mark.parametrize("location", ["root", "prefix", "file"])
def test_symlinks_are_refused_for_reads_and_writes(tmp_path: Path, location: str) -> None:
    root = tmp_path / "assets"
    storage = FilesystemBlobStorage(root)
    key = storage.put(b"original", content_type="image/png")
    outside = tmp_path / "outside"
    outside.mkdir()
    if location == "root":
        root.rename(tmp_path / "old")
        root.symlink_to(outside, target_is_directory=True)
    elif location == "prefix":
        (root / key[:2]).rename(tmp_path / "old")
        (root / key[:2]).symlink_to(outside, target_is_directory=True)
    else:
        (root / key).unlink()
        target = outside / "protected"
        target.write_bytes(b"protected")
        (root / key).symlink_to(target)
    with pytest.raises((ValueError, OSError)):
        storage.get_bounded(key, max_bytes=100)
    with pytest.raises((ValueError, OSError)):
        storage.put(b"original", content_type="image/png")
    assert not (outside / key.split("/")[1]).exists()
    if location == "file":
        assert (outside / "protected").read_bytes() == b"protected"


def test_nonregular_and_writable_directories_refused(tmp_path: Path) -> None:
    import os

    storage = FilesystemBlobStorage(tmp_path)
    key = storage.put(b"original", content_type="image/png")
    (tmp_path / key).unlink()
    os.mkfifo(tmp_path / key, mode=0o600)
    with pytest.raises(ValueError):
        storage.get_bounded(key, max_bytes=100)
    (tmp_path / key[:2]).chmod(0o777)
    with pytest.raises(ValueError, match="permissions"):
        storage.put(b"original", content_type="image/png")


@pytest.mark.parametrize("phase", ["file_fsync", "publish", "directory_fsync"])
def test_failure_never_publishes_partial_and_can_recover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    import errno
    import os
    import stat

    storage = FilesystemBlobStorage(tmp_path)
    data = b"durable" * 1024
    digest = hashlib.sha256(data).hexdigest()
    key = f"{digest[:2]}/{digest}"
    (tmp_path / digest[:2]).mkdir(mode=0o700)
    real_fsync, real_link = os.fsync, os.link

    def failing_fsync(fd: int) -> None:
        is_file = stat.S_ISREG(os.fstat(fd).st_mode)
        if (phase == "file_fsync" and is_file) or (phase == "directory_fsync" and not is_file):
            raise OSError(errno.ENOSPC, "synthetic disk full")
        real_fsync(fd)

    def failing_link(*args: object, **kwargs: object) -> None:
        if phase == "publish":
            raise OSError(errno.EIO, "synthetic publication failure")
        real_link(*args, **kwargs)

    monkeypatch.setattr(os, "fsync", failing_fsync)
    monkeypatch.setattr(os, "link", failing_link)
    with pytest.raises(OSError):
        storage.put(data, content_type="image/png")
    if (tmp_path / key).exists():
        assert (tmp_path / key).read_bytes() == data
    else:
        assert phase != "directory_fsync"
    assert not list(tmp_path.rglob(".pending-*"))
    monkeypatch.setattr(os, "fsync", real_fsync)
    monkeypatch.setattr(os, "link", real_link)
    assert storage.put(data, content_type="image/png") == key
    assert storage.get(key) == data


@pytest.mark.parametrize("phase", ["before_fsync", "before_publish", "after_publish"])
def test_actual_process_death_preserves_complete_or_absent_asset(
    tmp_path: Path, phase: str
) -> None:
    import os
    import signal
    import subprocess
    import sys

    script = """import os, signal, stat, sys
from pathlib import Path
from cycling_workshop.blobs.filesystem import FilesystemBlobStorage
storage = FilesystemBlobStorage(Path(sys.argv[1]))
phase = sys.argv[2]
real_fsync, real_link = os.fsync, os.link
def fsync(fd):
    if phase == 'before_fsync' and stat.S_ISREG(os.fstat(fd).st_mode):
        os.kill(os.getpid(), signal.SIGKILL)
    real_fsync(fd)
def link(*args, **kwargs):
    if phase == 'before_publish':
        os.kill(os.getpid(), signal.SIGKILL)
    real_link(*args, **kwargs)
    if phase == 'after_publish':
        os.kill(os.getpid(), signal.SIGKILL)
os.fsync, os.link = fsync, link
storage.put(b'durable crash fixture', content_type='image/png')
"""
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), phase], check=False, timeout=10
    )
    assert result.returncode == -signal.SIGKILL
    digest = hashlib.sha256(b"durable crash fixture").hexdigest()
    key = f"{digest[:2]}/{digest}"
    path = tmp_path / key
    assert path.exists() == (phase == "after_publish")
    if path.exists():
        assert path.read_bytes() == b"durable crash fixture"
    storage = FilesystemBlobStorage(tmp_path)
    assert storage.put(b"durable crash fixture", content_type="image/png") == key
    assert storage.get(key) == b"durable crash fixture"
    assert os.stat(path).st_mode & 0o777 == 0o600


def test_bounded_read_checks_fstat_before_reading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    storage = FilesystemBlobStorage(tmp_path)
    key = storage.put(b"original", content_type="image/png")
    with (tmp_path / key).open("wb") as file:
        file.truncate(10 * 1024 * 1024 * 1024)  # sparse corruption, no allocation

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("oversize opened file was read")

    monkeypatch.setattr(os, "fdopen", forbidden)
    with pytest.raises(ValueError, match="byte limit"):
        storage.get_bounded(key, max_bytes=262144)
