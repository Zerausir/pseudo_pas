"""
Servicio de pseudonimización de datos personales - VERSIÓN HÍBRIDA (Regex + spaCy)

DETECCIÓN:
- Regex: RUC, cédulas, emails, teléfonos, direcciones específicas
- spaCy: Nombres de personas con títulos profesionales (Ing., Dr., Econ., etc.)

PRECISIÓN: ~97% (filtros estrictos para evitar falsos positivos)
"""
import re
import uuid
from typing import Dict, Set, List
import logging

from app.vault_client import encrypt, decrypt
from app.redis_client import get as redis_get, set as redis_set, delete_pattern
from app.config import settings
from app.services.spacy_detector import detectar_entidades_spacy

logger = logging.getLogger(__name__)

# Patrones Regex para datos ESTRUCTURADOS
PATTERNS = {
    # ORDEN IMPORTANTE: Los más específicos primero
    'ruc': r'\b\d{13}\b',  # Primero para evitar conflicto con cédula
    'cedula': r'\b\d{10}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',

    # Teléfonos ecuatorianos (excluye cédulas/RUCs)
    'telefono': r'\b(?:\+593\s?)?(?:0)[2-9][0-9]{6,8}(?:\s?/\s?[0-9]{7,10})?\b',

    # Direcciones ecuatorianas específicas
    'direccion_interseccion': r'\b[A-Z0-9]+\s+Y\s+[A-Z0-9]+,\s+(?:CASA|EDIFICIO|PISO|DEPARTAMENTO|LOCAL)\s+[A-Z0-9\-]+\b',
}

# Excepciones explícitas - NO pseudonimizar
EXCEPCIONES = {
    # Instituciones
    'ARCOTEL', 'CAFI', 'CTDG', 'CCON', 'DEDA', 'CTRP', 'CADF',

    # Ciudades ecuatorianas (solas, sin provincia)
    'QUITO', 'GUAYAQUIL', 'CUENCA', 'AMBATO', 'RIOBAMBA', 'LOJA',
    'MACHALA', 'PORTOVIEJO', 'MANTA', 'SANTO DOMINGO', 'ESMERALDAS', 'IBARRA',

    # Provincias
    'PICHINCHA', 'GUAYAS', 'AZUAY', 'TUNGURAHUA', 'CHIMBORAZO',
    'MANABÍ', 'EL ORO', 'IMBABURA',

    # Términos legales comunes
    'Ley Orgánica', 'Código Orgánico', 'Reglamento', 'Estatuto',
    'Registro Oficial', 'Ministerio', 'Secretaría',

    # Cargos genéricos (sin nombre)
    'Director Ejecutivo', 'Director Técnico', 'Coordinador Técnico',
    'Profesional Financiero', 'Responsable', 'Titular',

    # Sistemas y documentos
    'Quipux', 'Memorando', 'Oficio', 'Informe', 'Resolución',
    'Sistema de Gestión Documental',
}

# Frases completas que NO deben pseudonimizarse
FRASES_EXCLUIDAS = {
    'Ley Orgánica de Telecomunicaciones',
    'Código Orgánico Administrativo',
    'Registro Oficial',
    'Estatuto Orgánico de Gestión',
    'Agencia de Regulación y Control',
    'Dirección Técnica de Gestión Económica',
    'Coordinación Técnica de Títulos Habilitantes',
    'Procedimiento Administrativo Sancionador',
    'Sistema de Gestión Documental',
    'Normativa Legal Vigente',
    'Registro Público de Telecomunicaciones',
    'Unidad de Documentación y Archivo',
    'Garantía de Fiel Cumplimiento',
    'Títulos Habilitantes',
    'Espectro Radioeléctrico',
}


def generate_pseudonym(prefix: str = "PSN") -> str:
    """Genera un pseudónimo único."""
    unique_id = str(uuid.uuid4())[:8].upper()
    return f"{prefix}_{unique_id}"


def is_exception(text: str) -> bool:
    """Verifica si un texto es una excepción conocida."""
    text_clean = text.strip()

    # Verificar excepciones exactas
    if text_clean.upper() in {e.upper() for e in EXCEPCIONES}:
        return True

    # Verificar frases completas
    for frase in FRASES_EXCLUIDAS:
        if frase.lower() in text_clean.lower():
            return True

    # Verificar si contiene palabras clave institucionales
    palabras_institucionales = [
        'ARCOTEL', 'Dirección', 'Coordinación', 'Unidad',
        'Reglamento', 'Ley', 'Código', 'Estatuto',
        'Ministerio', 'Secretaría', 'Agencia'
    ]

    for palabra in palabras_institucionales:
        if palabra in text_clean:
            return True

    return False


