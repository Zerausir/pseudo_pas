"""
Cliente para Redis - Caché de pseudónimos.
"""
import redis
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Cliente global de Redis
redis_client = None


def connect():
    """Conecta al servidor Redis."""
    global redis_client

    try:
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            decode_responses=True,  # Retorna strings en lugar de bytes
            socket_connect_timeout=5,
            socket_timeout=5
        )

        # Verificar conexión
        redis_client.ping()
        logger.info("✅ Redis conectado exitosamente")

    except Exception as e:
        logger.error(f"❌ Error conectando a Redis: {e}")
        raise


def get(key: str) -> str:
    """
    Obtiene un valor de Redis.

    Args:
        key: Clave a buscar

    Returns:
        str: Valor encontrado o None
    """
    try:
        return redis_client.get(key)
    except Exception as e:
        logger.error(f"❌ Error obteniendo clave {key}: {e}")
        return None


def set(key: str, value: str, ttl_seconds: int = None):
    """
    Guarda un valor en Redis.

    Args:
        key: Clave
        value: Valor a guardar
        ttl_seconds: Tiempo de vida en segundos (None = sin expiración)
    """
    try:
        if ttl_seconds:
            redis_client.setex(key, ttl_seconds, value)
        else:
            redis_client.set(key, value)
    except Exception as e:
        logger.error(f"❌ Error guardando clave {key}: {e}")
        raise


def delete(key: str):
    """Elimina una clave de Redis."""
    try:
        redis_client.delete(key)
    except Exception as e:
        logger.error(f"❌ Error eliminando clave {key}: {e}")
        raise


def delete_pattern(pattern: str):
    """
    Elimina todas las claves que coincidan con un patrón.

    Args:
        pattern: Patrón de búsqueda (ej: "session:*")
    """
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
            logger.info(f"✅ Eliminadas {len(keys)} claves con patrón '{pattern}'")
    except Exception as e:
        logger.error(f"❌ Error eliminando patrón {pattern}: {e}")
        raise


def health_check() -> dict:
    """Verifica el estado de Redis."""
    try:
        if redis_client:
            redis_client.ping()
            info = redis_client.info()
            return {
                "status": "healthy",
                "version": info.get('redis_version', 'unknown'),
                "connected_clients": info.get('connected_clients', 0),
                "used_memory_human": info.get('used_memory_human', 'unknown')
            }
        else:
            return {"status": "unhealthy", "error": "Not connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
