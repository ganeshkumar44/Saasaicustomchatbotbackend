"""
Direct image file extraction using Gemini Vision.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.modules.knowledgebase.extraction.models import StructuredDocument
from app.modules.knowledgebase.extraction.vision import describe_image_bytes, reset_vision_session

logger = logging.getLogger(__name__)

IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def extract_image_structured(file_path: Path, file_type: str) -> StructuredDocument:
    """Analyze a standalone image file and store a searchable description."""
    document = StructuredDocument()
    reset_vision_session()
    image_bytes = file_path.read_bytes()
    mime_type = IMAGE_MIME_TYPES.get(file_type, "image/png")

    description = describe_image_bytes(image_bytes, mime_type)
    if description:
        document.add("image_description", description)
    else:
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(file_path)
            ocr_text = pytesseract.image_to_string(image).strip()
            if ocr_text:
                document.add("ocr_text", ocr_text)
        except Exception:
            logger.exception("Fallback OCR failed for image file=%s", file_path)

    if not document.blocks:
        document.add(
            "paragraph",
            f"Image file uploaded: {file_path.name}. No description could be generated.",
        )

    return document
