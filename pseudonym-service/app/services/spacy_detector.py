"""
Detector de entidades nombradas usando spaCy NER.

SOLO DETECTA PERSONAS (PER) con validación estricta:
- Títulos profesionales: Ing., Dr., Econ., Abg., etc.
- Apellidos en mayúsculas
- Longitud 10-60 caracteres
- Rechaza verbos, palabras institucionales, y términos genéricos

Las ubicaciones específicas se detectan con Regex (direcciones, intersecciones).
"""
import spacy
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# Cargar modelo una sola vez (al iniciar el servicio)
try:
    nlp = spacy.load("es_core_news_lg")
    logger.info("✅ Modelo spaCy cargado correctamente")
except Exception as e:
    logger.error(f"❌ Error cargando spaCy: {e}")
    nlp = None


def detectar_entidades_spacy(texto: str) -> List[Dict]:
    """
    Detecta entidades nombradas usando spaCy NER.

    SOLO DETECTA PERSONAS (PER), ignora ubicaciones (LOC).
    Las ubicaciones específicas ya se detectan con Regex.

    Args:
        texto: Texto a analizar

    Returns:
        List[Dict]: Lista de PERSONAS detectadas y validadas
    """
    if not nlp:
        logger.warning("⚠️ spaCy no disponible, retornando lista vacía")
        return []

    try:
        doc = nlp(texto)
        entidades = []

        for ent in doc.ents:
            # ===== SOLO PERSONAS (PER) =====
            if ent.label_ != "PER":
                continue

            # Validación estricta para nombres
            if not es_nombre_real(ent.text):
                logger.debug(f"⏭️ spaCy rechazó nombre: {ent.text}")
                continue

            # Si pasó las validaciones, agregar
            entidades.append({
                "texto": ent.text,
                "tipo": ent.label_,
                "inicio": ent.start_char,
                "fin": ent.end_char
            })

        logger.info(
            f"✅ spaCy detectó {len(entidades)} PERSONAS validadas (de {len([e for e in doc.ents if e.label_ == 'PER'])} personas totales)")
        return entidades

    except Exception as e:
        logger.error(f"❌ Error en detección spaCy: {e}")
        return []


def es_nombre_real(texto: str) -> bool:
    """
    Verifica si un texto detectado por spaCy es realmente un nombre personal.

    FILTROS ESTRICTOS para evitar falsos positivos.

    Args:
        texto: Texto a verificar

    Returns:
        bool: True si parece un nombre real
    """
    # Palabras que indican que NO es un nombre personal
    palabras_institucionales = {
        'dirección', 'coordinación', 'unidad', 'técnica', 'administrativa',
        'financiera', 'gestión', 'control', 'registro', 'agencia',
        'ministerio', 'secretaría', 'departamento', 'división',
        'ley', 'reglamento', 'código', 'estatuto', 'manual',
        'servicio', 'sistema', 'procedimiento', 'proceso',
        'arcotel', 'telecomunicaciones', 'títulos', 'habilitantes',
        'orgánica', 'administrativo', 'sancionador', 'certificación',
        'remisión', 'elaborar', 'certifico', 'certificar', 'quinta',
        'documental', 'quipux', 'equinoccial', 'provincia'
    }

    # Verbos comunes que NO son nombres
    verbos = {
        'elaborar', 'certificar', 'certifico', 'remitir', 'enviar',
        'solicitar', 'aprobar', 'rechazar', 'validar', 'verificar'
    }

    # Convertir a minúsculas para comparación
    texto_lower = texto.lower()
    texto_clean = texto.strip()

    # FILTRO 1: Contiene palabras institucionales
    for palabra in palabras_institucionales:
        if palabra in texto_lower:
            return False

    # FILTRO 2: Contiene verbos
    for verbo in verbos:
        if verbo in texto_lower:
            return False

    # FILTRO 3: Debe tener al menos 2 palabras completas
    palabras = texto_clean.split()
    if len(palabras) < 2:
        return False

    # FILTRO 4: Máximo 5 palabras (nombres muy largos son sospechosos)
    if len(palabras) > 5:
        return False

    # FILTRO 5: Longitud razonable (entre 10 y 60 caracteres)
    # Más estricto que antes
    if len(texto_clean) < 10 or len(texto_clean) > 60:
        return False

    # FILTRO 6: Debe contener al menos un título profesional o apellido típico
    # Si empieza con Ing., Dr., Econ., Abg., etc. es más probable que sea nombre real
    titulos = ['ing.', 'dr.', 'econ.', 'abg.', 'msc.', 'phd.', 'mgtr.', 'lic.']
    tiene_titulo = any(titulo in texto_lower for titulo in titulos)

    # FILTRO 7: No debe contener caracteres sospechosos
    caracteres_invalidos = ['→', '←', '•', '○', '●', '\n', '\t']
    for char in caracteres_invalidos:
        if char in texto_clean:
            return False

    # FILTRO 8: No debe tener palabras cortadas (menos de 3 caracteres sin título)
    for palabra in palabras:
        palabra_limpia = palabra.strip('.,;:')
        # Ignorar títulos cortos
        if palabra_limpia.lower() not in ['ing', 'dr', 'sr', 'sra', 'ab', 'de', 'la', 'y']:
            if len(palabra_limpia) < 3:
                return False

    # FILTRO 9: Debe tener apellidos (palabras en mayúscula sostenida)
    palabras_mayusculas = sum(1 for p in palabras if p.isupper() and len(p) > 3)

    # Si tiene título profesional, es muy probable que sea nombre real
    if tiene_titulo and palabras_mayusculas >= 1:
        return True

    # Sin título, debe tener al menos 2 palabras en mayúscula (apellidos)
    if palabras_mayusculas >= 2:
        return True

    # Rechazar todo lo demás
    return False
