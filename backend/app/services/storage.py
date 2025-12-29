from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class StoredObject:
    storage: str
    storage_key: str
    url: str


class StorageProvider:
    def put_image(self, *, data: bytes, ext: str, now: datetime) -> StoredObject:
        raise NotImplementedError


class LocalStaticStorage(StorageProvider):
    """Save file under backend/app/static and expose via /static/..."""

    def __init__(self, static_dir: Path, public_base_url: str = "") -> None:
        self._static_dir = static_dir
        self._public_base_url = str(public_base_url or "").strip().rstrip("/")

    def put_image(self, *, data: bytes, ext: str, now: datetime) -> StoredObject:
        rel_dir = Path("uploads") / str(now.year) / f"{now.month:02d}"
        target_dir = self._static_dir / rel_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        # We keep random name (content is deduped by sha256 at DB level).
        from uuid import uuid4

        filename = f"{uuid4().hex}.{ext}"
        target_path = target_dir / filename
        target_path.write_bytes(data)

        storage_key = (rel_dir / filename).as_posix()  # uploads/2025/12/xxx.jpg
        url_path = f"/static/{storage_key}"
        url = f"{self._public_base_url}{url_path}" if self._public_base_url else url_path
        return StoredObject(storage="LOCAL", storage_key=storage_key, url=url)


