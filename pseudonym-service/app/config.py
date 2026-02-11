"""
Configuración del Servicio de Pseudonimización
Carga y valida variables de entorno
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Configuración del servicio de pseudonimización.
    
    Todas las variables se cargan desde .env o variables de entorno.
    """
    
    # =====================================================
    # POSTGRESQL - Base de Datos Separada
    # =====================================================
    POSTGRES_DB: str = Field(..., description="Nombre de la base de datos")
    POSTGRES_USER: str = Field(..., description="Usuario de PostgreSQL")
    POSTGRES_PASSWORD: str = Field(..., description="Password de PostgreSQL")
    POSTGRES_HOST: str = Field(default="postgres_pseudonym", description="Host de PostgreSQL")
    POSTGRES_PORT: int = Field(default=5432, description="Puerto de PostgreSQL")
    
    # =====================================================
    # HASHICORP VAULT - KMS
    # =====================================================
    VAULT_ADDR: str = Field(default="http://vault:8200", description="URL de Vault")
    VAULT_TOKEN: str = Field(..., description="Token de autenticación de Vault")
    VAULT_TRANSIT_KEY_NAME: str = Field(
        default="pseudonym-encryption-key",
        description="Nombre de la clave Transit en Vault"
    )
    
    # =====================================================
    # REDIS - Cache
    # =====================================================
    REDIS_HOST: str = Field(default="redis", description="Host de Redis")
    REDIS_PORT: int = Field(default=6379, description="Puerto de Redis")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Password de Redis")
    REDIS_DB: int = Field(default=0, description="Base de datos de Redis")
    
    # =====================================================
    # SERVICIO
    # =====================================================
    SERVICE_NAME: str = Field(default="pseudonym-service", description="Nombre del servicio")
    SERVICE_PORT: int = Field(default=8001, description="Puerto del servicio")
    ENV: str = Field(default="development", description="Entorno: development/production")
    DEBUG: bool = Field(default=False, description="Modo debug")
    
    # =====================================================
    # SEGURIDAD - JWT
    # =====================================================
    JWT_SECRET: str = Field(..., description="Secret para JWT")
    JWT_ALGORITHM: str = Field(default="HS256", description="Algoritmo JWT")
    JWT_EXPIRATION_MINUTES: int = Field(default=60, description="Expiración JWT en minutos")
    
    # =====================================================
    # TTL - Tiempo de Vida
    # =====================================================
    TTL_HOURS: int = Field(default=1, description="TTL de pseudónimos en horas")
    
    # =====================================================
    # LOGGING
    # =====================================================
    LOG_LEVEL: str = Field(default="INFO", description="Nivel de logging")
    LOG_FORMAT: str = Field(default="json", description="Formato de logs: json/text")
    
    # =====================================================
    # LÍMITES
    # =====================================================
    MAX_PSEUDONYMS_PER_SESSION: int = Field(
        default=1000,
        description="Máximo de pseudónimos por sesión"
    )
    MAX_TEXT_LENGTH: int = Field(
        default=100000,
        description="Longitud máxima de texto a pseudonimizar"
    )
    
    # =====================================================
    # CORS
    # =====================================================
    CORS_ORIGINS: str = Field(
        default="http://localhost:8000",
        description="Orígenes permitidos para CORS (separados por coma)"
    )
    
    # =====================================================
    # WORKERS
    # =====================================================
    WORKERS: int = Field(default=1, description="Número de workers Uvicorn")
    
    @validator("ENV")
    def validate_env(cls, v):
        """Validar que ENV sea development o production"""
        if v not in ["development", "production"]:
            raise ValueError("ENV debe ser 'development' o 'production'")
        return v
    
    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validar que LOG_LEVEL sea válido"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL debe ser uno de: {valid_levels}")
        return v.upper()
    
    @validator("TTL_HOURS")
    def validate_ttl(cls, v):
        """Validar que TTL sea razonable"""
        if v < 1 or v > 24:
            raise ValueError("TTL_HOURS debe estar entre 1 y 24")
        return v
    
    @property
    def database_url(self) -> str:
        """
        Construir URL de base de datos de forma segura.
        
        Usa sqlalchemy.engine.URL.create() internamente.
        """
        from sqlalchemy.engine import URL
        
        return URL.create(
            drivername="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)
    
    @property
    def redis_url(self) -> str:
        """Construir URL de Redis"""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        else:
            return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    @property
    def cors_origins_list(self) -> list:
        """Convertir CORS_ORIGINS a lista"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def is_production(self) -> bool:
        """Verificar si está en producción"""
        return self.ENV == "production"
    
    @property
    def is_development(self) -> bool:
        """Verificar si está en desarrollo"""
        return self.ENV == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# =====================================================
# INSTANCIA GLOBAL DE SETTINGS
# =====================================================

try:
    settings = Settings()
except Exception as e:
    print(f"❌ ERROR al cargar configuración: {e}")
    print("⚠️ Asegúrate de que el archivo .env existe y tiene todas las variables requeridas")
    raise


# =====================================================
# VALIDACIÓN AL IMPORTAR
# =====================================================

def validate_configuration():
    """
    Validar configuración crítica al iniciar la aplicación.
    """
    errors = []
    
    # Validar variables críticas
    if not settings.POSTGRES_PASSWORD or settings.POSTGRES_PASSWORD == "CAMBIAR_PASSWORD_SEGURO_AQUI":
        errors.append("POSTGRES_PASSWORD no está configurado")
    
    if not settings.VAULT_TOKEN or settings.VAULT_TOKEN == "root-token-dev-only-CHANGE-IN-PRODUCTION":
        if settings.is_production:
            errors.append("VAULT_TOKEN debe cambiarse en producción")
    
    if not settings.JWT_SECRET or settings.JWT_SECRET == "CAMBIAR_JWT_SECRET_SUPER_LARGO_Y_ALEATORIO_AQUI":
        errors.append("JWT_SECRET no está configurado")
    
    if len(settings.JWT_SECRET) < 32:
        errors.append("JWT_SECRET debe tener al menos 32 caracteres")
    
    # Reportar errores
    if errors:
        print("❌ ERRORES DE CONFIGURACIÓN:")
        for error in errors:
            print(f"   - {error}")
        if settings.is_production:
            raise ValueError("Configuración inválida para producción")
        else:
            print("⚠️ Advertencia: Configuración insegura (OK para desarrollo)")
    else:
        print("✅ Configuración validada correctamente")


# Validar al importar (solo si no estamos en tests)
if os.getenv("TESTING") != "true":
    validate_configuration()
