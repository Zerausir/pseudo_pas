"""
Configuración de base de datos PostgreSQL para ARCOTEL PAS

IMPORTANTE:
- Usa variables de entorno (NO credenciales hardcodeadas)
- Compatible con PostgreSQL 18+
- SQLAlchemy 2.0
- Manejo correcto de conexiones y sesiones
"""

import os
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import URL

# =====================================================
# CONFIGURACIÓN DESDE VARIABLES DE ENTORNO
# =====================================================

# Opción 1: Usar DATABASE_URL directamente (recomendado para Docker)
DATABASE_URL = os.getenv("DATABASE_URL")

# Opción 2: Construir URL desde componentes individuales (fallback)
if not DATABASE_URL:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")  # Nombre del servicio en docker-compose
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "arcotel_pas")

    if not POSTGRES_PASSWORD:
        raise ValueError(
            "ERROR: POSTGRES_PASSWORD no está configurada en variables de entorno.\n"
            "Asegúrate de que el archivo .env existe y tiene POSTGRES_PASSWORD definida."
        )

    # Construir URL de forma segura
    DATABASE_URL = URL.create(
        drivername="postgresql",
        username=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=int(POSTGRES_PORT),
        database=POSTGRES_DB,
    ).render_as_string(hide_password=False)

# =====================================================
# CONFIGURACIÓN DEL ENGINE
# =====================================================

# Configuración del engine con opciones de rendimiento
engine = create_engine(
    DATABASE_URL,
    # Pool de conexiones
    pool_size=5,  # Número de conexiones permanentes
    max_overflow=10,  # Conexiones adicionales permitidas
    pool_timeout=30,  # Timeout para obtener conexión
    pool_recycle=3600,  # Reciclar conexiones cada hora
    pool_pre_ping=True,  # Verificar conexión antes de usar

    # Logging (desactivar en producción)
    echo=os.getenv("DEBUG", "false").lower() == "true",

    # Opciones de ejecución
    future=True,  # SQLAlchemy 2.0 style
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
        @router.get("/items")
        def get_items(db: Session = Depends(get_db)):
            items = db.query(Item).all()
            return items
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =====================================================
# FUNCIONES ÚTILES
# =====================================================

def init_db() -> None:
    """
    Inicializa la base de datos creando todas las tablas.

    NOTA: En este proyecto, las tablas se crean automáticamente
    por el script de auto-inicialización de PostgreSQL.
    Esta función es solo por si se necesita crear tablas
    desde el código Python.
    """
    # Importar todos los modelos para que SQLAlchemy los registre
    # from app.models import prestador, caso_pas, documento_pas, etc

    Base.metadata.create_all(bind=engine)


def check_db_connection() -> bool:
    """
    Verifica la conexión a la base de datos.

    Returns:
        True si la conexión es exitosa, False en caso contrario
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Error al conectar con la base de datos: {e}")
        return False


def get_db_info() -> dict:
    """
    Obtiene información de la conexión a la base de datos.

    Returns:
        Diccionario con información de la conexión
    """
    # Obtener URL sin password
    safe_url = URL.create(
        drivername="postgresql",
        username=os.getenv("POSTGRES_USER", "postgres"),
        password="***",  # Ocultar password
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "arcotel_pas"),
    )

    return {
        "driver": "PostgreSQL",
        "host": os.getenv("POSTGRES_HOST", "postgres"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
        "database": os.getenv("POSTGRES_DB", "arcotel_pas"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "url": str(safe_url),
        "pool_size": engine.pool.size(),
        "pool_overflow": engine.pool._overflow,
    }


# =====================================================
# HEALTH CHECK
# =====================================================

async def health_check() -> dict:
    """
    Health check para endpoints de la API.

    Returns:
        Estado de la conexión a la base de datos
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]

        return {
            "status": "healthy",
            "database": "connected",
            "postgres_version": version,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
        }


# =====================================================
# VERIFICACIÓN AL IMPORTAR
# =====================================================

if __name__ == "__main__":
    # Script de verificación cuando se ejecuta directamente
    print("=" * 60)
    print("VERIFICACIÓN DE CONFIGURACIÓN DE BASE DE DATOS")
    print("=" * 60)
    print()

    # Mostrar información de conexión
    info = get_db_info()
    print("Información de conexión:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    print()

    # Verificar conexión
    print("Verificando conexión a PostgreSQL...")
    if check_db_connection():
        print("✅ Conexión exitosa")

        # Obtener versión
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ PostgreSQL version: {version}")
    else:
        print("❌ Error de conexión")
        print()
        print("Verifica que:")
        print("  1. PostgreSQL está corriendo (docker-compose ps)")
        print("  2. Las variables de entorno están configuradas (.env)")
        print("  3. Las credenciales son correctas")

    print()
    print("=" * 60)
else:
    # Al importar, hacer verificación silenciosa
    # Solo mostrar errores críticos
    if not DATABASE_URL and not os.getenv("POSTGRES_PASSWORD"):
        import warnings

        warnings.warn(
            "POSTGRES_PASSWORD no está configurada. "
            "La aplicación no podrá conectarse a la base de datos.",
            RuntimeWarning
        )
