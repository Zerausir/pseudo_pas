"""
API Endpoints para procesamiento controlado de Informes Técnicos.
Versión 4.0 - VALIDACIÓN OBLIGATORIA DE PSEUDONIMIZACIÓN
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
from pathlib import Path
import sys
from sqlalchemy import text

# Imports corregidos para estructura Docker
from backend.app.extractors.informe_tecnico_extractor import extraer_informe_tecnico
from backend.app.extractors.peticion_razonada_extractor import extraer_peticion_razonada
from backend.app.validators.validador_informe import ValidadorInformeTecnico
from backend.app.services.caso_service import (
    guardar_informe_tecnico,
    guardar_peticion_razonada,
    guardar_validacion
)
from backend.app.database import get_db
from datetime import datetime

router = APIRouter(tags=["procesador"])

# Configuración
DATA_DIR = Path("/app/data")

# ========================================
# CONFIGURACIÓN DE TIPOS DE DOCUMENTO
# ========================================
TIPOS_DOCUMENTO = {
    'informes_tecnicos': {
        'nombre': 'Informe Técnico',
        'extractor': 'informe_tecnico',
        'descripcion': 'Informes técnicos de CTDG (CTDG-GE-YYYY-XXXX.pdf)',
        'tabla_bd': 'informe_tecnico'
    },
    'peticiones_razonadas': {
        'nombre': 'Petición Razonada',
        'extractor': 'peticion_razonada',
        'descripcion': 'Peticiones razonadas de CCDS/CCDE (XXXX-PR-YYYY-ZZZZ.pdf)',
        'tabla_bd': 'peticion_razonada'
    },
    # Futuro: Agregar más tipos conforme se implementen
    # 'actos_inicio': {
    #     'nombre': 'Acto de Inicio',
    #     'extractor': 'acto_inicio',
    #     'descripcion': 'Actos de inicio de PAS',
    #     'tabla_bd': 'acto_inicio'
    # },
}


# ========================================
# SCHEMAS
# ========================================

class ArchivoInfo(BaseModel):
    """Información de un archivo disponible para procesar."""
    nombre: str
    ruta_completa: str
    tipo_documento: str  # NUEVO: 'Informe Técnico', 'Petición Razonada', etc.
    subdirectorio: str  # NUEVO: 'informes_tecnicos', 'peticiones_razonadas', etc.
    ya_procesado: bool
    fecha_procesamiento: Optional[str] = None
    numero_documento: Optional[str] = None
    prestador_ruc: Optional[str] = None
    version: Optional[int] = None
    caso_id: Optional[int] = None


class ProcesarRequest(BaseModel):
    """Request para procesar archivos seleccionados."""
    archivos: List[str]  # Lista de nombres de archivo
    forzar_reprocesar: bool = False  # Si True, crea nueva versión

    # ========== NUEVO v4.0: VALIDACIÓN OBLIGATORIA ==========
    session_id: Optional[str] = None  # Session ID de la validación previa
    confirmado: bool = False  # Usuario confirmó que todo está pseudonimizado


class ValidacionInfo(BaseModel):
    """Información de validación de un documento."""
    es_valido: bool
    total_inconsistencias: int
    num_errors: int
    num_critical: int


class ProcesarResponse(BaseModel):
    """Respuesta del procesamiento."""
    exitosos: int
    fallidos: int
    reprocesados: int
    detalles: List[dict]
    costo_total_usd: float = 0.0
    tokens_total_input: int = 0
    tokens_total_output: int = 0
    tokens_total: int = 0


# ========================================
# FUNCIONES AUXILIARES
# ========================================

def detectar_tipo_documento(ruta_completa: str, nombre: str) -> tuple:
    """
    Detecta el tipo de documento basándose en su ubicación.

    Args:
        ruta_completa: Ruta completa al archivo
        nombre: Nombre del archivo

    Returns:
        tuple: (tipo_documento, subdirectorio) o (None, None) si no se puede detectar
    """
    path = Path(ruta_completa)

    # Verificar si está en un subdirectorio conocido
    for subdir, config in TIPOS_DOCUMENTO.items():
        subdir_path = DATA_DIR / subdir
        try:
            # Verificar si el archivo está dentro del subdirectorio
            path.relative_to(subdir_path)
            return config['nombre'], subdir
        except ValueError:
            # No está en este subdirectorio, continuar
            continue

    # Si no está en ningún subdirectorio conocido
    return None, None


def crear_estructura_directorios():
    """
    Crea la estructura de subdirectorios si no existe.
    Se ejecuta al iniciar el servidor.
    """
    for subdir in TIPOS_DOCUMENTO.keys():
        subdir_path = DATA_DIR / subdir
        if not subdir_path.exists():
            subdir_path.mkdir(parents=True, exist_ok=True)
            print(f"📁 Creado subdirectorio: {subdir_path}")


# ========================================
# ENDPOINTS
# ========================================

@router.get("/archivos/listar", response_model=List[ArchivoInfo])
async def listar_archivos():
    """
    Lista todos los PDFs organizados por subdirectorios con su estado de procesamiento.

    Escanea:
    - /app/data/informes_tecnicos/*.pdf
    - /app/data/peticiones_razonadas/*.pdf
    - /app/data/*.pdf (archivos en raíz - con advertencia)
    """
    archivos_info = []

    # Crear estructura si no existe
    crear_estructura_directorios()

    # Conectar a BD para verificar cuáles ya fueron procesados
    db = next(get_db())

    # 1. ESCANEAR SUBDIRECTORIOS
    for subdir, config in TIPOS_DOCUMENTO.items():
        subdir_path = DATA_DIR / subdir

        if not subdir_path.exists():
            continue

        pdf_files = sorted(subdir_path.glob("*.pdf"))

        for pdf_path in pdf_files:
            nombre = pdf_path.name

            # Verificar si ya fue procesado
            query = """
                SELECT 
                    d.numero,
                    d.fecha,
                    d.contenido_json->>'version' as version,
                    c.id as caso_id,
                    c.prestador_ruc
                FROM documentos_pas d
                LEFT JOIN casos_pas c ON d.caso_id = c.id
                WHERE d.archivo_nombre = :nombre
                ORDER BY d.id DESC
                LIMIT 1
            """

            resultado = db.execute(text(query), {"nombre": nombre}).fetchone()

            if resultado:
                archivos_info.append(ArchivoInfo(
                    nombre=nombre,
                    ruta_completa=str(pdf_path),
                    tipo_documento=config['nombre'],
                    subdirectorio=subdir,
                    ya_procesado=True,
                    fecha_procesamiento=str(resultado[1]) if resultado[1] else None,
                    numero_documento=resultado[0],
                    prestador_ruc=resultado[4],
                    version=int(resultado[2]) if resultado[2] else 1,
                    caso_id=resultado[3]
                ))
            else:
                archivos_info.append(ArchivoInfo(
                    nombre=nombre,
                    ruta_completa=str(pdf_path),
                    tipo_documento=config['nombre'],
                    subdirectorio=subdir,
                    ya_procesado=False
                ))

    # 2. ESCANEAR RAÍZ (archivos huérfanos - retrocompatibilidad)
    pdf_files_raiz = sorted(DATA_DIR.glob("*.pdf"))

    for pdf_path in pdf_files_raiz:
        nombre = pdf_path.name

        # Verificar si ya fue procesado
        query = """
            SELECT 
                d.numero,
                d.fecha,
                d.contenido_json->>'version' as version,
                c.id as caso_id,
                c.prestador_ruc
            FROM documentos_pas d
            LEFT JOIN casos_pas c ON d.caso_id = c.id
            WHERE d.archivo_nombre = :nombre
            ORDER BY d.id DESC
            LIMIT 1
        """

        resultado = db.execute(text(query), {"nombre": nombre}).fetchone()

        # Marcar como tipo desconocido
        if resultado:
            archivos_info.append(ArchivoInfo(
                nombre=nombre,
                ruta_completa=str(pdf_path),
                tipo_documento="⚠️ Sin clasificar (en raíz)",
                subdirectorio="",
                ya_procesado=True,
                fecha_procesamiento=str(resultado[1]) if resultado[1] else None,
                numero_documento=resultado[0],
                prestador_ruc=resultado[4],
                version=int(resultado[2]) if resultado[2] else 1,
                caso_id=resultado[3]
            ))
        else:
            archivos_info.append(ArchivoInfo(
                nombre=nombre,
                ruta_completa=str(pdf_path),
                tipo_documento="⚠️ Sin clasificar (en raíz)",
                subdirectorio="",
                ya_procesado=False
            ))

    db.close()
    return archivos_info


@router.post("/archivos/procesar", response_model=ProcesarResponse)
async def procesar_archivos(request: ProcesarRequest):
    """
    Procesa los archivos seleccionados CON VALIDACIÓN OBLIGATORIA.

    ⚠️ NUEVO v4.0: VALIDACIÓN OBLIGATORIA DE PSEUDONIMIZACIÓN
    ============================================================
    ANTES de procesar, el usuario DEBE:
    1. Llamar a POST /api/validacion/previsualizar
    2. Descargar y revisar el HTML generado
    3. Confirmar que TODOS los datos personales están pseudonimizados
    4. Llamar a este endpoint con session_id y confirmado=true

    Sin confirmación previa, se RECHAZA el procesamiento (LOPDP Art. 8).

    Flujo:
    1. ✅ VALIDA que confirmado=true y session_id existe
    2. Detecta tipo de documento por subdirectorio
    3. Llama al extractor correspondiente (informe_tecnico o peticion_razonada)
    4. Valida consistencia de los datos extraídos
    5. Guarda en BD
    6. Guarda reporte de validación

    ⚡ ORDENAMIENTO AUTOMÁTICO:
    Los archivos se procesan en este orden garantizado:
    1. Informes Técnicos (base de los casos PAS)
    2. Peticiones Razonadas (requieren informes previos)
    3. Otros documentos

    Si un archivo ya fue procesado:
    - Y forzar_reprocesar=False: retorna error
    - Y forzar_reprocesar=True: crea nueva versión del documento
    """

    # ============================================
    # NUEVO v4.0: VALIDACIÓN OBLIGATORIA
    # ============================================
    print("\n" + "🔒" * 30)
    print("⚠️  VALIDACIÓN DE PSEUDONIMIZACIÓN OBLIGATORIA")
    print("🔒" * 30)

    if not request.confirmado:
        print("❌ RECHAZADO: Usuario no confirmó validación")
        raise HTTPException(
            status_code=403,
            detail={
                "error": "CONFIRMACIÓN REQUERIDA - CUMPLIMIENTO LOPDP",
                "mensaje": "Debe validar la pseudonimización antes de procesar documentos",
                "motivo": "Protección de datos personales según LOPDP Ecuador Art. 8 (Consentimiento Informado)",
                "pasos_requeridos": [
                    "1. POST /api/validacion/previsualizar con el(los) archivo(s)",
                    "2. Descargar el HTML generado",
                    "3. Revisar MANUALMENTE que TODO el texto está pseudonimizado",
                    "4. Verificar que NO aparecen nombres, cédulas, emails o direcciones REALES",
                    "5. Solo si TODO está correcto, llamar a este endpoint con:",
                    "   - session_id: (el recibido en paso 1)",
                    "   - confirmado: true"
                ],
                "documentacion": "Ver PSEUDONIMIZACION_ARQUITECTURA.md sección 4.3",
                "cumplimiento_legal": "LOPDP Ecuador Arts. 8, 10.e, 33, 37, 68"
            }
        )

    if not request.session_id:
        print("❌ RECHAZADO: session_id no proporcionado")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "SESSION_ID REQUERIDO",
                "mensaje": "Debe proporcionar el session_id obtenido en la validación previa",
                "ejemplo": {
                    "session_id": "pseudosession_20260211_203045_a1b2c3d4",
                    "confirmado": True
                }
            }
        )

    print(f"✅ Validación confirmada por usuario")
    print(f"✅ Session ID: {request.session_id}")
    print(f"✅ Archivos a procesar: {len(request.archivos)}")
    print("🔒" * 30 + "\n")

    # ============================================
    # CONTINUAR CON PROCESAMIENTO NORMAL
    # ============================================

    exitosos = 0
    fallidos = 0
    reprocesados = 0
    detalles = []

    # Acumuladores de costo
    costo_total_usd = 0.0
    tokens_total_input = 0
    tokens_total_output = 0

    db = next(get_db())

    # ============================================
    # ORDENAMIENTO AUTOMÁTICO DE ARCHIVOS
    # ============================================
    print("\n" + "=" * 60)
    print("🔄 ORDENANDO ARCHIVOS POR PRIORIDAD")
    print("=" * 60)

    archivos_ordenados = []

    # FASE 1: Informes Técnicos (PRIMERO)
    archivos_informes = []
    for nombre in request.archivos:
        # Buscar en subdirectorio de informes
        ruta_informe = DATA_DIR / 'informes_tecnicos' / nombre
        if ruta_informe.exists():
            archivos_informes.append(nombre)

    if archivos_informes:
        print(f"📄 FASE 1 - Informes Técnicos: {len(archivos_informes)} archivo(s)")
        for archivo in archivos_informes:
            print(f"   • {archivo}")
    archivos_ordenados.extend(archivos_informes)

    # FASE 2: Peticiones Razonadas (SEGUNDO)
    archivos_peticiones = []
    for nombre in request.archivos:
        # Buscar en subdirectorio de peticiones
        ruta_peticion = DATA_DIR / 'peticiones_razonadas' / nombre
        if ruta_peticion.exists():
            archivos_peticiones.append(nombre)

    if archivos_peticiones:
        print(f"📋 FASE 2 - Peticiones Razonadas: {len(archivos_peticiones)} archivo(s)")
        for archivo in archivos_peticiones:
            print(f"   • {archivo}")
    archivos_ordenados.extend(archivos_peticiones)

    # FASE 3: Otros documentos (TERCERO)
    archivos_otros = [
        a for a in request.archivos
        if a not in archivos_informes and a not in archivos_peticiones
    ]

    if archivos_otros:
        print(f"📦 FASE 3 - Otros documentos: {len(archivos_otros)} archivo(s)")
        for archivo in archivos_otros:
            print(f"   • {archivo}")
    archivos_ordenados.extend(archivos_otros)

    print("=" * 60)
    print(f"✅ Orden de procesamiento establecido: {len(archivos_ordenados)} archivo(s) total")
    print("=" * 60 + "\n")

    # ============================================
    # PROCESAR EN ORDEN (con lista ordenada)
    # ============================================
    for nombre_archivo in archivos_ordenados:
        try:
            # BUSCAR ARCHIVO EN SUBDIRECTORIOS
            pdf_path = None
            tipo_doc = None
            subdirectorio = None

            # 1. Buscar en subdirectorios conocidos
            for subdir in TIPOS_DOCUMENTO.keys():
                subdir_path = DATA_DIR / subdir / nombre_archivo
                if subdir_path.exists():
                    pdf_path = subdir_path
                    tipo_doc = TIPOS_DOCUMENTO[subdir]['nombre']
                    subdirectorio = subdir
                    break

            # 2. Si no se encuentra, buscar en raíz (retrocompatibilidad)
            if not pdf_path:
                raiz_path = DATA_DIR / nombre_archivo
                if raiz_path.exists():
                    pdf_path = raiz_path
                    tipo_doc = "Sin clasificar"
                    subdirectorio = ""
                    print(f"\n⚠️ ADVERTENCIA: Archivo en raíz (debe moverse a subdirectorio): {nombre_archivo}")

            # 3. Si aún no se encuentra, error
            if not pdf_path or not pdf_path.exists():
                detalles.append({
                    "archivo": nombre_archivo,
                    "estado": "error",
                    "mensaje": f"Archivo no encontrado en ningún subdirectorio ni en raíz"
                })
                fallidos += 1
                continue

            # Verificar si ya fue procesado
            query = """
                SELECT d.id, d.numero, c.id as caso_id
                FROM documentos_pas d
                LEFT JOIN casos_pas c ON d.caso_id = c.id
                WHERE d.archivo_nombre = :nombre
                ORDER BY d.id DESC
                LIMIT 1
            """

            ya_procesado = db.execute(text(query), {"nombre": nombre_archivo}).fetchone()

            if ya_procesado and not request.forzar_reprocesar:
                detalles.append({
                    "archivo": nombre_archivo,
                    "estado": "duplicado",
                    "mensaje": f"Ya procesado como {ya_procesado[1]}. "
                               "Use forzar_reprocesar=true para crear nueva versión."
                })
                fallidos += 1
                continue

            # ========================================
            # PROCESAMIENTO
            # ========================================

            print(f"\n{'=' * 60}")
            print(f"🔄 Procesando: {nombre_archivo}")
            print(f"📂 Tipo: {tipo_doc}")
            print(f"📁 Subdirectorio: {subdirectorio or '(raíz)'}")
            print(f"🔑 Session ID: {request.session_id}")
            print(f"{'=' * 60}")

            # DETERMINAR QUÉ EXTRACTOR USAR
            if subdirectorio == 'informes_tecnicos':
                # EXTRACTOR DE INFORME TÉCNICO
                print("\n📄 Paso 1: Extracción de datos (Informe Técnico)...")

                # ⬇️ NUEVO: Pasar session_id al extractor
                # NOTA: Si extraer_informe_tecnico no acepta session_id,
                # necesitarás modificar el extractor para aceptarlo
                resultado, costo_info = await extraer_informe_tecnico(
                    str(pdf_path),
                    session_id=request.session_id  # ⬅️ NUEVO
                )

                # Acumular costos
                costo_total_usd += costo_info.get('costo_usd', 0.0)
                tokens_total_input += costo_info.get('input_tokens', 0)
                tokens_total_output += costo_info.get('output_tokens', 0)

                # Validar consistencia
                print("\n📊 Paso 2: Validación de consistencia...")
                validador = ValidadorInformeTecnico()
                reporte_validacion = validador.validar(resultado.model_dump())

                print(f"\n   {'✅' if reporte_validacion['es_valido'] else '⚠️'} "
                      f"Validación: {reporte_validacion['total_inconsistencias']} inconsistencias")

                # Guardar en BD
                print("\n💾 Paso 3: Guardando en base de datos...")

                # Preparar datos para BD
                resultado_dict = resultado.model_dump()
                resultado_dict["costo_extraccion"] = costo_info
                resultado_dict["archivo_nombre"] = nombre_archivo

                caso_id = guardar_informe_tecnico(db, resultado_dict)

                # Obtener documento_id para validación
                query_doc_id = text("""
                    SELECT id FROM documentos_pas
                    WHERE caso_id = :caso_id
                    AND archivo_nombre = :nombre
                    ORDER BY id DESC
                    LIMIT 1
                """)
                doc_result = db.execute(query_doc_id, {
                    "caso_id": caso_id,
                    "nombre": nombre_archivo
                }).fetchone()

                if not doc_result:
                    raise Exception("No se encontró documento recién creado")

                documento_id = doc_result[0]

                guardar_validacion(db, documento_id, reporte_validacion)

                db.commit()

                if ya_procesado:
                    reprocesados += 1

                detalles.append({
                    "archivo": nombre_archivo,
                    "tipo": tipo_doc,
                    "subdirectorio": subdirectorio,
                    "estado": "exitoso",
                    "mensaje": f"✅ Procesado correctamente. Caso ID: {caso_id}",
                    "caso_id": caso_id,
                    "documento_id": documento_id,
                    "validacion": {
                        "es_valido": reporte_validacion['es_valido'],
                        "inconsistencias": reporte_validacion['total_inconsistencias']
                    },
                    "costo_usd": costo_info.get('costo_usd', 0.0),
                    "tokens": costo_info.get('total_tokens', 0)
                })
                exitosos += 1

            elif subdirectorio == 'peticiones_razonadas':
                # EXTRACTOR DE PETICIÓN RAZONADA
                print("\n📄 Paso 1: Extracción de datos (Petición Razonada)...")

                # ⬇️ NUEVO: Pasar session_id al extractor
                # NOTA: Si extraer_peticion_razonada no acepta session_id,
                # necesitarás modificar el extractor para aceptarlo
                resultado, costo_info = await extraer_peticion_razonada(
                    str(pdf_path),
                    session_id=request.session_id  # ⬅️ NUEVO
                )

                # Acumular costos
                costo_total_usd += costo_info.get('costo_usd', 0.0)
                tokens_total_input += costo_info.get('input_tokens', 0)
                tokens_total_output += costo_info.get('output_tokens', 0)

                # Guardar en BD (vincula con informe existente)
                print("\n💾 Paso 2: Guardando en base de datos...")

                # Verificar tipo de resultado
                if hasattr(resultado, "model_dump"):
                    resultado_dict = resultado.model_dump()
                else:
                    resultado_dict = resultado

                resultado_dict['costo_extraccion'] = costo_info
                resultado_dict['archivo_nombre'] = nombre_archivo

                try:
                    caso_id, documento_id = guardar_peticion_razonada(db, resultado_dict)

                    db.commit()

                    if ya_procesado:
                        reprocesados += 1

                    detalles.append({
                        "archivo": nombre_archivo,
                        "tipo": tipo_doc,
                        "subdirectorio": subdirectorio,
                        "estado": "exitoso",
                        "mensaje": f"✅ Petición vinculada con caso ID: {caso_id}",
                        "caso_id": caso_id,
                        "documento_id": documento_id,
                        "informe_base": resultado_dict.get('informe_base', {}).get('numero'),
                        "prestador_ruc": resultado_dict.get('prestador_ruc') or "Copiado del informe",
                        "costo_usd": costo_info.get('costo_usd', 0.0),
                        "tokens": costo_info.get('total_tokens', 0)
                    })
                    exitosos += 1

                except ValueError as ve:
                    # Error específico: informe base no encontrado
                    print(f"\n⚠️ Error de vinculación: {str(ve)}")
                    detalles.append({
                        "archivo": nombre_archivo,
                        "tipo": tipo_doc,
                        "subdirectorio": subdirectorio,
                        "estado": "error",
                        "mensaje": f"❌ {str(ve)}"
                    })
                    fallidos += 1
                    db.rollback()

            else:
                # ARCHIVO SIN CLASIFICAR (en raíz)
                detalles.append({
                    "archivo": nombre_archivo,
                    "tipo": tipo_doc,
                    "subdirectorio": subdirectorio,
                    "estado": "error",
                    "mensaje": f"❌ Archivo sin clasificar. Mueva a: {', '.join(TIPOS_DOCUMENTO.keys())}"
                })
                fallidos += 1

            print(f"\n✅ Procesamiento completado: {nombre_archivo}")

        except Exception as e:
            print(f"\n❌ Error procesando {nombre_archivo}: {str(e)}")
            detalles.append({
                "archivo": nombre_archivo,
                "estado": "error",
                "mensaje": str(e)
            })
            fallidos += 1
            db.rollback()  # Rollback en caso de error

    db.close()

    return ProcesarResponse(
        exitosos=exitosos,
        fallidos=fallidos,
        reprocesados=reprocesados,
        detalles=detalles,
        costo_total_usd=round(costo_total_usd, 4),
        tokens_total_input=tokens_total_input,
        tokens_total_output=tokens_total_output,
        tokens_total=tokens_total_input + tokens_total_output
    )


@router.get("/estadisticas")
async def obtener_estadisticas():
    """
    Retorna estadísticas generales del sistema.

    Incluye:
    - Total de casos procesados
    - Casos por tipo de documento
    - Costos acumulados
    - Métricas de validación
    """
    db = next(get_db())

    try:
        # Total de casos
        result = db.execute(text("SELECT COUNT(*) FROM casos_pas")).fetchone()
        total_casos = result[0] if result else 0

        # Total de documentos
        result = db.execute(text("SELECT COUNT(*) FROM documentos_pas")).fetchone()
        total_documentos = result[0] if result else 0

        # Documentos por tipo
        result = db.execute(text("""
            SELECT tipo, COUNT(*) 
            FROM documentos_pas 
            GROUP BY tipo
        """)).fetchall()
        docs_por_tipo = {row[0]: row[1] for row in result} if result else {}

        db.close()

        return {
            "total_casos": total_casos,
            "total_documentos": total_documentos,
            "documentos_por_tipo": docs_por_tipo,
            "tipos_soportados": list(TIPOS_DOCUMENTO.keys()),
            "configuracion": {
                nombre: config['descripcion']
                for nombre, config in TIPOS_DOCUMENTO.items()
            }
        }

    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tipos-documento")
async def listar_tipos_documento():
    """
    Lista los tipos de documento soportados y su configuración.
    """
    return {
        "tipos": TIPOS_DOCUMENTO,
        "instrucciones": {
            "informes_tecnicos": f"Colocar archivos en: {DATA_DIR}/informes_tecnicos/",
            "peticiones_razonadas": f"Colocar archivos en: {DATA_DIR}/peticiones_razonadas/",
        }
    }


@router.get("/validacion/{documento_id}")
async def obtener_validacion_documento(documento_id: int):
    """
    Obtiene el reporte de validación completo de un documento.

    Args:
        documento_id: ID del documento en la tabla documentos_pas

    Returns:
        Reporte de validación con todas las inconsistencias detectadas

    Raises:
        HTTPException 404: Si el documento o su validación no existen
        HTTPException 500: Error al consultar base de datos
    """
    db = next(get_db())

    try:
        # Consultar validación con JOIN a documentos_pas
        query = """
            SELECT 
                v.documento_id,
                v.es_valido,
                v.total_inconsistencias,
                v.num_info,
                v.num_warnings,
                v.num_errors,
                v.num_critical,
                v.inconsistencias,
                v.validador_version,
                v.created_at,
                d.numero as numero_documento,
                d.archivo_nombre,
                d.tipo as tipo_documento
            FROM validaciones_informe v
            INNER JOIN documentos_pas d ON v.documento_id = d.id
            WHERE v.documento_id = :documento_id
            ORDER BY v.id DESC
            LIMIT 1
        """

        resultado = db.execute(text(query), {"documento_id": documento_id}).fetchone()

        if not resultado:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró validación para documento ID {documento_id}. "
                       f"Verifique que el documento existe y que se procesó con validación."
            )

        # Construir respuesta estructurada
        respuesta = {
            "documento_id": resultado[0],
            "es_valido": resultado[1],
            "total_inconsistencias": resultado[2],
            "num_info": resultado[3],
            "num_warnings": resultado[4],
            "num_errors": resultado[5],
            "num_critical": resultado[6],
            "inconsistencias": resultado[7] or [],  # JSONB puede ser None
            "validador_version": resultado[8],
            "created_at": str(resultado[9]),
            "numero_documento": resultado[10],
            "archivo_nombre": resultado[11],
            "tipo_documento": resultado[12],

            # Objeto validacion anidado para compatibilidad con frontend
            "validacion": {
                "es_valido": resultado[1],
                "total_inconsistencias": resultado[2],
                "contadores": {
                    "info": resultado[3],
                    "warnings": resultado[4],
                    "errors": resultado[5],
                    "critical": resultado[6]
                }
            }
        }

        db.close()
        return respuesta

    except HTTPException:
        db.close()
        raise
    except Exception as e:
        db.close()
        print(f"❌ Error en endpoint /validacion/{documento_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al consultar validación: {str(e)}"
        )
