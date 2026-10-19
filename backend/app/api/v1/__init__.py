from fastapi import APIRouter
from app.api.v1.health import router as health_router
from app.api.v1.signals import router as signals_router
from app.api.v1.portfolios import router as portfolios_router
from app.api.v1.stress_test import router as stress_test_router
from app.api.v1.ingestion import router as ingestion_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(signals_router)
api_router.include_router(portfolios_router)
api_router.include_router(stress_test_router)
api_router.include_router(ingestion_router)
