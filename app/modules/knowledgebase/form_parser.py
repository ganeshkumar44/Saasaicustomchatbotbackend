"""Multipart form parsing helpers for knowledge base uploads."""

from __future__ import annotations

from fastapi import Request, UploadFile

from app.modules.knowledgebase.service import UploadedFilePayload


def _is_upload_file(value: object) -> bool:
    """Return True when a form value is an uploaded file."""
    return isinstance(value, UploadFile) or (
        hasattr(value, "read") and hasattr(value, "filename")
    )


async def _parse_files_and_urls(
    form,
) -> tuple[list[UploadedFilePayload], list[str]]:
    """Extract uploaded files and website URLs from a multipart form."""
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


async def parse_knowledgebase_multipart_form(
    request: Request,
) -> tuple[list[UploadedFilePayload], list[str]]:
    """
    Parse knowledge base upload form data.

    Swagger UI may send empty strings for optional file fields; those values are
    ignored so URL-only uploads work without validation errors.
    """
    form = await request.form()
    return await _parse_files_and_urls(form)


async def parse_knowledge_base_settings_form(
    request: Request,
) -> tuple[int, list[int], list[UploadedFilePayload], list[str]]:
    """
    Parse chatbot settings knowledge base update form data.

    Used by PUT /v1/chatbots/knowledge-base for file/URL updates during
    chatbot settings. Ignores empty Swagger file placeholders.
    """
    form = await request.form()

    chatbot_id_raw = form.get("chatbot_id")
    if chatbot_id_raw is None or str(chatbot_id_raw).strip() == "":
        raise ValueError("chatbot_id is required")
    chatbot_id = int(chatbot_id_raw)

    delete_document_ids: list[int] = []
    for key, value in form.multi_items():
        if key != "delete_document_ids":
            continue
        raw_id = str(value).strip()
        if not raw_id:
            continue
        try:
            delete_document_ids.append(int(raw_id))
        except ValueError as exc:
            raise ValueError(f"Invalid delete_document_ids value: {raw_id}") from exc

    file_payloads, urls = await _parse_files_and_urls(form)
    return chatbot_id, delete_document_ids, file_payloads, urls