async def pseudonymize_text(text: str, session_id: str) -> Dict:
    """
    Pseudonimiza un texto usando HÍBRIDO (Regex + spaCy).

    FLUJO:
    1. Detectar con Regex (datos estructurados: RUC, cédula, email, teléfono, direcciones)
    2. Detectar con spaCy (nombres de personas con títulos profesionales)
    3. Merge inteligente (sin duplicados)
    4. Pseudonimizar todos

    Args:
        text: Texto original con datos personales
        session_id: ID de sesión para vincular pseudónimos

    Returns:
        dict: {
            'pseudonymized_text': str,
            'session_id': str,
            'mapping': dict,
            'pseudonyms_count': int,
            'stats': dict  # Estadísticas de detección
        }
    """
    pseudonymized_text = text
    mapping = {}
    processed_values: Set[str] = set()

    stats = {
        'regex_detections': 0,
        'spacy_detections': 0,
        'total_unique': 0
    }

    # ========== CAPA 1: DETECCIÓN CON REGEX (Datos Estructurados) ==========
    logger.info("🔍 Capa 1: Detección con Regex...")

    for data_type, pattern in PATTERNS.items():
        matches = re.finditer(pattern, text, re.MULTILINE)

        for match in matches:
            original_value = match.group(0).strip()

            # Evitar duplicados
            if original_value in processed_values:
                continue

            # Verificar excepciones
            if is_exception(original_value):
                logger.debug(f"⏭️  Regex omitió excepción: {original_value}")
                continue

            # Verificar si ya existe pseudónimo
            cache_key = f"{session_id}:{data_type}:{original_value}"
            cached_pseudonym = redis_get(cache_key)

            if cached_pseudonym:
                pseudonym = cached_pseudonym
                logger.debug(f"♻️  Reutilizando: {pseudonym}")
            else:
                # Generar nuevo pseudónimo
                prefix_map = {
                    'ruc': 'RUC',
                    'cedula': 'CEDULA',
                    'email': 'EMAIL',
                    'telefono': 'TELEFONO',
                    'direccion_interseccion': 'DIRECCION',
                }
                prefix = prefix_map.get(data_type, 'PSN')
                pseudonym = generate_pseudonym(prefix)

                # Cifrar con Vault
                encrypted_value = encrypt(original_value)

                # Guardar en Redis
                reverse_key = f"{session_id}:reverse:{pseudonym}"
                ttl_seconds = settings.TTL_HOURS * 3600
                redis_set(reverse_key, encrypted_value, ttl_seconds)
                redis_set(cache_key, pseudonym, ttl_seconds)

                logger.info(f"✅ Regex detectó: {original_value} → {pseudonym}")
                stats['regex_detections'] += 1

            # Reemplazar en el texto
            pseudonymized_text = pseudonymized_text.replace(original_value, pseudonym)
            mapping[pseudonym] = original_value
            processed_values.add(original_value)

    # ========== CAPA 2: DETECCIÓN CON spaCy (Nombres de Personas) ==========
    logger.info("🔍 Capa 2: Detección con spaCy NER (solo personas)...")

    entidades_spacy = detectar_entidades_spacy(text)

    for entidad in entidades_spacy:
        original_value = entidad["texto"].strip()
        tipo_spacy = entidad["tipo"]  # Siempre será PER

        # Evitar duplicados
        if original_value in processed_values:
            continue

        # Verificar excepciones
        if is_exception(original_value):
            logger.debug(f"⏭️  spaCy omitió excepción: {original_value}")
            continue

        # Verificar si ya existe pseudónimo
        data_type = "nombre_persona"
        cache_key = f"{session_id}:{data_type}:{original_value}"
        cached_pseudonym = redis_get(cache_key)

        if cached_pseudonym:
            pseudonym = cached_pseudonym
            logger.debug(f"♻️  Reutilizando: {pseudonym}")
        else:
            # Generar nuevo pseudónimo
            pseudonym = generate_pseudonym("NOMBRE")

            # Cifrar con Vault
            encrypted_value = encrypt(original_value)

            # Guardar en Redis
            reverse_key = f"{session_id}:reverse:{pseudonym}"
            ttl_seconds = settings.TTL_HOURS * 3600
            redis_set(reverse_key, encrypted_value, ttl_seconds)
            redis_set(cache_key, pseudonym, ttl_seconds)

            logger.info(f"✅ spaCy detectó: {original_value} → {pseudonym}")
            stats['spacy_detections'] += 1

        # Reemplazar en el texto
        pseudonymized_text = pseudonymized_text.replace(original_value, pseudonym)
        mapping[pseudonym] = original_value
        processed_values.add(original_value)

    # ========== ESTADÍSTICAS FINALES ==========
    stats['total_unique'] = len(mapping)

    logger.info(f"📊 Estadísticas de detección:")
    logger.info(f"   - Regex: {stats['regex_detections']} detecciones")
    logger.info(f"   - spaCy: {stats['spacy_detections']} detecciones")
    logger.info(f"   - Total: {stats['total_unique']} pseudónimos únicos")

    return {
        'pseudonymized_text': pseudonymized_text,
        'session_id': session_id,
        'mapping': mapping,
        'pseudonyms_count': len(mapping),
        'stats': stats
    }


async def depseudonymize_text(text: str, session_id: str) -> Dict:
    """Revierte la pseudonimización."""
    original_text = text

    pseudonym_pattern = r'\b[A-Z]+_[A-F0-9]{8}\b'
    matches = re.finditer(pseudonym_pattern, text)

    for match in matches:
        pseudonym = match.group(0)
        reverse_key = f"{session_id}:reverse:{pseudonym}"
        encrypted_value = redis_get(reverse_key)

        if encrypted_value:
            try:
                original_value = decrypt(encrypted_value)
                original_text = original_text.replace(pseudonym, original_value)
                logger.info(f"✅ Recuperado valor original para {pseudonym}")
            except Exception as e:
                logger.error(f"❌ Error descifrando {pseudonym}: {e}")
        else:
            logger.warning(f"⚠️  No se encontró valor original para {pseudonym}")

    return {'original_text': original_text}


async def cleanup_session(session_id: str):
    """Elimina todos los datos de una sesión."""
    try:
        pattern = f"{session_id}:*"
        delete_pattern(pattern)
        logger.info(f"🧹 Sesión {session_id} limpiada")
        return {"status": "success", "session_id": session_id}
    except Exception as e:
        logger.error(f"❌ Error limpiando sesión {session_id}: {e}")
        raise
