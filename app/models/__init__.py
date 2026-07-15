"""
Central ORM model registry for Alembic and application startup.

Models continue to live under ``app/modules/*/model.py``. This package only
imports them so every table registers on ``Base.metadata`` before:
  - ``alembic revision --autogenerate``
  - application lifespan (seed / sync helpers)

Importing ``app.models`` is enough; you do not need to import each module
individually elsewhere for metadata registration.
"""

# Auth & account
import app.modules.auth.model  # noqa: F401
import app.modules.user_details.model  # noqa: F401
import app.modules.login_history.model  # noqa: F401
import app.modules.theme.model  # noqa: F401
import app.modules.notification.model  # noqa: F401

# Chatbots & knowledge
import app.modules.chatbot.model  # noqa: F401
import app.modules.prompt.model  # noqa: F401
import app.modules.knowledgebase.model  # noqa: F401
import app.modules.knowledge_chunks.model  # noqa: F401
import app.modules.widget.model  # noqa: F401

# Conversations
import app.modules.chat_sessions.model  # noqa: F401
import app.modules.chat_messages.model  # noqa: F401
import app.modules.chat_analysis.model  # noqa: F401
import app.modules.playground.model  # noqa: F401

# Plans, billing, usage
import app.modules.plan_master.model  # noqa: F401
import app.modules.user_plan.model  # noqa: F401
import app.modules.billing.model  # noqa: F401
import app.modules.chatbot_usage.model  # noqa: F401
import app.modules.feedback.model  # noqa: F401

from app.core.database import Base

# Expose metadata for Alembic / tooling.
metadata = Base.metadata

__all__ = ["Base", "metadata"]
