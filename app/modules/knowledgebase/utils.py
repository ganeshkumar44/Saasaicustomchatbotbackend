"""
Knowledge base helper utilities for storage and text extraction.
"""

import logging
import re
import uuid
from pathlib import Path

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.config import PROJECT_ROOT
from app.core import messages

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
MAX_KNOWLEDGE_BASE_FILE_SIZE_BYTES = 2 * 1024 * 1024
ALLOWED_FILE_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".csv",
    ".md",
    ".ppt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
KNOWLEDGEBASE_UPLOAD_DIR = PROJECT_ROOT / "uploads" / "knowledgebase"


def validate_knowledgebase_file_size(file_size: int) -> str | None:
    """Return an error message when a knowledge base file exceeds the per-file limit."""
    if file_size > MAX_KNOWLEDGE_BASE_FILE_SIZE_BYTES:
        return messages.KNOWLEDGE_BASE_FILE_SIZE_EXCEEDED
    return None


def apply_knowledgebase_migrations(db_engine: Engine) -> None:
    """Align existing knowledge base tables with the current ORM schema."""
    inspector = inspect(db_engine)
    table_names = inspector.get_table_names()
    statements: list[str] = []

    if "knowledge_chunks" in table_names:
        columns = {
            column["name"] for column in inspector.get_columns("knowledge_chunks")
        }
        if "character_count" not in columns:
            statements.append(
                "ALTER TABLE knowledge_chunks ADD COLUMN character_count INTEGER "
                "NOT NULL DEFAULT 0"
            )

    if "knowledgebase_documents" in table_names:
        document_columns = {
            column["name"] for column in inspector.get_columns("knowledgebase_documents")
        }
        if "processing_started_at" not in document_columns:
            statements.append(
                "ALTER TABLE knowledgebase_documents "
                "ADD COLUMN processing_started_at TIMESTAMPTZ"
            )
        if "processing_completed_at" not in document_columns:
            statements.append(
                "ALTER TABLE knowledgebase_documents "
                "ADD COLUMN processing_completed_at TIMESTAMPTZ"
            )
        if "processing_error" not in document_columns:
            statements.append(
                "ALTER TABLE knowledgebase_documents "
                "ADD COLUMN processing_error TEXT"
            )

        for column in inspector.get_columns("knowledgebase_documents"):
            if column["name"] != "file_path":
                continue
            column_type = str(column.get("type", "")).lower()
            if "varchar(1000)" in column_type or "character varying(1000)" in column_type:
                statements.append(
                    "ALTER TABLE knowledgebase_documents "
                    "ALTER COLUMN file_path TYPE VARCHAR(2000)"
                )
            break

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def _is_table_block(text: str) -> bool:
    """Return True when a text block appears to be a Markdown table."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    pipe_lines = sum(1 for line in lines if "|" in line)
    return pipe_lines >= 2 and lines[1].replace("|", "").replace("-", "").strip() == ""


def _is_atomic_block(text: str) -> bool:
    """Return True when a block should never be split during chunking."""
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.startswith("[Image Description:") and stripped.endswith("]"):
        return True
    if stripped.startswith("[OCR Text]"):
        return True
    if stripped.startswith("[Caption:"):
        return True
    if stripped.startswith("[Speaker Notes]"):
        return True
    if stripped.startswith("--- Page ") or stripped.startswith("--- Slide "):
        return True
    if _is_table_block(stripped):
        return True
    if stripped.startswith("# ") or stripped.startswith("## "):
        return True
    if stripped.startswith("```"):
        return True
    if stripped.startswith("| ") and "|" in stripped:
        return True
    return False


def _split_code_blocks(text: str) -> list[str]:
    """Keep fenced code blocks intact during semantic chunking."""
    pattern = re.compile(r"```[\s\S]*?```", re.MULTILINE)
    parts: list[str] = []
    last_end = 0
    for match in pattern.finditer(text):
        if match.start() > last_end:
            parts.append(text[last_end : match.start()])
        parts.append(match.group(0))
        last_end = match.end()
    if last_end < len(text):
        parts.append(text[last_end:])
    return [part.strip() for part in parts if part.strip()]


def _split_into_atomic_blocks(text: str) -> list[str]:
    """Split merged structured text into atomic blocks for semantic chunking."""
    segments: list[str] = []
    for segment in re.split(r"\n\n+", text.strip()):
        if "```" in segment:
            segments.extend(_split_code_blocks(segment))
        else:
            segments.append(segment)

    atomic_blocks: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if not buffer:
            return
        combined = "\n\n".join(buffer).strip()
        if combined:
            atomic_blocks.append(combined)
        buffer.clear()

    for block in segments:
        stripped = block.strip()
        if not stripped:
            continue
        if _is_atomic_block(stripped):
            flush_buffer()
            atomic_blocks.append(stripped)
            continue
        buffer.append(stripped)

    flush_buffer()
    return atomic_blocks


def _split_character_chunks(
    text: str,
    chunk_size: int,
    overlap: int,
) -> list[dict[str, int | str]]:
    """Split text using the original fixed-size overlapping window."""
    chunks: list[dict[str, int | str]] = []
    step = chunk_size - overlap
    start = 0
    chunk_index = 1

    while start < len(text):
        chunk_text = text[start : start + chunk_size]
        chunks.append(
            {
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "character_count": len(chunk_text),
            }
        )
        if start + chunk_size >= len(text):
            break
        chunk_index += 1
        start += step

    return chunks


def split_text_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, int | str]]:
    """
    Split extracted text into overlapping semantic chunks.

    Keeps tables, headings, image descriptions, and page markers intact whenever
    possible. Falls back to character-based chunking for unstructured content.
    """
    cleaned_text = text.strip()
    if not cleaned_text:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")
    if overlap >= chunk_size:
        raise ValueError("overlap must be less than chunk_size")

    atomic_blocks = _split_into_atomic_blocks(cleaned_text)
    if len(atomic_blocks) <= 1:
        return _split_character_chunks(cleaned_text, chunk_size, overlap)

    chunks: list[dict[str, int | str]] = []
    current_parts: list[str] = []
    current_length = 0
    chunk_index = 1
    previous_chunk_text = ""

    def flush_chunk() -> None:
        nonlocal chunk_index, current_parts, current_length, previous_chunk_text
        if not current_parts:
            return
        chunk_text = "\n\n".join(current_parts).strip()
        if overlap > 0 and previous_chunk_text and chunks:
            prefix = previous_chunk_text[-overlap:]
            if prefix and not chunk_text.startswith(prefix):
                chunk_text = f"{prefix}{chunk_text}"
        if len(chunk_text) > chunk_size and len(current_parts) == 1:
            sub_chunks = _split_character_chunks(chunk_text, chunk_size, overlap)
            chunks.extend(sub_chunks)
            if sub_chunks:
                previous_chunk_text = sub_chunks[-1]["chunk_text"]
            current_parts = []
            current_length = 0
            chunk_index = len(chunks) + 1
            return
        chunks.append(
            {
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "character_count": len(chunk_text),
            }
        )
        previous_chunk_text = chunk_text
        chunk_index += 1
        current_parts = []
        current_length = 0

    for block in atomic_blocks:
        block_length = len(block)
        separator_length = 2 if current_parts else 0
        projected_length = current_length + separator_length + block_length

        if current_parts and projected_length > chunk_size:
            flush_chunk()

        if not current_parts and overlap > 0 and previous_chunk_text and chunks:
            prefix = previous_chunk_text[-overlap:]
            if prefix and not block.startswith(prefix):
                block = f"{prefix}{block}"

        current_parts.append(block)
        current_length = len("\n\n".join(current_parts))

    flush_chunk()

    if not chunks:
        return _split_character_chunks(cleaned_text, chunk_size, overlap)

    for index, chunk in enumerate(chunks, start=1):
        chunk["chunk_index"] = index

    return chunks


def normalize_extracted_text(text: str) -> str:
    """Normalize text for storage and future vectorization."""
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def get_file_extension(filename: str) -> str:
    """Return the lowercase file extension including the leading dot."""
    return Path(filename).suffix.lower()


def normalize_file_type(file_type: str | None) -> str:
    """
    Normalize a stored or incoming file type to a lowercase extension with a leading dot.

    Database rows store extensions without a leading dot (e.g. ``pdf``), while
    extractors expect dotted values (e.g. ``.pdf``).
    """
    if not file_type:
        return ""

    normalized = file_type.strip().lower()
    if not normalized:
        return ""
    return normalized if normalized.startswith(".") else f".{normalized}"


def is_allowed_file_type(filename: str) -> bool:
    """Return True when the uploaded file has a supported extension."""
    return get_file_extension(filename) in ALLOWED_FILE_EXTENSIONS


def build_chatbot_upload_dir(chatbot_id: int) -> Path:
    """Create and return the upload directory for a chatbot."""
    upload_dir = KNOWLEDGEBASE_UPLOAD_DIR / str(chatbot_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def save_uploaded_file(chatbot_id: int, filename: str, content: bytes) -> Path:
    """Persist an uploaded file and return the saved path."""
    upload_dir = build_chatbot_upload_dir(chatbot_id)
    safe_name = Path(filename).name
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = upload_dir / unique_name
    file_path.write_bytes(content)
    return file_path


def extract_file_text(file_path: Path, file_type: str) -> str:
    """Extract structured searchable text from a supported file type."""
    from app.modules.knowledgebase.extraction.registry import extract_structured_file_text

    return extract_structured_file_text(file_path, normalize_file_type(file_type))


def extract_file_text_from_storage(
    *,
    file_path: str,
    file_type: str,
) -> str:
    """
    Extract text from a knowledge base file stored on S3 or legacy local disk.

    S3 files are downloaded to a temporary path for processing and removed
    automatically after extraction completes.
    """
    from app.modules.knowledgebase.s3_storage import (
        download_knowledgebase_file_to_temp,
        is_knowledgebase_s3_url,
    )

    normalized_file_type = normalize_file_type(file_type)

    if is_knowledgebase_s3_url(file_path):
        with download_knowledgebase_file_to_temp(
            file_path,
            suffix=normalized_file_type,
        ) as temp_path:
            return extract_file_text(temp_path, normalized_file_type)

    local_path = Path(file_path)
    if local_path.exists():
        return extract_file_text(local_path, normalized_file_type)

    raise FileNotFoundError(f"Knowledge base file not found: {file_path}")


async def extract_url_text(url: str) -> str:
    """
    Extract readable text from a website URL.

    Uses Playwright to render JavaScript-heavy pages, crawls same-domain
    internal links, and merges cleaned content for semantic chunking.
    """
    from app.modules.knowledgebase.url_ingestion.service import extract_url_text as ingest_url

    return await ingest_url(url)
