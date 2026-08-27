from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from portfolio_api.config import Settings


class QuarantineStorage(Protocol):
    def put(self, tenant_id: UUID, upload_id: UUID, suffix: str, content: bytes) -> str: ...

    def delete(self, object_key: str) -> None: ...

    def read(self, object_key: str) -> bytes: ...

    def head(self, object_key: str) -> StorageObjectInfo: ...

    def presign(
        self,
        tenant_id: UUID,
        upload_id: UUID,
        suffix: str,
        *,
        sha256: str,
        content_type: str,
        max_size: int,
        expires_seconds: int,
    ) -> tuple[str, dict[str, Any]]: ...


@dataclass(frozen=True)
class StorageObjectInfo:
    size_bytes: int
    metadata: dict[str, str]


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
        target = self._target(object_key)
        target.unlink(missing_ok=True)

    def _target(self, object_key: str) -> Path:
        target = (self.root / object_key).resolve()
        if self.root not in target.parents:
            raise ValueError("Unsafe storage path")
        return target

    def read(self, object_key: str) -> bytes:
        return self._target(object_key).read_bytes()

    def head(self, object_key: str) -> StorageObjectInfo:
        target = self._target(object_key)
        return StorageObjectInfo(size_bytes=target.stat().st_size, metadata={})

    def presign(
        self,
        tenant_id: UUID,
        upload_id: UUID,
        suffix: str,
        *,
        sha256: str,
        content_type: str,
        max_size: int,
        expires_seconds: int,
    ) -> tuple[str, dict[str, Any]]:
        del sha256, content_type, max_size, expires_seconds
        safe_suffix = suffix.lower() if suffix.lower() == ".csv" else ""
        object_key = f"{tenant_id}/quarantine/{upload_id}{safe_suffix}"
        return object_key, {
            "upload_url": f"/v1/uploads/{upload_id}/content",
            "method": "PUT",
            "fields": {},
            "required_headers": {"Content-Type": "text/csv"},
        }


class S3QuarantineStorage:
    def __init__(self, settings: Settings) -> None:
        import boto3

        self.bucket = settings.object_storage_bucket
        self.kms_key_id = settings.object_storage_kms_key_id
        client_options: dict[str, Any] = {
            "region_name": settings.object_storage_region,
            "use_ssl": settings.object_storage_secure,
            "verify": settings.object_storage_secure,
        }
        if settings.object_storage_endpoint:
            client_options["endpoint_url"] = settings.object_storage_endpoint
        if settings.object_storage_access_key and settings.object_storage_secret_key:
            client_options["aws_access_key_id"] = settings.object_storage_access_key
            client_options["aws_secret_access_key"] = settings.object_storage_secret_key
        self.client = boto3.client("s3", **client_options)

    def put(self, tenant_id: UUID, upload_id: UUID, suffix: str, content: bytes) -> str:
        safe_suffix = suffix.lower() if suffix.lower() in {".pdf", ".xls", ".xlsx", ".csv"} else ""
        object_key = f"{tenant_id}/quarantine/{upload_id}{safe_suffix}"
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_key,
            Body=content,
            ContentType="application/octet-stream",
            Metadata={"state": "quarantine"},
            ServerSideEncryption="aws:kms" if self.kms_key_id else "AES256",
            **({"SSEKMSKeyId": self.kms_key_id} if self.kms_key_id else {}),
        )
        return object_key

    def delete(self, object_key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def read(self, object_key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=object_key)
        return response["Body"].read()

    def head(self, object_key: str) -> StorageObjectInfo:
        response = self.client.head_object(Bucket=self.bucket, Key=object_key)
        return StorageObjectInfo(
            size_bytes=int(response["ContentLength"]),
            metadata={str(key): str(value) for key, value in response.get("Metadata", {}).items()},
        )

    def presign(
        self,
        tenant_id: UUID,
        upload_id: UUID,
        suffix: str,
        *,
        sha256: str,
        content_type: str,
        max_size: int,
        expires_seconds: int,
    ) -> tuple[str, dict[str, Any]]:
        safe_suffix = suffix.lower() if suffix.lower() == ".csv" else ""
        object_key = f"{tenant_id}/quarantine/{upload_id}{safe_suffix}"
        fields = {
            "Content-Type": content_type,
            "x-amz-meta-sha256": sha256,
            "x-amz-meta-state": "quarantine",
        }
        if self.kms_key_id:
            fields["x-amz-server-side-encryption"] = "aws:kms"
            fields["x-amz-server-side-encryption-aws-kms-key-id"] = self.kms_key_id
        conditions: list[Any] = [
            {"Content-Type": content_type},
            {"x-amz-meta-sha256": sha256},
            {"x-amz-meta-state": "quarantine"},
            ["content-length-range", 1, max_size],
        ]
        if self.kms_key_id:
            conditions.append({"x-amz-server-side-encryption": "aws:kms"})
            conditions.append({"x-amz-server-side-encryption-aws-kms-key-id": self.kms_key_id})
        policy = self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=object_key,
            Fields=fields,
            Conditions=conditions,
            ExpiresIn=expires_seconds,
        )
        return object_key, {
            "upload_url": policy["url"],
            "method": "POST",
            "fields": {str(key): str(value) for key, value in policy["fields"].items()},
            "required_headers": {},
        }


def build_quarantine_storage(settings: Settings) -> QuarantineStorage:
    backend = settings.storage_backend.lower()
    if backend == "local":
        return LocalQuarantineStorage(settings.storage_directory)
    if backend == "s3":
        return S3QuarantineStorage(settings)
    raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
