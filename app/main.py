from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import Base, engine
from app.modules.auth.routes import router as auth_router, signup_router
from app.modules.auth.utils import apply_verification_migrations
from app.modules.health.routes import router as health_router

# Import all ORM models so they register with Base.metadata before create_all().
import app.modules.auth.model  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup if they do not already exist."""
    get_settings().validate()
    apply_verification_migrations(engine)
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="My Project API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(signup_router)
