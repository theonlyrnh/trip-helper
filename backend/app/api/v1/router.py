"""Versioned API assembly."""

from fastapi import APIRouter

from . import auth, dashboard, documents, exports, health, invoices, jobs, settings, trips


router = APIRouter()
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(dashboard.router)
router.include_router(trips.router)
router.include_router(documents.router)
router.include_router(invoices.router)
router.include_router(jobs.router)
router.include_router(exports.router)
router.include_router(settings.router)
