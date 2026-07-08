"""AWS S3 storage helpers for knowledge base file uploads."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

from botocore.exceptions import BotoCoreError, ClientError

from app.core import messages
from app.modules.user_details.utils import get_s3_client

logger = logging.getLogger(__name__)

KNOWLEDGEBASE_S3_PREFIX = "knowledgebase/"

KNOWLEDGEBASE_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    ),
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _get_aws_setting(name: str) -> str:
    return os.getenv(name, "").strip()


def build_knowledgebase_object_key(chatbot_id: int, filename: str) -> str:
    """Build a unique S3 object key for a knowledge base file upload."""
    safe_name = Path(filename).name
    return (
        f"{KNOWLEDGEBASE_S3_PREFIX}chatbot_{chatbot_id}/"
        f"{uuid.uuid4().hex}_{safe_name}"
    )


def build_knowledgebase_public_url(object_key: str) -> str:
    """Build the public S3 URL for a stored knowledge base object."""
    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    region = _get_aws_setting("AWS_REGION")
    return f"https://{bucket_name}.s3.{region}.amazonaws.com/{object_key}"


def resolve_knowledgebase_content_type(file_type: str) -> str:
    """Return an appropriate content type for a knowledge base file extension."""
    extension = file_type if file_type.startswith(".") else f".{file_type}"
    return KNOWLEDGEBASE_CONTENT_TYPES.get(extension.lower(), "application/octet-stream")


def is_knowledgebase_s3_url(file_path: str | None) -> bool:
    """Return True when the stored file path points to a managed S3 object."""
    return extract_knowledgebase_object_key(file_path) is not None


def extract_knowledgebase_object_key(file_url: str | None) -> str | None:
    """Extract the S3 object key from a stored knowledge base file URL."""
    if not file_url or not file_url.strip():
        return None

    parsed = urlparse(file_url.strip())
    object_key = parsed.path.lstrip("/")
    if not object_key.startswith(KNOWLEDGEBASE_S3_PREFIX):
        return None

    return object_key


def upload_knowledgebase_file_to_s3(
    *,
    content: bytes,
    object_key: str,
    content_type: str,
) -> str:
    """Upload a knowledge base file to S3 and return its public URL."""
    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    if not bucket_name:
        raise RuntimeError(messages.KNOWLEDGE_BASE_UPLOAD_FAILED)

    client = get_s3_client()
    upload_content_type = content_type.split(";", 1)[0].strip().lower()

    try:
        client.upload_fileobj(
            BytesIO(content),
            bucket_name,
            object_key,
            ExtraArgs={
                "ContentType": upload_content_type or "application/octet-stream",
            },
        )
    except (BotoCoreError, ClientError) as exc:
        logger.exception(
            "Failed to upload knowledge base file to S3 object_key=%s",
            object_key,
        )
        raise RuntimeError(messages.KNOWLEDGE_BASE_UPLOAD_FAILED) from exc

    return build_knowledgebase_public_url(object_key)


def delete_knowledgebase_file_from_s3(file_url: str | None) -> None:
    """Delete a knowledge base file object from S3 when possible."""
    object_key = extract_knowledgebase_object_key(file_url)
    if object_key is None:
        return

    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    if not bucket_name:
        logger.warning(
            "Skipping knowledge base file delete; AWS_BUCKET_NAME is not configured",
        )
        return

    try:
        get_s3_client().delete_object(Bucket=bucket_name, Key=object_key)
        logger.info("Deleted knowledge base file from S3 object_key=%s", object_key)
    except (BotoCoreError, ClientError):
        logger.exception(
            "Failed to delete knowledge base file from S3 object_key=%s",
            object_key,
        )


def delete_knowledgebase_file_from_s3_strict(file_url: str | None) -> None:
    """Delete a knowledge base file from S3 and raise when deletion fails."""
    object_key = extract_knowledgebase_object_key(file_url)
    if object_key is None:
        return

    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    if not bucket_name:
        raise RuntimeError(messages.KNOWLEDGE_BASE_DELETE_FAILED)

    try:
        get_s3_client().delete_object(Bucket=bucket_name, Key=object_key)
        logger.info("Deleted knowledge base file from S3 object_key=%s", object_key)
    except (BotoCoreError, ClientError) as exc:
        logger.exception(
            "Failed to delete knowledge base file from S3 object_key=%s",
            object_key,
        )
        raise RuntimeError(messages.KNOWLEDGE_BASE_DELETE_FAILED) from exc


def download_knowledgebase_file(*, file_url: str) -> bytes:
    """Download a knowledge base file from S3 and return its bytes."""
    object_key = extract_knowledgebase_object_key(file_url)
    if object_key is None:
        raise RuntimeError(messages.KNOWLEDGE_BASE_DOWNLOAD_FAILED)

    bucket_name = _get_aws_setting("AWS_BUCKET_NAME")
    if not bucket_name:
        raise RuntimeError(messages.KNOWLEDGE_BASE_DOWNLOAD_FAILED)

    buffer = BytesIO()
    try:
        get_s3_client().download_fileobj(bucket_name, object_key, buffer)
    except (BotoCoreError, ClientError) as exc:
        logger.exception(
            "Failed to download knowledge base file from S3 object_key=%s",
            object_key,
        )
        raise RuntimeError(messages.KNOWLEDGE_BASE_DOWNLOAD_FAILED) from exc

    return buffer.getvalue()


@contextmanager
def download_knowledgebase_file_to_temp(
    file_url: str,
    *,
    suffix: str,
) -> Iterator[Path]:
    """
    Download a knowledge base file from S3 into a temporary local file.

    The temporary file is deleted automatically when the context exits.
    """
    file_bytes = download_knowledgebase_file(file_url=file_url)
    normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    temp_file = tempfile.NamedTemporaryFile(
        suffix=normalized_suffix,
        delete=False,
    )
    temp_path = Path(temp_file.name)

    try:
        temp_file.write(file_bytes)
        temp_file.close()
        yield temp_path
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                logger.exception(
                    "Failed to delete temporary knowledge base file %s",
                    temp_path,
                )
