from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.cors import DynamicCORSMiddleware
from app.core.database import Base, engine
from app.modules.auth.routes import router as auth_router, signup_router
from app.modules.auth.utils import apply_verification_migrations
from app.modules.chatbot.routes import router as chatbot_router
from app.modules.chatbot_settings.routes import router as chatbot_settings_router
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
from app.modules.user_details.utils import apply_user_account_migrations, sync_existing_user_details
from app.modules.chat_analysis.utils import sync_existing_chat_analysis
from app.modules.theme.utils import sync_existing_user_themes
from app.modules.notification.utils import sync_existing_notification_settings

# Import all ORM models so they register with Base.metadata before create_all().
import app.modules.auth.model  # noqa: F401
import app.modules.chatbot.model  # noqa: F401
import app.modules.knowledgebase.model  # noqa: F401
import app.modules.chat_sessions.model  # noqa: F401
import app.modules.chat_messages.model  # noqa: F401
import app.modules.knowledge_chunks.model  # noqa: F401
import app.modules.user_details.model  # noqa: F401
import app.modules.widget.model  # noqa: F401
import app.modules.chat_analysis.model  # noqa: F401
import app.modules.theme.model  # noqa: F401
import app.modules.login_history.model  # noqa: F401
import app.modules.notification.model  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup if they do not already exist."""
    get_settings().validate()
    apply_verification_migrations(engine)
    apply_user_account_migrations(engine)
    apply_chatbot_migrations(engine)
    Base.metadata.create_all(bind=engine)
    apply_chat_session_migrations(engine)
    apply_chat_message_migrations(engine)
    apply_knowledgebase_migrations(engine)
    sync_existing_user_details(engine)
    sync_existing_chat_analysis(engine)
    sync_existing_user_themes(engine)
    sync_existing_notification_settings(engine)
    yield


app = FastAPI(
    title="Saas AI Custom Chatbot API",
    description="API for the Saas AICustom Chatbot",
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

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
