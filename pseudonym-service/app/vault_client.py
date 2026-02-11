"""
Cliente para HashiCorp Vault - Encryption as a Service.
"""
import hvac
import base64
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Cliente global de Vault
vault_client = None
TRANSIT_KEY_NAME = settings.VAULT_TRANSIT_KEY_NAME


def initialize():
    """Inicializa el cliente de Vault y crea la clave de cifrado."""
    global vault_client

    try:
        # Conectar a Vault
        vault_client = hvac.Client(
            url=settings.VAULT_ADDR,
            token=settings.VAULT_TOKEN
        )

        # Verificar autenticación
        if not vault_client.is_authenticated():
            raise Exception("❌ Vault authentication failed")

        logger.info("✅ Vault cliente conectado")

        # Habilitar Transit engine si no está habilitado
        try:
            vault_client.sys.enable_secrets_engine(
                backend_type='transit',
                path='transit'
            )
            logger.info("✅ Transit engine habilitado")
        except hvac.exceptions.InvalidRequest as e:
            if "path is already in use" in str(e):
                logger.info("ℹ️  Transit engine ya estaba habilitado")
            else:
                raise

        # Crear clave de cifrado si no existe
        try:
            vault_client.secrets.transit.create_key(
                name=TRANSIT_KEY_NAME,
                key_type='aes256-gcm96',
                exportable=False
            )
            logger.info(f"✅ Clave de cifrado '{TRANSIT_KEY_NAME}' creada")
        except hvac.exceptions.InvalidRequest as e:
            if "already exists" in str(e):
                logger.info(f"ℹ️  Clave '{TRANSIT_KEY_NAME}' ya existía")
            else:
                raise

        logger.info("✅ Vault inicializado correctamente")

    except Exception as e:
        logger.error(f"❌ Error inicializando Vault: {e}")
        raise


def encrypt(plaintext: str) -> str:
    """
    Cifra un texto usando Vault Transit Engine.

    Args:
        plaintext: Texto a cifrar

    Returns:
        str: Texto cifrado (formato: vault:v1:...)
    """
    try:
        # ✅ CRÍTICO: Vault requiere base64
        plaintext_b64 = base64.b64encode(plaintext.encode('utf-8')).decode('utf-8')

        response = vault_client.secrets.transit.encrypt_data(
            name=TRANSIT_KEY_NAME,
            plaintext=plaintext_b64  # ← base64, no texto plano
        )
        return response['data']['ciphertext']
    except Exception as e:
        logger.error(f"❌ Error cifrando: {e}")
        raise


def decrypt(ciphertext: str) -> str:
    """
    Descifra un texto usando Vault Transit Engine.

    Args:
        ciphertext: Texto cifrado (formato: vault:v1:...)

    Returns:
        str: Texto descifrado
    """
    try:
        response = vault_client.secrets.transit.decrypt_data(
            name=TRANSIT_KEY_NAME,
            ciphertext=ciphertext
        )

        # ✅ CRÍTICO: Vault devuelve base64, hay que decodificar
        plaintext_b64 = response['data']['plaintext']
        plaintext = base64.b64decode(plaintext_b64).decode('utf-8')

        return plaintext
    except Exception as e:
        logger.error(f"❌ Error descifrando: {e}")
        raise


def health_check() -> dict:
    """Verifica el estado de Vault."""
    try:
        if vault_client and vault_client.is_authenticated():
            health = vault_client.sys.read_health_status(method='GET')
            return {
                "status": "healthy",
                "initialized": health.get('initialized', False),
                "sealed": health.get('sealed', False),
                "version": health.get('version', 'unknown')
            }
        else:
            return {"status": "unhealthy", "error": "Not authenticated"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
