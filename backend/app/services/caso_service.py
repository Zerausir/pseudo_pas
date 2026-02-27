"""
Servicio para gestionar casos PAS en base de datos.
Versión 3.0 - AGREGADO: guardar_peticion_razonada para vincular Peticiones con Informes
"""

import json
from datetime import datetime, date
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


# ========================================
# FUNCIÓN AUXILIAR: CONVERTIR FECHAS
# ========================================

def _convert_dates_to_str(obj):
    """
    Convierte recursivamente objetos date/datetime a strings ISO.
    Necesario porque PostgreSQL JSONB no acepta objetos Python date.

    Args:
        obj: Objeto a convertir (dict, list, date, datetime, o primitivo)

    Returns:
        Objeto con fechas convertidas a strings
    """
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _convert_dates_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_dates_to_str(item) for item in obj]
    return obj


# ========================================
# FUNCIÓN PRINCIPAL: GUARDAR INFORME
# ========================================

def guardar_informe_tecnico(db: Session, datos_extraidos: dict) -> int:
    """
    Guarda Informe Técnico en BD siguiendo el schema real simplificado.

    Tablas afectadas:
    1. prestadores: Inserta/actualiza prestador
    2. casos_pas: Crea nuevo caso PAS
    3. documentos_pas: Guarda documento con JSON completo

    Args:
        db: Sesión de SQLAlchemy
        datos_extraidos: Diccionario con datos del informe

    Returns:
        int: ID del caso creado

    Raises:
        Exception: Si hay error en BD
    """
    try:
        # ========================================
        # 1. INSERTAR/ACTUALIZAR PRESTADOR
        # ========================================

        prestador_data = datos_extraidos.get('prestador', {})

        # Normalizar emails como lista Python (psycopg2 lo convierte automáticamente a array PG)
        emails_list = prestador_data.get('emails', [])
        if isinstance(emails_list, str):
            emails_list = [emails_list]
        if not emails_list:
            emails_list = []

        query_prestador = text("""
            INSERT INTO prestadores (
                ruc, 
                razon_social, 
                representante_legal,
                direccion,
                ciudad,
                provincia,
                emails,
                created_at, 
                updated_at
            )
            VALUES (
                :ruc, 
                :razon_social, 
                :representante_legal,
                :direccion,
                :ciudad,
                :provincia,
                :emails,
                NOW(), 
                NOW()
            )
            ON CONFLICT (ruc) DO UPDATE 
            SET razon_social = EXCLUDED.razon_social,
                representante_legal = EXCLUDED.representante_legal,
                direccion = EXCLUDED.direccion,
                ciudad = EXCLUDED.ciudad,
                provincia = EXCLUDED.provincia,
                emails = EXCLUDED.emails,
                updated_at = NOW()
            RETURNING ruc
        """)

        result = db.execute(query_prestador, {
            'ruc': prestador_data.get('ruc'),
            'razon_social': prestador_data.get('nombre'),
            'representante_legal': prestador_data.get('representante_legal'),
            'direccion': prestador_data.get('direccion'),
            'ciudad': prestador_data.get('ciudad'),
            'provincia': prestador_data.get('provincia'),
            'emails': emails_list
        })

        prestador_ruc = result.fetchone()[0]
        logger.info(f"✅ Prestador guardado/actualizado: {prestador_ruc}")

        # ========================================
        # 2. CREAR CASO PAS
        # ========================================

        infraccion_data = datos_extraidos.get('infraccion', {})

        query_caso = text("""
            INSERT INTO casos_pas (
                prestador_ruc,
                infraccion_tipo,
                fecha_infraccion,
                estado,
                created_at,
                updated_at
            )
            VALUES (
                :prestador_ruc,
                :infraccion_tipo,
                :fecha_infraccion,
                :estado,
                NOW(),
                NOW()
            )
            RETURNING id
        """)

        result = db.execute(query_caso, {
            'prestador_ruc': prestador_ruc,
            'infraccion_tipo': infraccion_data.get('tipo', 'garantia_gfc_tardia'),
            'fecha_infraccion': infraccion_data.get('fecha_real_entrega'),
            'estado': 'extraido'
        })

        caso_id = result.fetchone()[0]
        logger.info(f"✅ Caso PAS creado con ID: {caso_id}")

        # ========================================
        # 3. CREAR DOCUMENTO
        # ========================================

        # Convertir fechas a strings para JSONB
        contenido_json = _convert_dates_to_str(datos_extraidos)

        # Buscar 'archivo_nombre'
        archivo_nombre = datos_extraidos.get('archivo_nombre')
        if not archivo_nombre and 'archivo_path' in datos_extraidos:
            # Extraer nombre del path si existe
            from pathlib import Path
            archivo_nombre = Path(datos_extraidos['archivo_path']).name

        query_documento = text("""
            INSERT INTO documentos_pas (
                caso_id,
                tipo,
                numero,
                fecha,
                contenido_json,
                archivo_nombre,
                created_at
            )
            VALUES (
                :caso_id,
                :tipo,
                :numero,
                :fecha,
                CAST(:contenido_json AS jsonb),
                :archivo_nombre,
                NOW()
            )
            RETURNING id
        """)

        result = db.execute(query_documento, {
            'caso_id': caso_id,
            'tipo': 'informe_tecnico',
            'numero': datos_extraidos.get('numero'),
            'fecha': datos_extraidos.get('fecha'),
            'contenido_json': json.dumps(contenido_json),
            'archivo_nombre': archivo_nombre
        })

        documento_id = result.fetchone()[0]
        logger.info(f"✅ Documento guardado con ID: {documento_id} (archivo: {archivo_nombre})")

        # Commit de la transacción
        db.commit()

        return caso_id

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error guardando en BD: {str(e)}")
        raise


