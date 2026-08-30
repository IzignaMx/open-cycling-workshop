from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath


class FilesystemBlobStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, *, content_type: str) -> str:
        del content_type  # Metadata persistence belongs to the owning bounded context.
        digest = hashlib.sha256(data).hexdigest()
        key = f"{digest[:2]}/{digest}"
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path_for(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path_for(key).is_file()

    def delete(self, key: str) -> None:
        path = self._path_for(key)
        path.unlink(missing_ok=True)

    def _path_for(self, key: str) -> Path:
        parsed = PurePosixPath(key)
        if parsed.is_absolute() or not parsed.parts or any(part in {"", ".", ".."} for part in parsed.parts):
            raise ValueError("invalid blob key")
        candidate = (self._root / Path(*parsed.parts)).resolve()
        if self._root not in candidate.parents:
            raise ValueError("invalid blob key")
        return candidate
