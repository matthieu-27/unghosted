"""Document domain rules, envelope encryption and storage gateways (us-4)."""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from unghosted.domain.documents import (
    DocumentValidationError,
    checksum_sha256,
    extract_pdf_text,
    parse_master_key,
    sniff_pdf,
    storage_key,
    validate_type_key,
)
from unghosted.domain.eligibility import (
    DocumentRef,
    IneligibleDocumentError,
    ensure_model_eligible,
)
from unghosted.gateways.encrypt import DecryptionError, EnvelopeEncryptor
from unghosted.gateways.storage import (
    LocalStorageGateway,
    S3StorageGateway,
    StorageError,
)

if TYPE_CHECKING:
    from unghosted.domain.templates import Template

MASTER_KEY = b"0" * 32


def make_pdf() -> bytes:
    """Smallest readable PDF: one blank page from pypdf's own writer."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def template() -> Iterator[Template]:
    from unghosted.domain.templates import load_templates

    templates = load_templates(Path(os.environ["UNGHOSTED_SHARED_TEMPLATES_DIR"]))
    yield templates["apprenticeship-search"]


def test_validate_type_key_resolves_eligible_and_ineligible_types(
    template: Template,
) -> None:
    cv = validate_type_key("cv", template)
    id_document = validate_type_key("id_document", template)
    assert cv.model_eligible is True
    assert id_document.model_eligible is False


def test_validate_type_key_rejects_type_outside_template(template: Template) -> None:
    with pytest.raises(DocumentValidationError, match="unknown document type"):
        validate_type_key("transcript", template)


def test_sniff_pdf_rejects_non_pdf_header() -> None:
    with pytest.raises(DocumentValidationError, match="not a PDF"):
        sniff_pdf(b"<html>not a pdf</html>")


def test_sniff_pdf_accepts_generated_pdf() -> None:
    sniff_pdf(make_pdf())


def test_extract_pdf_text_rejects_corrupt_pdf() -> None:
    with pytest.raises(DocumentValidationError, match="cannot be parsed"):
        extract_pdf_text(b"%PDF-broken")


def test_extract_pdf_text_reads_generated_pdf() -> None:
    assert isinstance(extract_pdf_text(make_pdf()), str)


def test_checksum_sha256_matches_hashlib() -> None:
    content = b"document content"
    assert checksum_sha256(content) == hashlib.sha256(content).hexdigest()


def test_storage_key_never_contains_the_filename() -> None:
    owner, document = uuid.uuid4(), uuid.uuid4()
    assert storage_key(str(owner), str(document)) == (
        f"users/{owner}/documents/{document}.bin"
    )


def test_parse_master_key_decodes_base64() -> None:
    assert parse_master_key(base64.b64encode(MASTER_KEY).decode()) == MASTER_KEY


def test_parse_master_key_rejects_invalid_base64() -> None:
    with pytest.raises(ValueError, match="not valid base64"):
        parse_master_key("not base64!")


def test_parse_master_key_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        parse_master_key(base64.b64encode(b"short").decode())


async def test_encryptor_roundtrips_content() -> None:
    encryptor = EnvelopeEncryptor(MASTER_KEY)
    content = b"applicant cv bytes"
    encrypted, wrapped_key = encryptor.encrypt(content)
    assert encrypted != content
    assert encryptor.decrypt(encrypted, wrapped_key) == content


async def test_encryptor_uses_a_fresh_nonce_per_call() -> None:
    encryptor = EnvelopeEncryptor(MASTER_KEY)
    first, first_key = encryptor.encrypt(b"same")
    second, second_key = encryptor.encrypt(b"same")
    assert first != second
    assert first_key != second_key


async def test_encryptor_fails_closed_on_tampered_content() -> None:
    encryptor = EnvelopeEncryptor(MASTER_KEY)
    encrypted, wrapped_key = encryptor.encrypt(b"applicant cv bytes")
    tampered = encrypted[:-1] + bytes([encrypted[-1] ^ 0x01])
    with pytest.raises(DecryptionError, match="decryption failed"):
        encryptor.decrypt(tampered, wrapped_key)


async def test_encryptor_fails_closed_on_tampered_data_key() -> None:
    encryptor = EnvelopeEncryptor(MASTER_KEY)
    encrypted, wrapped_key = encryptor.encrypt(b"applicant cv bytes")
    tampered_key = wrapped_key[:-1] + bytes([wrapped_key[-1] ^ 0x01])
    with pytest.raises(DecryptionError, match="decryption failed"):
        encryptor.decrypt(encrypted, tampered_key)


async def test_encryptor_fails_closed_on_master_key_rotation() -> None:
    """Documents encrypted before a rotation stay unreadable under the new
    key: download must fail closed, never serve garbage."""
    old = EnvelopeEncryptor(MASTER_KEY)
    new = EnvelopeEncryptor(b"1" * 32)
    encrypted, wrapped_key = old.encrypt(b"applicant cv bytes")
    with pytest.raises(DecryptionError, match="decryption failed"):
        new.decrypt(encrypted, wrapped_key)


def test_encryptor_rejects_wrong_master_key_length() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        EnvelopeEncryptor(b"short")


def test_ensure_model_eligible_passes_eligible_refs() -> None:
    ensure_model_eligible(
        [DocumentRef("cv", True), DocumentRef("motivation_letter", True)]
    )


def test_ensure_model_eligible_rejects_ineligible_refs() -> None:
    with pytest.raises(IneligibleDocumentError) as exc_info:
        ensure_model_eligible([DocumentRef("cv", True), DocumentRef("payslip", False)])
    assert exc_info.value.type_keys == ["payslip"]


async def exercise_storage_contract(
    gateway: LocalStorageGateway | S3StorageGateway,
) -> None:
    """Write, read back in chunks, probe existence, delete: the same
    sequence the document service runs, over both backends."""
    key = f"users/{uuid.uuid4()}/documents/{uuid.uuid4()}.bin"
    data = os.urandom(200_000)  # multiple read chunks (64 KiB each)
    await gateway.write(key, data)
    assert await gateway.exists(key) is True
    read: AsyncIterator[bytes] = gateway.read(key)
    assert b"".join([chunk async for chunk in read]) == data
    await gateway.delete(key)
    assert await gateway.exists(key) is False


async def test_local_storage_passes_the_contract(tmp_path: Path) -> None:
    await exercise_storage_contract(LocalStorageGateway(tmp_path))


async def test_local_storage_read_of_missing_key_fails() -> None:
    gateway = LocalStorageGateway(Path("."))
    with pytest.raises(StorageError, match="missing storage key"):
        [chunk async for chunk in gateway.read("users/x/documents/missing.bin")]


async def test_local_storage_delete_of_missing_key_fails(tmp_path: Path) -> None:
    gateway = LocalStorageGateway(tmp_path)
    with pytest.raises(StorageError, match="missing storage key"):
        await gateway.delete("users/x/documents/missing.bin")


async def test_local_storage_rejects_key_escaping_root(tmp_path: Path) -> None:
    gateway = LocalStorageGateway(tmp_path)
    with pytest.raises(StorageError, match="escapes root"):
        await gateway.write("../escape.bin", b"data")


@pytest.fixture
async def s3_gateway(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[S3StorageGateway]:
    """In-process moto S3 on an ephemeral port: same wire path as CI.
    moto accepts any credentials; botocore still requires some."""
    import boto3
    from moto.server import ThreadedMotoServer

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    host, port = server.get_host_and_port()
    endpoint = f"http://{host}:{port}"
    bucket = "unghosted-test"
    boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1").create_bucket(
        Bucket=bucket
    )
    gateway = S3StorageGateway(bucket=bucket, region="us-east-1", endpoint_url=endpoint)
    try:
        yield gateway
    finally:
        await gateway.close()
        server.stop()


async def test_s3_storage_passes_the_contract(s3_gateway: S3StorageGateway) -> None:
    await exercise_storage_contract(s3_gateway)


async def test_s3_storage_read_of_missing_key_fails(
    s3_gateway: S3StorageGateway,
) -> None:
    read: AsyncIterator[bytes] = s3_gateway.read("users/x/documents/missing.bin")
    with pytest.raises(StorageError, match="missing storage key"):
        [chunk async for chunk in read]
