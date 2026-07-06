"""Structured document extraction for the knowledge base ingestion pipeline."""

from app.modules.knowledgebase.extraction.registry import extract_structured_file_text

__all__ = ["extract_structured_file_text"]