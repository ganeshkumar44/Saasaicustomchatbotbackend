from fastapi import FastAPI
from app.modules.health.routes import router as health_router
from app.modules.auth.routes import router as auth_router

app = FastAPI(
    title="My Project API",
    version="1.0.0"
)

app.include_router(health_router)
app.include_router(auth_router)