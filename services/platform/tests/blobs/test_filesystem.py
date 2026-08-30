from pathlib import Path

import pytest

from cycling_workshop.blobs.filesystem import FilesystemBlobStorage


def test_filesystem_blob_storage_round_trips_bytes_under_generated_key(tmp_path: Path) -> None:
    storage = FilesystemBlobStorage(tmp_path)

    key = storage.put(b'wheel photo bytes', content_type='image/jpeg')

    assert storage.get(key) == b'wheel photo bytes'
    assert storage.exists(key)
    assert (tmp_path / key).is_file()


def test_filesystem_blob_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = FilesystemBlobStorage(tmp_path)

    with pytest.raises(ValueError, match='blob key'):
        storage.get('../outside')
