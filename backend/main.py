"""Travel Invoice Assistant – FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from routers.health import router as health_router
from routers.settings import router as settings_router
from routers.trips import router as trips_router
from routers.documents import router as documents_router
from routers.analysis import router as analysis_router
from routers.exports import router as exports_router
from routers.system import router as system_router
from routers.dashboard import router as dashboard_router

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Local travel invoice intelligent sorting assistant",
)

# CORS – allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(settings_router)
app.include_router(trips_router)
app.include_router(documents_router)
app.include_router(analysis_router)
app.include_router(exports_router)
app.include_router(system_router)
app.include_router(dashboard_router)


@app.on_event("startup")
def on_startup():
    init_db()
    print(f"[startup] Database initialized at {settings.DB_PATH}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )