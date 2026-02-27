"""
Servicio de pseudonimización - VERSIÓN 2.1.7

HISTORIAL DE VERSIONES:
- v2.0: Normalización mayúsculas, variaciones de nombres, 3 capas detección
- v2.1: FIX patrones flexibles encabezado + normalización saltos de línea
- v2.1.1: FIX caracteres especiales (&, números, comas) en nombres
- v2.1.2: FIX orden de reemplazo de variaciones (más larga a más corta)
- v2.1.3: FIX búsqueda con \s+ para permitir saltos de línea entre palabras
- v2.1.4: FIX pseudonimización de direcciones desde encabezado
- v2.1.5: FIX Capa 2 spaCy usa buscar_y_reemplazar_variaciones (IGNORECASE)
- v2.1.6: FIX agregar Mgs. a patrones de firmantes (Capa 3)
- v2.1.7: FIX tres bugs de implementación en informes técnicos

CAMBIOS v2.1.7:
- 🐛 BUG 1 FIX: Lookahead CIUDAD cortaba prematuramente en "CIUDADELA"
  Solución: Agregar \b (word boundary) → (?=\s*Ciudad\b|CIUDAD\b|...)
  Afectado: CTDG-GE-2022-0485

- 🐛 BUG 2 FIX: Em dash (– U+2013) no estaba en clase de caracteres de dirección
  Solución: Agregar \u2013 a la clase de caracteres
  Afectados: CTDG-GE-2023-0255, CTDG-GE-2022-0169

- 🐛 BUG 3 FIX: Teléfonos sin prefijo "0" no detectados (ej: "84337197")
  Solución: Nuevo patrón 'telefono_campo' en patrones_encabezado con prefijo TELEFONO
  Afectado: CTDG-GE-2022-0337

- 🐛 BUG 4 FIX: Doble backslash en patrones Capa 3 → nunca hacían match
  Solución: Corregir a backslash simple en raw strings
  Afectados: Todos los documentos (firmantes nunca detectados correctamente)

- 🐛 BUG 5 FIX: telefono_campo procesado como NOMBRE en lugar de TELEFONO
  Solución: Branch dedicado en el loop de patrones_encabezado

HALLAZGOS DOCUMENTADOS (NO corregidos — para tesis):
- Apellidos compuestos ecuatorianos (Catucuago, Guerrero Gualsaqui, etc.)
  → Limitación de spaCy es_core_news_lg: cobertura insuficiente en corpus
- Texto fragmentado por pypdf (MERC EDES, hotma il.com)
  → Limitación del extractor de texto PDF al procesar columnas/tablas
"""
import re
import uuid
from typing import Dict, Set, List, Tuple
import logging

from app.vault_client import encrypt, decrypt
from app.redis_client import get as redis_get, set as redis_set, delete_pattern
from app.config import settings
from app.services.spacy_detector import detectar_entidades_spacy

logger = logging.getLogger(__name__)

# Patrones Regex para datos ESTRUCTURADOS (Capa 1)
PATTERNS = {
    'ruc': r'\b\d{13}\b',
    'cedula': r'\b\d{10}\b',
    'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    'telefono': r'\b(?:\+593\s?)?(?:0)[2-9][0-9]{6,8}(?:\s?/\s?[0-9]{7,10})?\b',
    'direccion_interseccion': r'\b[A-Z0-9]+\s+Y\s+[A-Z0-9]+,\s+(?:CASA|EDIFICIO|PISO|DEPARTAMENTO|LOCAL)\s+[A-Z0-9\-]+\b',
}

# Excepciones explícitas
EXCEPCIONES = {
    'ARCOTEL', 'CAFI', 'CTDG', 'CCON', 'DEDA', 'CTRP', 'CADF',
    'QUITO', 'GUAYAQUIL', 'CUENCA', 'AMBATO', 'RIOBAMBA', 'LOJA',
    'MACHALA', 'PORTOVIEJO', 'MANTA', 'SANTO DOMINGO', 'ESMERALDAS', 'IBARRA',
    'PICHINCHA', 'GUAYAS', 'AZUAY', 'TUNGURAHUA', 'CHIMBORAZO',
    'MANABÍ', 'EL ORO', 'IMBABURA',
}

FRASES_EXCLUIDAS = {
    'Ley Orgánica de Telecomunicaciones',
    'Código Orgánico Administrativo',
    'Registro Oficial',
    'Agencia de Regulación y Control',
    'Sistema de Gestión Documental',
}


def normalizar_espacios(texto: str) -> str:
    """Normaliza espacios múltiples, tabs, newlines."""
    return re.sub(r'\s+', ' ', texto.strip())


def generar_variaciones_nombre(nombre: str) -> List[str]:
    """
    Genera variaciones de un nombre completo.

    Ejemplos:
        "SANTOS ORELLANA ADRIAN ALEXANDER" →
        ['SANTOS ORELLANA ADRIAN ALEXANDER',
         'ADRIAN ALEXANDER SANTOS ORELLANA',
         'SANTOS ORELLANA',
         'ADRIAN ALEXANDER']
    """
    nombre_limpio = normalizar_espacios(nombre)
    variaciones = [nombre_limpio]

    palabras = nombre_limpio.split()

    if len(palabras) >= 4:
        apellidos = palabras[:2]
        nombres = palabras[2:]
        variaciones.append(' '.join(nombres + apellidos))
        variaciones.append(' '.join(apellidos))
        variaciones.append(' '.join(nombres))
        variaciones.append(apellidos[0])
        variaciones.append(nombres[0])

    elif len(palabras) == 3:
        variaciones.append(f"{palabras[2]} {palabras[0]} {palabras[1]}")
        variaciones.append(f"{palabras[0]} {palabras[1]}")
        variaciones.append(f"{palabras[1]} {palabras[2]} {palabras[0]}")
        variaciones.append(f"{palabras[1]} {palabras[2]}")

    elif len(palabras) == 2:
        variaciones.append(f"{palabras[1]} {palabras[0]}")

    variaciones_unicas = []
    for v in variaciones:
        if v not in variaciones_unicas and len(v) >= 5:
            variaciones_unicas.append(v)

    return variaciones_unicas


def buscar_y_reemplazar_variaciones(
        texto: str,
        variaciones: List[str],
        pseudonimo: str
) -> Tuple[str, int]:
    """
    Busca todas las variaciones de un nombre y las reemplaza.

    CRÍTICO v2.1.2: Ordena variaciones de MÁS LARGA a MÁS CORTA.
    CRÍTICO v2.1.3: Permite saltos de línea entre palabras (\s+).
    """
    texto_resultado = texto
    total_reemplazos = 0

    variaciones_ordenadas = sorted(variaciones, key=len, reverse=True)

    for variacion in variaciones_ordenadas:
        variacion_flexible = re.escape(variacion).replace(r'\ ', r'\s+')
        patron = r'\b' + variacion_flexible + r'\b'

        matches = list(re.finditer(patron, texto_resultado, re.IGNORECASE))

        if matches:
            texto_resultado = re.sub(patron, pseudonimo, texto_resultado, flags=re.IGNORECASE)
            total_reemplazos += len(matches)
            logger.debug(f"   🔄 Variación '{variacion}' → {pseudonimo} ({len(matches)} veces)")

    return texto_resultado, total_reemplazos


def generate_pseudonym(prefix: str = "PSN") -> str:
    """Genera un pseudónimo único."""
    unique_id = str(uuid.uuid4())[:8].upper()
    return f"{prefix}_{unique_id}"