# ========================================
# FUNCIÓN: GUARDAR PETICIÓN RAZONADA (NUEVO)
# ========================================

def guardar_peticion_razonada(db: Session, datos_extraidos: dict) -> Tuple[int, int]:
    """
    Guarda Petición Razonada y la vincula con el Informe Técnico existente.

    Versión 2.1: Búsqueda flexible para ambos formatos de número de informe:
    - Formato antiguo: CTDG-GE-2025-XXXX (año al final)
    - Formato nuevo 2025: CTDG-2025-GE-XXXX (año al principio)

    DIFERENCIAS vs guardar_informe_tecnico:
    1. NO crea caso nuevo, ACTUALIZA caso existente
    2. Busca caso por número de informe base (informe_base.numero)
    3. Copia RUC del informe si no está en la petición
    4. Actualiza estado del caso a 'peticion_razonada'

    Tablas afectadas:
    1. casos_pas: Busca y actualiza caso existente
    2. prestadores: Actualiza nombre si cambió
    3. documentos_pas: Inserta petición vinculada al caso

    Args:
        db: Sesión de SQLAlchemy
        datos_extraidos: Diccionario con datos de la petición
            Campos requeridos:
            - informe_base.numero: Para buscar el caso
            - prestador_nombre: Nombre del prestador
            - prestador_ruc: RUC (opcional, se copia del informe si es null)

    Returns:
        Tuple[int, int]: (caso_id, documento_id)

    Raises:
        Exception: Si no encuentra el informe base o error en BD
    """
    try:
        informe_base = datos_extraidos.get('informe_base', {})
        numero_informe = informe_base.get('numero')

        if not numero_informe:
            raise ValueError("Petición Razonada debe tener 'informe_base.numero' para vincular con caso")

        # Normalizar: eliminar prefijo "IT-" si lo incluyó el extractor
        # (documentos 2021 referencian el informe como "IT-CTDG-GE-2021-XXXX")
        if numero_informe.upper().startswith('IT-'):
            numero_informe = numero_informe[3:]
            logger.info(f"   ℹ️  Prefijo IT- eliminado: {numero_informe}")

        logger.info(f"🔍 Buscando caso existente para informe: {numero_informe}")

        # ========================================
        # NUEVO v2.1: GENERAR FORMATO ALTERNATIVO
        # ========================================

        def generar_formato_alternativo(numero: str) -> str:
            """
            Genera el formato alternativo del número de informe.

            Ejemplos:
            - CTDG-GE-2025-0335 → CTDG-2025-GE-0335
            - CTDG-2025-GE-0335 → CTDG-GE-2025-0335
            """
            import re

            # Formato antiguo: CTDG-GE-2025-0335
            patron_antiguo = r'^(\w+)-GE-(\d{4})-(\d+)$'
            match_antiguo = re.match(patron_antiguo, numero)

            if match_antiguo:
                unidad, anio, consecutivo = match_antiguo.groups()
                # Convertir a formato nuevo: CTDG-2025-GE-0335
                return f"{unidad}-{anio}-GE-{consecutivo}"

            # Formato nuevo: CTDG-2025-GE-0335
            patron_nuevo = r'^(\w+)-(\d{4})-GE-(\d+)$'
            match_nuevo = re.match(patron_nuevo, numero)

            if match_nuevo:
                unidad, anio, consecutivo = match_nuevo.groups()
                # Convertir a formato antiguo: CTDG-GE-2025-0335
                return f"{unidad}-GE-{anio}-{consecutivo}"

            # Si no coincide con ningún patrón, retornar el mismo
            return numero

        numero_alternativo = generar_formato_alternativo(numero_informe)

        logger.info(f"   • Formato original: {numero_informe}")
        logger.info(f"   • Formato alternativo: {numero_alternativo}")

        # ========================================
        # 1. BUSCAR CASO CON AMBOS FORMATOS
        # ========================================

        query_buscar_caso = text("""
            SELECT 
                c.id,
                c.prestador_ruc,
                c.infraccion_tipo,
                c.estado,
                d.numero as numero_informe_real
            FROM casos_pas c
            JOIN documentos_pas d ON c.id = d.caso_id
            WHERE (d.numero = :numero_informe OR d.numero = :numero_alternativo)
            AND d.tipo = 'informe_tecnico'
            ORDER BY c.created_at DESC
            LIMIT 1
        """)

        result = db.execute(query_buscar_caso, {
            'numero_informe': numero_informe,
            'numero_alternativo': numero_alternativo
        })
        caso_existente = result.fetchone()

        if not caso_existente:
            raise ValueError(
                f"No se encontró caso PAS con informe técnico '{numero_informe}' "
                f"ni con formato alternativo '{numero_alternativo}'. "
                "Debe procesarse el informe técnico ANTES de la petición razonada."
            )

        caso_id, prestador_ruc_caso, infraccion_tipo, estado_actual, numero_real = caso_existente
        logger.info(
            f"✅ Caso encontrado: ID={caso_id}, Informe={numero_real}, RUC={prestador_ruc_caso}, Estado={estado_actual}")

        # ========================================
        # 2. VERIFICAR/ACTUALIZAR PRESTADOR
        # ========================================

        prestador_nombre = datos_extraidos.get('prestador_nombre')
        prestador_ruc = datos_extraidos.get('prestador_ruc')

        # Si no hay RUC en petición, copiar del caso
        if not prestador_ruc:
            prestador_ruc = prestador_ruc_caso
            logger.info(f"   ℹ️ RUC copiado del informe: {prestador_ruc}")

        # Actualizar nombre del prestador si es necesario
        if prestador_nombre:
            query_actualizar_prestador = text("""
                UPDATE prestadores
                SET razon_social = :razon_social,
                    updated_at = NOW()
                WHERE ruc = :ruc
            """)

            db.execute(query_actualizar_prestador, {
                'ruc': prestador_ruc,
                'razon_social': prestador_nombre
            })
            logger.info(f"   ℹ️ Nombre prestador actualizado: {prestador_nombre}")

        # ========================================
        # 3. VERIFICAR CONSISTENCIA
        # ========================================

        # Advertir si hay inconsistencias (pero NO falla)
        if datos_extraidos.get('prestador_ruc') and datos_extraidos['prestador_ruc'] != prestador_ruc_caso:
            logger.warning(
                f"⚠️ RUC en petición ({datos_extraidos['prestador_ruc']}) "
                f"difiere del informe ({prestador_ruc_caso}). "
                f"Usando RUC del informe: {prestador_ruc_caso}"
            )

        # ========================================
        # 4. ACTUALIZAR ESTADO DEL CASO
        # ========================================

        query_actualizar_caso = text("""
            UPDATE casos_pas
            SET estado = :nuevo_estado,
                updated_at = NOW()
            WHERE id = :caso_id
        """)

        db.execute(query_actualizar_caso, {
            'caso_id': caso_id,
            'nuevo_estado': 'peticion_razonada'
        })
        logger.info(f"✅ Estado del caso actualizado: {estado_actual} → peticion_razonada")

        # ========================================
        # 5. INSERTAR DOCUMENTO PETICIÓN
        # ========================================

        # Convertir fechas a strings para JSONB
        contenido_json = _convert_dates_to_str(datos_extraidos)

        # Buscar 'archivo_nombre'
        archivo_nombre = datos_extraidos.get('archivo_nombre')
        if not archivo_nombre and 'archivo_path' in datos_extraidos:
            from pathlib import Path
            archivo_nombre = Path(datos_extraidos['archivo_path']).name

        query_documento = text("""
            INSERT INTO documentos_pas (
                caso_id,
                tipo,
                numero,
                fecha,
                contenido_json,
                archivo_nombre,
                created_at
            )
            VALUES (
                :caso_id,
                :tipo,
                :numero,
                :fecha,
                CAST(:contenido_json AS jsonb),
                :archivo_nombre,
                NOW()
            )
            RETURNING id
        """)

        result = db.execute(query_documento, {
            'caso_id': caso_id,
            'tipo': 'peticion_razonada',
            'numero': datos_extraidos.get('numero'),
            'fecha': datos_extraidos.get('fecha'),
            'contenido_json': json.dumps(contenido_json),
            'archivo_nombre': archivo_nombre
        })

        documento_id = result.fetchone()[0]
        logger.info(f"✅ Petición guardada con ID: {documento_id} (archivo: {archivo_nombre})")

        # Commit de la transacción
        db.commit()

        logger.info(
            f"🎯 Petición vinculada exitosamente: "
            f"Caso {caso_id} ← Petición {datos_extraidos.get('numero')} "
            f"← Informe {numero_real}"
        )

        return caso_id, documento_id

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error guardando petición razonada: {str(e)}")
        raise


# ========================================
# FUNCIÓN: GUARDAR VALIDACIÓN
# ========================================

def guardar_validacion(db: Session, documento_id: int, reporte_validacion: dict) -> int:
    """
    Guarda el reporte de validación de consistencia en la BD.

    Args:
        db: Sesión de SQLAlchemy
        documento_id: ID del documento validado
        reporte_validacion: Dict con resultado de ValidadorInformeTecnico.validar()

    Returns:
        int: ID de la validación creada

    Raises:
        Exception: Si hay error en BD
    """
    try:
        query = text("""
            INSERT INTO validaciones_informe (
                documento_id,
                es_valido,
                total_inconsistencias,
                num_info,
                num_warnings,
                num_errors,
                num_critical,
                inconsistencias,
                validador_version,
                created_at
            )
            VALUES (
                :documento_id,
                :es_valido,
                :total_inconsistencias,
                :num_info,
                :num_warnings,
                :num_errors,
                :num_critical,
                CAST(:inconsistencias AS jsonb),
                :validador_version,
                NOW()
            )
            RETURNING id
        """)

        contadores = reporte_validacion.get('contadores', {})

        result = db.execute(query, {
            'documento_id': documento_id,
            'es_valido': reporte_validacion.get('es_valido', False),
            'total_inconsistencias': reporte_validacion.get('total_inconsistencias', 0),
            'num_info': contadores.get('info', 0),
            'num_warnings': contadores.get('warnings', 0),
            'num_errors': contadores.get('errors', 0),
            'num_critical': contadores.get('critical', 0),
            'inconsistencias': json.dumps(reporte_validacion.get('inconsistencias', [])),
            'validador_version': '1.0'
        })

        validacion_id = result.fetchone()[0]

        # Commit
        db.commit()

        logger.info(
            f"✅ Validación guardada con ID: {validacion_id} "
            f"(documento: {documento_id}, válido: {reporte_validacion.get('es_valido')})"
        )

        return validacion_id

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Error guardando validación: {str(e)}")
        raise


# ========================================
# FUNCIONES AUXILIARES DE CONSULTA
# ========================================

def obtener_caso_por_numero(db: Session, numero_informe: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene un caso PAS por número de informe técnico.

    Args:
        db: Sesión de SQLAlchemy
        numero_informe: Número del informe técnico (ej: "CTDG-GE-2022-0487")

    Returns:
        Dict con datos del caso o None si no existe
    """
    try:
        query = text("""
            SELECT 
                c.id,
                c.prestador_ruc,
                c.infraccion_tipo,
                c.estado,
                p.razon_social
            FROM casos_pas c
            JOIN prestadores p ON c.prestador_ruc = p.ruc
            JOIN documentos_pas d ON c.id = d.caso_id
            WHERE d.numero = :numero_informe
            AND d.tipo = 'informe_tecnico'
            LIMIT 1
        """)

        result = db.execute(query, {'numero_informe': numero_informe})
        row = result.fetchone()

        if row:
            return {
                'id': row[0],
                'prestador_ruc': row[1],
                'infraccion_tipo': row[2],
                'estado': row[3],
                'razon_social': row[4]
            }
        return None

    except Exception as e:
        logger.error(f"Error buscando caso: {str(e)}")
        return None


def contar_casos(db: Session) -> int:
    """
    Cuenta total de casos PAS en la BD.

    Args:
        db: Sesión de SQLAlchemy

    Returns:
        int: Número total de casos
    """
    try:
        result = db.execute(text("SELECT COUNT(*) FROM casos_pas"))
        return result.scalar()
    except Exception as e:
        logger.error(f"Error contando casos: {str(e)}")
        return 0
