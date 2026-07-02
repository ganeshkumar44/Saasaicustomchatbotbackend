"""
Widget visitor helper utilities.
"""

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.widget.model import WidgetVisitor

logger = logging.getLogger(__name__)


def generate_visitor_key() -> str:
    """Generate a unique widget visitor identifier."""
    return f"vis_{secrets.token_hex(6)}"


def generate_unique_visitor_key(db: Session) -> str:
    """Generate a visitor key that does not already exist in the database."""
    while True:
        visitor_key = generate_visitor_key()
        existing = db.execute(
            select(WidgetVisitor.id).where(WidgetVisitor.visitor_key == visitor_key)
        ).scalar_one_or_none()
        if existing is None:
            return visitor_key


def get_widget_visitor_by_key(
    db: Session,
    chatbot_id: int,
    visitor_key: str,
) -> WidgetVisitor | None:
    """Return a widget visitor for the given chatbot and visitor key."""
    return db.execute(
        select(WidgetVisitor).where(
            WidgetVisitor.chatbot_id == chatbot_id,
            WidgetVisitor.visitor_key == visitor_key,
        )
    ).scalar_one_or_none()


def save_widget_visitor(
    db: Session,
    *,
    chatbot_id: int,
    visitor_key: str,
    visitor_name: str,
    visitor_email: str,
    visitor_phone: str,
) -> tuple[WidgetVisitor, bool]:
    """Create or update a persistent widget visitor profile.

    Returns the visitor record and whether a new profile was created.
    """
    now = datetime.now(timezone.utc)
    visitor = get_widget_visitor_by_key(db, chatbot_id, visitor_key)
    created = False

    if visitor is None:
        created = True
        visitor = WidgetVisitor(
            chatbot_id=chatbot_id,
            visitor_key=visitor_key,
            visitor_name=visitor_name,
            visitor_email=visitor_email,
            visitor_phone=visitor_phone,
        )
        db.add(visitor)
        logger.info(
            "Created widget visitor visitor_key=%s chatbot_id=%s",
            visitor_key,
            chatbot_id,
        )
    else:
        visitor.visitor_name = visitor_name
        visitor.visitor_email = visitor_email
        visitor.visitor_phone = visitor_phone
        visitor.updated_at = now
        logger.info(
            "Updated widget visitor visitor_key=%s chatbot_id=%s",
            visitor_key,
            chatbot_id,
        )

    db.commit()
    db.refresh(visitor)
    return visitor, created
