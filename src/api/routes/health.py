"""
Rotas de health check e status da aplicação.
"""

from datetime import datetime, UTC
from fastapi import APIRouter
from loguru import logger

from src.api.schemas.responses import HealthCheckResponse
from src.core.config import get_settings
from src.infrastructure.database.session import check_db_connection

settings = get_settings()
router = APIRouter()


@router.get("", response_model=HealthCheckResponse)
@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """
    Health check da aplicação.
    Verifica status de dependências críticas.
    """
    
    status = "healthy"
    checks = {
        "database": False,
        "ai_service": False,
        "whatsapp": False
    }
    
    # 1. Banco de dados
    try:
        checks["database"] = await check_db_connection()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        status = "unhealthy"
    
    # 2. IA Service (verifica se tem API key configurada)
    checks["ai_service"] = bool(settings.deepseek_api_key)
    if not checks["ai_service"]:
        status = "degraded"
    
    # 3. WhatsApp (verifica se tem token configurado)
    checks["whatsapp"] = bool(settings.whatsapp_access_token)
    if not checks["whatsapp"]:
        status = "degraded"
    
    return HealthCheckResponse(
        status=status,
        version=settings.app_version,
        database=checks["database"],
        ai_service=checks["ai_service"],
        whatsapp=checks["whatsapp"],
        timestamp=datetime.now(UTC)
    )


@router.get("/live")
async def liveness():
    """
    Liveness probe (para Kubernetes).
    Retorna 200 se a aplicação está rodando.
    """
    return {"status": "alive"}


@router.get("/ready")
async def readiness():
    """
    Readiness probe (para Kubernetes).
    Retorna 200 apenas se a aplicação está pronta para receber tráfego.
    """
    
    # Verifica banco de dados
    db_ok = await check_db_connection()
    
    if not db_ok:
        return {"status": "not ready", "reason": "database unavailable"}, 503
    
    return {"status": "ready"}