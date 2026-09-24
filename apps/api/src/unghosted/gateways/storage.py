"""File storage gateway (ADR 0001): local filesystem or AWS S3 behind one
interface. Both implementations pass the same contract test suite
(test_storage.py); S3 is exercised in CI with an in-process moto server."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Self

if TYPE_CHECKING:
    from types import TracebackType

_CHUNK_BYTES = 64 * 1024


class StorageError(RuntimeError):
    """A storage operation failed. Keys are app-generated, so a missing
    key means data loss, not a client error."""


class StorageGateway(Protocol):
    async def write(self, key: str, data: bytes) -> None: ...

    def read(self, key: str) -> AsyncIterator[bytes]: ...

    async def exists(self, key: str) -> bool: ...

    async def delete(self, key: str) -> None: ...


class LocalStorageGateway:
    """One file per storage key under a root directory. Dev, CI, staging."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        # Storage keys are app-generated (domain.documents.storage_key);
        # the resolve check keeps a future bug from escaping the root.
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root.resolve()):
            raise StorageError(f"storage key escapes root: {key!r}")
        return path

    async def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> AsyncIterator[bytes]:
        path = self._path(key)
        if not path.is_file():
            raise StorageError(f"missing storage key: {key}")

        async def stream() -> AsyncIterator[bytes]:
            with path.open("rb") as handle:
                while chunk := handle.read(_CHUNK_BYTES):
                    yield chunk

        return stream()

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    async def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            path.unlink()
        except FileNotFoundError as exc:
            raise StorageError(f"missing storage key: {key}") from exc


class S3StorageGateway:
    """AWS S3 (production). aioboto3 is imported lazily so local-only
    installs (backend=local) do not need botocore on disk."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str | None,
        endpoint_url: str | None = None,
    ) -> None:
        import aioboto3  # lazy: heavy dependency, only needed on s3 backend

        self._bucket = bucket
        self._session = aioboto3.Session()
        self._region = region
        self._endpoint_url = endpoint_url
        self._client = None

    async def _s3(self) -> Any:
        """aioboto3 has no type stubs: everything under this class is Any
        to mypy (see the pyproject override), so the contract tests are the
        type boundary."""
        if self._client is None:
            self._client = await self._session.client(
                "s3",
                region_name=self._region,
                endpoint_url=self._endpoint_url,
            ).__aenter__()
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    async def __aenter__(self) -> Self:
        await self._s3()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def write(self, key: str, data: bytes) -> None:
        s3 = await self._s3()
        await s3.put_object(Bucket=self._bucket, Key=key, Body=data)

    def read(self, key: str) -> AsyncIterator[bytes]:
        async def stream() -> AsyncIterator[bytes]:
            s3 = await self._s3()
            try:
                response = await s3.get_object(Bucket=self._bucket, Key=key)
                body = response["Body"]
                while chunk := await body.read(_CHUNK_BYTES):
                    yield chunk
            except s3.exceptions.NoSuchKey as exc:
                raise StorageError(f"missing storage key: {key}") from exc

        return stream()

    async def exists(self, key: str) -> bool:
        s3 = await self._s3()
        try:
            await s3.head_object(Bucket=self._bucket, Key=key)
        except s3.exceptions.ClientError:
            return False
        return True

    async def delete(self, key: str) -> None:
        s3 = await self._s3()
        await s3.delete_object(Bucket=self._bucket, Key=key)
