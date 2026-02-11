"""
Endpoints de salud del servicio.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Endpoint de health check - versión simplificada."""
    # Importar aquí para evitar problemas circulares
    from app.database import health_check as db_health
    from app.vault_client import health_check as vault_health
    from app.redis_client import health_check as redis_health

    # Llamar directamente (si son sync) o con try-except si pueden ser async
    try:
        # Intentar sync primero
        db_status = db_health()
        vault_status = vault_health()
        redis_status = redis_health()
    except TypeError:
        # Si fallan, son async - usar await
        db_status = await db_health()
        vault_status = await vault_health()
        redis_status = await redis_health()

    # Verificar si son coroutines sin ejecutar
    if hasattr(db_status, '__await__'):
        db_status = await db_status
    if hasattr(vault_status, '__await__'):
        vault_status = await vault_status
    if hasattr(redis_status, '__await__'):
        redis_status = await redis_status

    all_healthy = (
            db_status.get("status") == "healthy" and
            vault_status.get("status") == "healthy" and
            redis_status.get("status") == "healthy"
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "services": {
            "database": db_status,
            "vault": vault_status,
            "redis": redis_status
        }
    }


@router.get("/ready")
async def ready():
    """Endpoint de readiness check."""
    return {"ready": True}


@router.get("/live")
async def live():
    """Endpoint de liveness check."""
    return {"alive": True}
