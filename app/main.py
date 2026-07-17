from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.cors import DynamicCORSMiddleware
from app.core.database import engine
from app.core.migrations import run_pending_migrations
from app.modules.auth.routes import router as auth_router, signup_router
from app.modules.auth.utils import apply_verification_migrations
from app.modules.chatbot.routes import router as chatbot_router
from app.modules.chatbot_settings.routes import router as chatbot_settings_router
from app.modules.prompt.routes import router as prompt_router
from app.modules.chatbot.utils import apply_chatbot_migrations
from app.modules.knowledgebase.utils import apply_knowledgebase_migrations
from app.modules.chat_sessions.utils import apply_chat_session_migrations
from app.modules.chat_messages.utils import apply_chat_message_migrations
from app.modules.health.routes import router as health_router
from app.modules.knowledgebase.routes import router as knowledgebase_router
from app.modules.chat_messages.routes import router as chat_messages_router
from app.modules.knowledge_chunks.routes import router as knowledge_chunks_router
from app.modules.widget.routes import router as widget_router, static_router as widget_static_router
from app.rag.routes import router as rag_router
from app.modules.ai.routes import router as ai_router
from app.modules.user_details.routes import router as user_details_router
from app.modules.dashboard.routes import router as dashboard_router
from app.modules.chatbot_analysis.routes import router as chatbot_analysis_router
from app.modules.graphs.routes import router as graphs_router
from app.modules.chat_history.routes import router as chat_history_router
from app.modules.theme.routes import router as theme_router
from app.modules.notification.routes import router as notification_router
from app.modules.manage_users.routes import router as manage_users_router
from app.modules.manage_chatbot.routes import router as manage_chatbot_router
from app.modules.playground.routes import router as playground_router
from app.modules.chatbot_usage.routes import router as chatbot_usage_router
from app.modules.feedback.routes import router as feedback_router
from app.modules.contact.routes import router as contact_router
from app.modules.billing.routes import router as billing_router
from app.modules.user_details.utils import apply_user_account_migrations, sync_existing_user_details
from app.modules.chat_analysis.utils import sync_existing_chat_analysis
from app.modules.theme.utils import sync_existing_user_themes
from app.modules.notification.utils import sync_existing_notification_settings
from app.modules.user_plan.utils import (
    apply_user_plan_migrations,
    backfill_user_plan_plan_ids,
    backfill_user_plan_subscription_fields,
    sync_existing_user_plans,
)
from app.modules.plan_master.utils import (
    apply_plan_master_migrations,
    backfill_plan_master_billing_fields,
    seed_plan_master,
)
from app.modules.billing.migrations import apply_billing_migrations
from app.modules.prompt.utils import apply_prompt_migrations
from app.modules.chatbot_usage.utils import sync_existing_chatbot_usage

# Register every ORM model on Base.metadata (used by tooling / relationships).
# Schema creation/alteration is owned by Alembic — not create_all().
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup / shutdown.

    On every start (including live deploy):
      1. ``run_pending_migrations()`` → ``alembic upgrade head`` (AUTO_RUN_MIGRATIONS)
      2. Legacy idempotent column backfills + data seeds / sync helpers
    """
    get_settings().validate()
    # Apply committed Alembic revisions before serving traffic (live-safe: skips if at head).
    run_pending_migrations()
    # Legacy idempotent ALTERs retained during Alembic rollout so older DBs
    # that have not been upgraded yet still receive missing columns safely.
    # New schema changes must be added via Alembic revisions only.
    apply_verification_migrations(engine)
    apply_user_account_migrations(engine)
    apply_chatbot_migrations(engine)
    apply_plan_master_migrations(engine)
    seed_plan_master(engine)
    backfill_plan_master_billing_fields(engine)
    apply_billing_migrations(engine)
    apply_chat_session_migrations(engine)
    apply_chat_message_migrations(engine)
    apply_knowledgebase_migrations(engine)
    apply_prompt_migrations(engine)
    apply_user_plan_migrations(engine)
    backfill_user_plan_plan_ids(engine)
    backfill_user_plan_subscription_fields(engine)
    sync_existing_user_details(engine)
    sync_existing_chat_analysis(engine)
    sync_existing_user_themes(engine)
    sync_existing_notification_settings(engine)
    sync_existing_user_plans(engine)
    sync_existing_chatbot_usage(engine)
    yield


app = FastAPI(
    title="NexGenChat Chatbot API",
    description="API for the NexGenChat Chatbot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(DynamicCORSMiddleware)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(signup_router)
app.include_router(chatbot_router)
app.include_router(chatbot_settings_router)
app.include_router(prompt_router)
app.include_router(knowledgebase_router)
app.include_router(widget_router)
app.include_router(widget_static_router)
app.include_router(chat_messages_router)
app.include_router(knowledge_chunks_router)
app.include_router(rag_router)
app.include_router(ai_router)
app.include_router(user_details_router)
app.include_router(dashboard_router)
app.include_router(chatbot_analysis_router)
app.include_router(graphs_router)
app.include_router(chat_history_router)
app.include_router(theme_router)
app.include_router(notification_router)
app.include_router(manage_users_router)
app.include_router(manage_chatbot_router)
app.include_router(playground_router)
app.include_router(chatbot_usage_router)
app.include_router(feedback_router)
app.include_router(contact_router)
app.include_router(billing_router)

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
