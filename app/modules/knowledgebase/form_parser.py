"""Multipart form parsing helpers for knowledge base uploads."""

from __future__ import annotations

from fastapi import Request, UploadFile

from app.modules.knowledgebase.service import UploadedFilePayload


def _is_upload_file(value: object) -> bool:
    """Return True when a form value is an uploaded file."""
    return isinstance(value, UploadFile) or (
        hasattr(value, "read") and hasattr(value, "filename")
    )


async def parse_knowledgebase_multipart_form(
    request: Request,
) -> tuple[list[UploadedFilePayload], list[str]]:
    """
    Parse knowledge base upload form data.

    Swagger UI may send empty strings for optional file fields; those values are
    ignored so URL-only uploads work without validation errors.
    """
    form = await request.form()
    file_payloads: list[UploadedFilePayload] = []
    urls: list[str] = []

    for key, value in form.multi_items():
        if key == "files":
            if not _is_upload_file(value) or not value.filename:
                continue
            content = await value.read()
            if not content:
                continue
            file_payloads.append(
                UploadedFilePayload(
                    filename=value.filename,
                    content=content,
                )
            )
            continue

        if key == "urls":
            normalized_url = str(value).strip()
            if normalized_url:
                urls.append(normalized_url)

    return file_payloads, urls
