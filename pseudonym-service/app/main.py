"""
Aplicación principal del servicio de pseudonimización.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import settings
from app.database import engine, Base, health_check as db_health
from app.vault_client import initialize as vault_init, health_check as vault_health
from app.redis_client import connect as redis_connect, health_check as redis_health
from app.api import internal, health

# Configurar logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear aplicación FastAPI
app = FastAPI(
    title="Servicio de Pseudonimización ARCOTEL",
    description="Servicio para pseudonimizar datos personales antes de enviar a Claude API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir routers
app.include_router(health.router, tags=["health"])
app.include_router(internal.router, prefix="/internal", tags=["internal"])


@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar."""
    logger.info("🚀 Iniciando servicio de pseudonimización...")

    # Crear tablas si no existen
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Tablas de base de datos verificadas")

    # Inicializar Vault
    vault_init()
    logger.info("✅ Vault inicializado")

    # Conectar a Redis
    redis_connect()
    logger.info("✅ Redis conectado")

    logger.info("✅ Servicio de pseudonimización listo")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar."""
    logger.info("👋 Cerrando servicio de pseudonimización...")
