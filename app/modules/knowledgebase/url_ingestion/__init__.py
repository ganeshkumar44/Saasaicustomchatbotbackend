"""Playwright-based website URL ingestion for the knowledge base."""

from app.modules.knowledgebase.url_ingestion.service import extract_url_text

__all__ = ["extract_url_text"]
