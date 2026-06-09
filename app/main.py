from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import Base, engine
from app.modules.auth.routes import router as auth_router, signup_router
from app.modules.auth.utils import apply_verification_migrations
from app.modules.chatbot.routes import router as chatbot_router
from app.modules.chatbot.utils import apply_chatbot_migrations
from app.modules.health.routes import router as health_router

# Import all ORM models so they register with Base.metadata before create_all().
import app.modules.auth.model  # noqa: F401
import app.modules.chatbot.model  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup if they do not already exist."""
    get_settings().validate()
    apply_verification_migrations(engine)
    apply_chatbot_migrations(engine)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Saas AI Custom Chatbot API",
    description="API for the Saas AICustom Chatbot",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(signup_router)
app.include_router(chatbot_router)