def is_exception(text: str) -> bool:
    """Verifica si un texto es una excepción conocida."""
    text_clean = text.strip()

    if text_clean.upper() in {e.upper() for e in EXCEPCIONES}:
        return True

    for frase in FRASES_EXCLUIDAS:
        if frase.lower() in text_clean.lower():
            return True

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
    Pseudonimiza un texto usando arquitectura híbrida v2.1.7.

    ARQUITECTURA DE 4 CAPAS:
    1. Regex: Datos estructurados (RUC, cédula, email, teléfono estándar)
    1.5. Encabezado: Nombres prestador/representante, dirección, teléfono sin prefijo
    2. spaCy NER: Nombres restantes con validación estricta (IGNORECASE v2.1.5)
    3. Firmantes: Extracción de sección de firmas
    """
    # Normalizar espacios OCR en secuencias numéricas que parecen RUC/cédula
    # Ej: "172473306600 1" → "1724733066001" (OCR insertó espacio en el dígito final)
    import re as _re
    text = _re.sub(
        r'(\d{10,12})\s(\d{1,3})(?=\D|$)',
        lambda m: m.group(1) + m.group(2) if len(m.group(1) + m.group(2)) in [10, 13] else m.group(0),
        text
    )

    pseudonymized_text = text
    mapping = {}
    processed_values: Set[str] = set()

    stats = {
        'regex_detections': 0,
        'encabezado_detections': 0,
        'spacy_detections': 0,
        'firmantes_detections': 0,
        'total_unique': 0,
        'total_reemplazos': 0
    }

    # ========== CAPA 1: REGEX DATOS ESTRUCTURADOS ==========
    logger.info("🔍 Capa 1: Detección con Regex (datos estructurados)...")

    for data_type, pattern in PATTERNS.items():
        matches = re.finditer(pattern, text, re.MULTILINE)

        for match in matches:
            original_value = match.group(0).strip()

            if original_value in processed_values:
                continue

            if is_exception(original_value):
                logger.debug(f"⏭️  Regex omitió excepción: {original_value}")
                continue

            cache_key = f"{session_id}:{data_type}:{original_value}"
            cached_pseudonym = redis_get(cache_key)

            if cached_pseudonym:
                pseudonym = cached_pseudonym
            else:
                prefix_map = {
                    'ruc': 'RUC',
                    'cedula': 'CEDULA',
                    'email': 'EMAIL',
                    'telefono': 'TELEFONO',
                    'direccion_interseccion': 'DIRECCION',
                }
                prefix = prefix_map.get(data_type, 'PSN')
                pseudonym = generate_pseudonym(prefix)

                encrypted_value = encrypt(original_value)
                reverse_key = f"{session_id}:reverse:{pseudonym}"
                ttl_seconds = settings.TTL_HOURS * 3600
                redis_set(reverse_key, encrypted_value, ttl_seconds)
                redis_set(cache_key, pseudonym, ttl_seconds)

                logger.info(f"✅ Regex detectó: {original_value} → {pseudonym}")
                stats['regex_detections'] += 1

            pseudonymized_text = pseudonymized_text.replace(original_value, pseudonym)
            mapping[pseudonym] = original_value
            processed_values.add(original_value)
            stats['total_reemplazos'] += 1

    # ========== CAPA 1.5: ENCABEZADO ==========
    logger.info("🔍 Capa 1.5: Extrayendo datos del ENCABEZADO...")

    encabezado = text[:1500]
    encabezado_normalizado = encabezado.replace('\n', ' ')
    encabezado_normalizado = re.sub(r'\s+', ' ', encabezado_normalizado)

    patrones_encabezado = {
        'prestador': r'(?:PRESTADOR\s+O\s+CONCESIONARIO|Poseedor\s+o\s+no.*?Habilitante)\s*:\s*([A-Za-záéíóúñÑ0-9\s\-\.&,]+?)(?=\s*Representante|REPRESENTANTE|Cédula|CEDULA|RUC)',
        'representante': r'REPRESENTANTE\s+LEGAL\s*:\s*([A-Za-záéíóúñÑ0-9\s\-\.&,]+?)(?=\s*Cédula|CEDULA|RUC)',
        # v2.1.7 BUG 1: \b evita match prematuro con "CIUDADELA"
        # v2.1.7 BUG 2: \u2013 captura em dash (–) en direcciones ecuatorianas
        'direccion': r'(?:Dirección|Direccion|DIRECCIÓN|DIRECCION)\s*:\s*([A-Za-záéíóúñÑ0-9\s\-\u2013\.&,/]+?)(?=\s*Ciudad\b|CIUDAD\b|Provincia\b|PROVINCIA\b|Correo\b|CORREO\b|$)',
        # v2.1.7 BUG 3: Teléfonos sin prefijo "0" (ej: "TELÉFONO: 84337197")
        'telefono_campo': r'(?:TELÉFONO|TELEFONO|Teléfono|Telefono)\s*[:\s]+(\d{7,10})(?:\s*/\s*\d{7,10})?',
    }

    for contexto, patron in patrones_encabezado.items():
        match = re.search(patron, encabezado_normalizado, re.IGNORECASE | re.MULTILINE)

        if match:
            nombre_original = match.group(1).strip()
            nombre_limpio = normalizar_espacios(nombre_original).strip('.')
            nombre_limpio = re.sub(r'[\s,\-\.]+$', '', nombre_limpio)

            longitud_minima = 5 if contexto == 'telefono_campo' else 10
            if len(nombre_limpio) < longitud_minima:
                continue

            data_type = f"encabezado_{contexto}"
            cache_key = f"{session_id}:{data_type}:{nombre_limpio}"
            cached_pseudonym = redis_get(cache_key)

            # v2.1.7 BUG 5: branch dedicado para telefono_campo y direccion
            if contexto == 'telefono_campo':
                variaciones = [nombre_limpio]
                prefix = 'TELEFONO'
            elif contexto == 'direccion':
                variaciones = [nombre_limpio]
                prefix = 'DIRECCION'
            else:
                variaciones = generar_variaciones_nombre(nombre_limpio)
                prefix = 'NOMBRE'
                logger.info(f"   📝 Nombre base ({contexto}): {nombre_limpio}")
                logger.info(f"   🔀 Variaciones generadas: {len(variaciones)}")

            if cached_pseudonym:
                pseudonym = cached_pseudonym
                logger.debug(f"   ♻️  Reutilizando pseudónimo: {pseudonym}")
            else:
                pseudonym = generate_pseudonym(prefix)
                encrypted_value = encrypt(nombre_limpio)
                reverse_key = f"{session_id}:reverse:{pseudonym}"
                ttl_seconds = settings.TTL_HOURS * 3600
                redis_set(reverse_key, encrypted_value, ttl_seconds)
                redis_set(cache_key, pseudonym, ttl_seconds)
                stats['encabezado_detections'] += 1

            pseudonymized_text, count = buscar_y_reemplazar_variaciones(
                pseudonymized_text,
                variaciones,
                pseudonym
            )

            if count > 0:
                logger.info(f"✅ Encabezado ({contexto}): {nombre_limpio} → {pseudonym} ({count} reemplazos)")
                mapping[pseudonym] = nombre_limpio
                processed_values.add(nombre_limpio)
                stats['total_reemplazos'] += count
            else:
                logger.warning(f"⚠️  Dato detectado pero no encontrado en texto: {nombre_limpio}")

    # ========== CAPA 2: spaCy ==========
    # v2.1.5: buscar_y_reemplazar_variaciones reemplaza str.replace (IGNORECASE)
    logger.info("🔍 Capa 2: Detección con spaCy NER...")

    entidades_spacy = detectar_entidades_spacy(text)

    for entidad in entidades_spacy:
        original_value = entidad["texto"].strip()
        original_value = normalizar_espacios(original_value)

        if original_value in processed_values:
            continue

        if is_exception(original_value):
            continue

        data_type = "nombre_persona"
        cache_key = f"{session_id}:{data_type}:{original_value}"
        cached_pseudonym = redis_get(cache_key)

        if cached_pseudonym:
            pseudonym = cached_pseudonym
        else:
            pseudonym = generate_pseudonym("NOMBRE")
            encrypted_value = encrypt(original_value)
            reverse_key = f"{session_id}:reverse:{pseudonym}"
            ttl_seconds = settings.TTL_HOURS * 3600
            redis_set(reverse_key, encrypted_value, ttl_seconds)
            redis_set(cache_key, pseudonym, ttl_seconds)
            stats['spacy_detections'] += 1

        variaciones = generar_variaciones_nombre(original_value)
        pseudonymized_text, count = buscar_y_reemplazar_variaciones(
            pseudonymized_text,
            variaciones,
            pseudonym
        )

        if count > 0:
            logger.info(f"✅ spaCy: {original_value} → {pseudonym} ({count} reemplazos)")
            mapping[pseudonym] = original_value
            processed_values.add(original_value)
            stats['total_reemplazos'] += count
        else:
            logger.warning(f"⚠️ spaCy detectó pero no reemplazó (posible falso positivo): {original_value}")

    # ========== CAPA 3: FIRMANTES ==========
    # v2.1.6: Agrega Mgs. a patrones
    # v2.1.7 BUG 4: Corregido doble backslash → nunca hacían match
    logger.info("🔍 Capa 3: Extrayendo FIRMANTES...")

    seccion_firmas = text[-2000:]
    patrones_firmantes = [
        r'Elaborado\s+por:\s+([A-Za-záéíóúñÑ\s\.]+?)(?=\n|\s{2,})',
        r'Revisado\s+por:\s+([A-Za-záéíóúñÑ\s\.]+?)(?=\n|\s{2,})',
        r'Aprobado\s+por:\s+([A-Za-záéíóúñÑ\s\.]+?)(?=\n|\s{2,})',
        r'Ing\.\s+([A-Za-záéíóúñÑ\s\.]+?)(?=\n|\s{2,})',
        r'Econ\.\s+([A-Za-záéíóúñÑ\s\.]+?)(?=\n|\s{2,})',
        r'Dr\.\s+([A-Za-záéíóúñÑ\s\.]+?)(?=\n|\s{2,})',
        r'Mgs\.\s+([A-Za-záéíóúñÑ\s\.]+?)(?=\n|\s{2,})',  # v2.1.6
    ]

    for patron in patrones_firmantes:
        for match in re.finditer(patron, seccion_firmas, re.MULTILINE):
            nombre_original = match.group(1).strip()
            nombre_limpio = normalizar_espacios(nombre_original).strip('.')

            if len(nombre_limpio) >= 5 and nombre_limpio not in processed_values:
                data_type = "nombre_firmante"
                cache_key = f"{session_id}:{data_type}:{nombre_limpio}"
                cached_pseudonym = redis_get(cache_key)

                if cached_pseudonym:
                    pseudonym = cached_pseudonym
                else:
                    pseudonym = generate_pseudonym("NOMBRE")
                    encrypted_value = encrypt(nombre_limpio)
                    reverse_key = f"{session_id}:reverse:{pseudonym}"
                    ttl_seconds = settings.TTL_HOURS * 3600
                    redis_set(reverse_key, encrypted_value, ttl_seconds)
                    redis_set(cache_key, pseudonym, ttl_seconds)
                    stats['firmantes_detections'] += 1

                pseudonymized_text = pseudonymized_text.replace(nombre_limpio, pseudonym)
                mapping[pseudonym] = nombre_limpio
                processed_values.add(nombre_limpio)
                stats['total_reemplazos'] += 1

    # ========== ESTADÍSTICAS ==========
    stats['total_unique'] = len(mapping)

    logger.info(f"📊 Estadísticas de detección:")
    logger.info(f"   - Regex: {stats['regex_detections']}")
    logger.info(f"   - Encabezado: {stats['encabezado_detections']}")
    logger.info(f"   - spaCy: {stats['spacy_detections']}")
    logger.info(f"   - Firmantes: {stats['firmantes_detections']}")
    logger.info(f"   - Total únicos: {stats['total_unique']}")
    logger.info(f"   - Total reemplazos: {stats['total_reemplazos']}")

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
            except Exception as e:
                logger.error(f"❌ Error descifrando {pseudonym}: {e}")

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
