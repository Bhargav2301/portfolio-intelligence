from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import UUID

from portfolio_api.config import Settings


class QuarantineStorage(Protocol):
    def put(self, tenant_id: UUID, upload_id: UUID, suffix: str, content: bytes) -> str: ...

    def delete(self, object_key: str) -> None: ...


class LocalQuarantineStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, tenant_id: UUID, upload_id: UUID, suffix: str, content: bytes) -> str:
        safe_suffix = suffix.lower() if suffix.lower() in {".pdf", ".xls", ".xlsx", ".csv"} else ""
        target_dir = self.root / str(tenant_id) / "quarantine"
        target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        target = (target_dir / f"{upload_id}{safe_suffix}").resolve()
        if self.root not in target.parents:
            raise ValueError("Unsafe storage path")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(target, flags, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return str(target.relative_to(self.root))

    def delete(self, object_key: str) -> None:
        target = (self.root / object_key).resolve()
        if self.root not in target.parents:
            raise ValueError("Unsafe storage path")
        target.unlink(missing_ok=True)


class S3QuarantineStorage:
    def __init__(self, settings: Settings) -> None:
        import boto3

        if not settings.object_storage_endpoint:
            raise ValueError("OBJECT_STORAGE_ENDPOINT is required for S3 storage")
        if not settings.object_storage_access_key or not settings.object_storage_secret_key:
            raise ValueError("Object-storage credentials are required for S3 storage")
        self.bucket = settings.object_storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            region_name=settings.object_storage_region,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            use_ssl=settings.object_storage_secure,
            verify=settings.object_storage_secure,
        )

    def put(self, tenant_id: UUID, upload_id: UUID, suffix: str, content: bytes) -> str:
        safe_suffix = suffix.lower() if suffix.lower() in {".pdf", ".xls", ".xlsx", ".csv"} else ""
        object_key = f"{tenant_id}/quarantine/{upload_id}{safe_suffix}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=content,
            ContentType="application/octet-stream",
            Metadata={"state": "quarantine"},
        )
        return object_key

    def delete(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)


def build_quarantine_storage(settings: Settings) -> QuarantineStorage:
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalQuarantineStorage(settings.storage_directory)
    if backend == "s3":
        return S3QuarantineStorage(settings)
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
