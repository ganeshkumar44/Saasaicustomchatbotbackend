"""
Dynamic CORS middleware.

Allows origins from CORS_ORIGINS (.env) and, for widget routes,
origins listed in the chatbot's allowed_domains value stored in the database.
"""

import re

from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.modules.chatbot.model import ChatbotSettings
from app.modules.widget.utils import get_chatbot_settings_by_public_key

WIDGET_CONFIG_PATH_RE = re.compile(r"^/v1/widget/config/([^/]+)$")
WIDGET_CHAT_PATH = "/v1/widget/chat"
WIDGET_SESSION_START_PATH = "/v1/widget/session/start"
WIDGET_VISITOR_INFO_PATH = "/v1/widget/visitor-info"
WIDGET_CHAT_HISTORY_PATH_RE = re.compile(r"^/v1/widget/chat-history/[^/]+$")


def normalize_origin(origin: str) -> str:
    """Normalize an origin or domain URL for comparison."""
    return origin.strip().rstrip("/").lower()


def parse_allowed_domains(allowed_domains: str) -> set[str]:
    """Parse comma-separated allowed domain values from the database."""
    return {
        normalize_origin(domain)
        for domain in allowed_domains.split(",")
        if domain.strip()
    }


def is_origin_allowed_for_widget(public_key: str, origin: str) -> bool:
    """Return True when origin is listed in the chatbot's allowed_domains."""
    db = SessionLocal()
    try:
        settings = get_chatbot_settings_by_public_key(db, public_key)
        if settings is None:
            return False
        return normalize_origin(origin) in parse_allowed_domains(settings.allowed_domains)
    finally:
        db.close()


def is_origin_in_any_allowed_domains(origin: str) -> bool:
    """Return True when origin matches allowed_domains of any published chatbot."""
    db = SessionLocal()
    try:
        normalized_origin = normalize_origin(origin)
        allowed_domains_list = db.execute(
            select(ChatbotSettings.allowed_domains)
        ).scalars().all()
        return any(
            normalized_origin in parse_allowed_domains(allowed_domains)
            for allowed_domains in allowed_domains_list
        )
    finally:
        db.close()


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    """Apply CORS for .env origins and per-chatbot DB allowed_domains on widget routes."""

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin")

        if request.method == "OPTIONS" and origin and self._is_allowed(request, origin):
            return Response(status_code=200, headers=self._cors_headers(origin))

        response = await call_next(request)

        if origin and self._is_allowed(request, origin):
            for header, value in self._cors_headers(origin).items():
                response.headers[header] = value

        return response

    def _is_allowed(self, request: Request, origin: str) -> bool:
        settings = get_settings()
        normalized_origin = normalize_origin(origin)

        env_origins = {normalize_origin(item) for item in settings.CORS_ORIGINS}
        if normalized_origin in env_origins:
            return True

        if request.url.path in (
            WIDGET_CHAT_PATH,
            WIDGET_SESSION_START_PATH,
            WIDGET_VISITOR_INFO_PATH,
        ):
            return is_origin_in_any_allowed_domains(origin)

        if WIDGET_CHAT_HISTORY_PATH_RE.match(request.url.path):
            return is_origin_in_any_allowed_domains(origin)

        match = WIDGET_CONFIG_PATH_RE.match(request.url.path)
        if match:
            return is_origin_allowed_for_widget(match.group(1), origin)

        return False

    @staticmethod
    def _cors_headers(origin: str) -> dict[str, str]:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        }
