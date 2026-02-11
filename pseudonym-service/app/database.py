"""
Configuración de Base de Datos - Servicio de Pseudonimización
Conexión a PostgreSQL separada (postgres_pseudonym)
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
from typing import Generator
import logging

from app.config import settings

# =====================================================
# LOGGER
# =====================================================

logger = logging.getLogger(__name__)

# =====================================================
# CONFIGURACIÓN DEL ENGINE
# =====================================================

# Construir DATABASE_URL de forma segura
DATABASE_URL = settings.database_url

logger.info(f"📊 Conectando a base de datos: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")

# Configuración del engine con opciones de rendimiento
engine = create_engine(
    DATABASE_URL,
    # Pool de conexiones
    poolclass=QueuePool,
    pool_size=5,  # Número de conexiones permanentes
    max_overflow=10,  # Conexiones adicionales permitidas
    pool_timeout=30,  # Timeout para obtener conexión (segundos)
    pool_recycle=3600,  # Reciclar conexiones cada hora
    pool_pre_ping=True,  # Verificar conexión antes de usar
    
    # Logging (solo en desarrollo)
    echo=settings.DEBUG,
    
    # SQLAlchemy 2.0 style
    future=True,
)

# =====================================================
# SESIONES
# =====================================================

# Factory de sesiones
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,  # SQLAlchemy 2.0 style
)

# Base declarativa para modelos
Base = declarative_base()


# =====================================================
# DEPENDENCY INJECTION (para FastAPI)
# =====================================================

def get_db() -> Generator[Session, None, None]:
    """
    Dependency para obtener sesión de base de datos en FastAPI.
    
    Uso en endpoints:
        @router.post("/endpoint")
        async def my_endpoint(db: Session = Depends(get_db)):
            # Usar db aquí
            pass
    
    Yields:
        Session: Sesión de SQLAlchemy
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================
# FUNCIONES DE HEALTH CHECK
# =====================================================

async def health_check() -> dict:
    """
    Verificar salud de la conexión a base de datos.
    
    Returns:
        dict: Estado de la base de datos
    """
    try:
        with engine.connect() as conn:
            # Ejecutar query simple
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            
            # Verificar pool de conexiones
            pool_status = engine.pool.status()
            
            return {
                "status": "healthy",
                "database": settings.POSTGRES_DB,
                "host": settings.POSTGRES_HOST,
                "postgres_version": version,
                "pool_status": pool_status,
            }
    except Exception as e:
        logger.error(f"❌ Error en health check de BD: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }


def check_connection() -> bool:
    """
    Verificar si la conexión a base de datos funciona.
    
    Returns:
        bool: True si la conexión funciona, False si falla
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"❌ Error al conectar con base de datos: {e}")
        return False


# =====================================================
# FUNCIONES DE INICIALIZACIÓN
# =====================================================

def init_db() -> None:
    """
    Inicializar base de datos creando todas las tablas.
    
    NOTA: En este proyecto, las tablas se crean automáticamente
    por el script SQL en /docker-entrypoint-initdb.d/
    Esta función es solo por si se necesita crear tablas
    desde el código Python.
    """
    logger.info("📊 Inicializando base de datos...")
    
    # Importar todos los modelos para que SQLAlchemy los registre
    from app.models import pseudonym  # noqa
    
    # Crear todas las tablas
    Base.metadata.create_all(bind=engine)
    
    logger.info("✅ Base de datos inicializada")


def get_db_info() -> dict:
    """
    Obtener información de configuración de la base de datos.
    
    ADVERTENCIA: No exponer en producción sin autenticación.
    
    Returns:
        dict: Información de configuración (sin password)
    """
    return {
        "database": settings.POSTGRES_DB,
        "user": settings.POSTGRES_USER,
        "host": settings.POSTGRES_HOST,
        "port": settings.POSTGRES_PORT,
        "pool_size": engine.pool.size(),
        "pool_timeout": engine.pool.timeout(),
        "pool_recycle": engine.pool._recycle,
    }


# =====================================================
# FUNCIONES DE UTILIDAD PARA QUERIES
# =====================================================

def execute_query(query: str, params: dict = None) -> list:
    """
    Ejecutar query SQL y retornar resultados.
    
    Args:
        query: Query SQL (usar :param para parámetros)
        params: Diccionario de parámetros
    
    Returns:
        list: Lista de resultados
    
    Example:
        >>> execute_query("SELECT * FROM tabla WHERE id = :id", {"id": 123})
    """
    with engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result]


def execute_function(function_name: str, params: list = None) -> any:
    """
    Ejecutar función de PostgreSQL.
    
    Args:
        function_name: Nombre de la función
        params: Lista de parámetros
    
    Returns:
        any: Resultado de la función
    
    Example:
        >>> execute_function("delete_expired_mappings")
    """
    params_str = ", ".join([f":{i}" for i in range(len(params or []))])
    query = f"SELECT * FROM {function_name}({params_str})"
    
    with engine.connect() as conn:
        result = conn.execute(text(query), {str(i): p for i, p in enumerate(params or [])})
        return result.fetchone()


# =====================================================
# VALIDACIÓN AL IMPORTAR
# =====================================================

def validate_database_connection():
    """
    Validar conexión a base de datos al iniciar.
    """
    logger.info("🔍 Validando conexión a base de datos...")
    
    if check_connection():
        logger.info("✅ Conexión a base de datos exitosa")
        
        # Mostrar versión de PostgreSQL
        try:
            with engine.connect() as conn:
                version = conn.execute(text("SELECT version()")).scalar()
                logger.info(f"📊 PostgreSQL version: {version[:50]}...")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo obtener versión de PostgreSQL: {e}")
    else:
        logger.error("❌ No se pudo conectar a base de datos")
        logger.error(f"❌ URL: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
        raise ConnectionError("No se pudo conectar a base de datos de pseudonimización")


# Validar al importar (solo si no estamos en tests)
import os
if os.getenv("TESTING") != "true":
    validate_database_connection()


# =====================================================
# CLEANUP
# =====================================================

def cleanup_expired_sessions():
    """
    Ejecutar limpieza de sesiones expiradas.
    
    Esta función llama a la función SQL delete_expired_mappings()
    que elimina sesiones expiradas y sus mapeos asociados.
    
    Returns:
        tuple: (sesiones eliminadas, mapeos eliminados)
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM delete_expired_mappings()"))
            deleted_sessions, deleted_mappings = result.fetchone()
            
            logger.info(f"🧹 Limpieza: {deleted_sessions} sesiones, {deleted_mappings} mapeos eliminados")
            
            return deleted_sessions, deleted_mappings
    except Exception as e:
        logger.error(f"❌ Error en cleanup: {e}")
        return 0, 0
