"""
Knowledge base helper utilities for storage and text extraction.
"""

import logging
import re
import subprocess
import uuid
from pathlib import Path

import fitz
import pandas as pd
import requests
from bs4 import BeautifulSoup
from docx import Document
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
ALLOWED_FILE_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".csv", ".md"}
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
KNOWLEDGEBASE_UPLOAD_DIR = PROJECT_ROOT / "uploads" / "knowledgebase"
URL_FETCH_TIMEOUT_SECONDS = 30
MIN_STATIC_TEXT_LENGTH = 200


def apply_knowledgebase_migrations(db_engine: Engine) -> None:
    """Align existing knowledge base tables with the current ORM schema."""
    inspector = inspect(db_engine)
    if "knowledge_chunks" not in inspector.get_table_names():
        return

    columns = {
        column["name"] for column in inspector.get_columns("knowledge_chunks")
    }
    statements: list[str] = []

    if "character_count" not in columns:
        statements.append(
            "ALTER TABLE knowledge_chunks ADD COLUMN character_count INTEGER "
            "NOT NULL DEFAULT 0"
        )

    if not statements:
        return

    with db_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def split_text_into_chunks(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, int | str]]:
    """
    Split large extracted text into smaller overlapping chunks.

    Each chunk overlaps the previous chunk by the configured number of characters
    to preserve context for future embedding generation and vector search.
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

    chunks: list[dict[str, int | str]] = []
    step = chunk_size - overlap
    start = 0
    chunk_index = 1

    while start < len(cleaned_text):
        chunk_text = cleaned_text[start : start + chunk_size]
        chunks.append(
            {
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "character_count": len(chunk_text),
            }
        )
        if start + chunk_size >= len(cleaned_text):
            break
        chunk_index += 1
        start += step

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


def extract_pdf_text(file_path: Path) -> str:
    """Extract readable text from a PDF file."""
    text_parts: list[str] = []
    with fitz.open(file_path) as pdf_document:
        for page in pdf_document:
            text_parts.append(page.get_text("text"))
    return normalize_extracted_text("\n".join(text_parts))


def extract_docx_text(file_path: Path) -> str:
    """Extract readable text from a DOCX file."""
    document = Document(file_path)
    paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    return normalize_extracted_text("\n".join(paragraphs))


def extract_doc_text(file_path: Path) -> str:
    """Extract readable text from a legacy DOC file."""
    try:
        result = subprocess.run(
            ["antiword", str(file_path)],
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return normalize_extracted_text(result.stdout)
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        logger.warning(
            "DOC extraction fallback used for %s; install antiword for better results.",
            file_path,
        )
        raw_bytes = file_path.read_bytes()
        decoded = raw_bytes.decode("utf-8", errors="ignore")
        ascii_text = re.sub(r"[^\x20-\x7E\n]", " ", decoded)
        return normalize_extracted_text(ascii_text)


def extract_txt_text(file_path: Path) -> str:
    """Extract readable text from a plain text file."""
    return normalize_extracted_text(file_path.read_text(encoding="utf-8", errors="ignore"))


def extract_md_text(file_path: Path) -> str:
    """Extract readable text from a Markdown file."""
    return extract_txt_text(file_path)


def extract_csv_text(file_path: Path) -> str:
    """Extract readable text from a CSV file."""
    dataframe = pd.read_csv(file_path)
    return normalize_extracted_text(dataframe.to_csv(index=False))


def extract_file_text(file_path: Path, file_type: str) -> str:
    """Extract text from a supported file type."""
    extractors = {
        ".pdf": extract_pdf_text,
        ".doc": extract_doc_text,
        ".docx": extract_docx_text,
        ".txt": extract_txt_text,
        ".csv": extract_csv_text,
        ".md": extract_md_text,
    }
    extractor = extractors.get(file_type)
    if not extractor:
        raise ValueError(f"Unsupported file type: {file_type}")
    return extractor(file_path)


def _extract_visible_text_from_html(html_content: str) -> str:
    """Extract visible text content from HTML."""
    soup = BeautifulSoup(html_content, "html.parser")
    for element in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        element.decompose()
    text = soup.get_text(separator="\n")
    return normalize_extracted_text(text)


def extract_static_url_text(url: str) -> str:
    """Fetch and extract text from a static website URL."""
    response = requests.get(
        url,
        timeout=URL_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SaaSChatbotBot/1.0)"},
    )
    response.raise_for_status()
    return _extract_visible_text_from_html(response.text)


def extract_dynamic_url_text(url: str) -> str:
    """Extract text from JavaScript-rendered websites using Playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60000)
            html_content = page.content()
        finally:
            browser.close()
    return _extract_visible_text_from_html(html_content)


def extract_url_text(url: str) -> str:
    """
    Extract readable text from a website URL.

    Uses static HTML parsing first, then Playwright for dynamic pages.
    """
    static_text = extract_static_url_text(url)
    if len(static_text) >= MIN_STATIC_TEXT_LENGTH:
        return static_text

    try:
        dynamic_text = extract_dynamic_url_text(url)
        if dynamic_text:
            return dynamic_text
    except Exception:
        logger.exception("Dynamic URL extraction failed for %s", url)

    return static_text
