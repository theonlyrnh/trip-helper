from .health import router as health_router
from .settings import router as settings_router
from .trips import router as trips_router
from .documents import router as documents_router
from .analysis import router as analysis_router
from .exports import router as exports_router
from .system import router as system_router
from .dashboard import router as dashboard_router

__all__ = [
    "health_router",
    "settings_router",
    "trips_router",
    "documents_router",
    "analysis_router",
    "exports_router",
    "system_router",
    "dashboard_router",
]