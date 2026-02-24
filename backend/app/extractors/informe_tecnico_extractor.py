"""
Extractor de Informe Técnico usando Claude API con Pseudonimización.

MODIFICADO para incluir pseudonimización de datos personales antes de enviar a Claude API.
Cumple con LOPDP Ecuador Arts. 10.e, 33, 37.

Versión: 4.2 - Campos derivados calculados (dias_retraso, fecha_vencimiento_gfc)

Autor: Iván Suárez
Fecha: 2026-02-13
"""
import os
import json
import asyncio
import anthropic
import PyPDF2
from datetime import datetime, date, timedelta
from typing import Tuple, Dict, Optional
from pathlib import Path
from pydantic import BaseModel, Field, validator, ValidationError

# Importar cliente de pseudonimización
try:
    from backend.app.services.pseudonym_client import pseudonym_client
except ImportError:
    print("⚠️ pseudonym_client no disponible - ejecutando sin pseudonimización")
    pseudonym_client = None


# ========================================
# SCHEMAS PYDANTIC
# ========================================

class PrestadorSchema(BaseModel):
    nombre: str = Field(..., description="Razón social del prestador")
    nombre_comercial: Optional[str] = Field(None, description="Nombre comercial")
    ruc: str = Field(..., description="RUC del prestador (10 o 13 dígitos)")
    representante_legal: Optional[str] = Field(None, description="Representante legal")
    emails: list[str] = Field(default_factory=list, description="Lista de emails")

    @validator('ruc')
    def validar_ruc(cls, v):
        if v and not v.isdigit():
            raise ValueError('RUC debe contener solo dígitos')
        if v and len(v) not in [10, 13]:
            raise ValueError('RUC debe tener 10 o 13 dígitos')
        return v


class InfraccionSchema(BaseModel):
    tipo: str
    hecho: str
    fecha_vencimiento_gfc: Optional[date] = None
    fecha_maxima_entrega_gfc: Optional[date] = None
    fecha_real_entrega: Optional[date] = None
    dias_retraso_extraido: Optional[int] = None
    articulos_violados: list[str] = Field(default_factory=list)

    @validator('dias_retraso_extraido')
    def validar_dias_retraso(cls, v):
        if v is not None and not isinstance(v, int):
            raise ValueError('dias_retraso_extraido debe ser entero')
        return v


class InformeTecnicoSchema(BaseModel):
    numero: str
    fecha: date
    servicio_controlado: Optional[str] = None
    prestador: PrestadorSchema
    infraccion: InfraccionSchema

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


# ========================================
# FUNCIONES DE EXTRACCIÓN
# ========================================

def extraer_texto_pdf(pdf_path: str) -> str:
    """Extrae texto de un PDF."""
    print(f"\n📄 Extrayendo texto de: {pdf_path}")

    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)

            texto_completo = ""
            for i, page in enumerate(pdf_reader.pages, 1):
                texto_pagina = page.extract_text()
                texto_completo += texto_pagina
                print(f"   - Página {i}: {len(texto_pagina)} caracteres extraídos")

            print(f"   - Total: {num_pages} páginas, {len(texto_completo)} caracteres\n")
            return texto_completo

    except Exception as e:
        raise Exception(f"Error extrayendo texto del PDF: {str(e)}")


async def extraer_con_claude(
        texto_pdf: str,
        session_id: Optional[str] = None
) -> Tuple[dict, dict]:
    """
    Usa Claude API para extraer datos estructurados con PSEUDONIMIZACIÓN OBLIGATORIA.

    FLUJO:
    1. Pseudonimizar texto (OBLIGATORIO - aborta si falla)
    2. Verificar que se pseudonimizaron datos
    3. Mostrar y guardar texto pseudonimizado para auditoría
    4. Enviar texto pseudonimizado a Claude API (CON RETRY LOGIC)
    5. Recibir datos extraídos (con pseudónimos)
    6. Calcular campos derivados (dias_retraso, fecha_vencimiento_gfc) si no vienen de Claude
    7. Des-pseudonimizar datos (valores reales)
    8. Retornar datos reales

    Args:
        texto_pdf: Texto extraído del PDF
        session_id: Session ID de validación previa (opcional)
                   Si se proporciona, reutiliza esa sesión de pseudonimización
                   garantizando que los datos coincidan con lo que el usuario validó

    Returns:
        Tuple[dict, dict]: (datos_extraidos, info_costo)

    Raises:
        Exception: Si pseudonimización falla o no está disponible

    Versión: 4.5
    Cambios respecto a 4.4:
      - Eliminado "obligaciones_economicas" del enum tipo (ese tipo de informe está fuera
        del alcance del TFE; si llega uno, Claude devuelve null y el sistema lo rechaza)
      - Agregada lógica de validación por fechas: si existen fecha_maxima_entrega_gfc
        y fecha_real_entrega en el documento, Claude las usa para CONFIRMAR o CORREGIR
        el tipo inferido del texto. Las fechas son datos objetivos y tienen prioridad
        sobre redacción ambigua. Esto resuelve el caso CTDGGE20230096 (solo tabla, sin
        texto explícito en conclusiones).
    """
    print("\n" + "=" * 80)
    print("🤖 INICIANDO EXTRACCIÓN CON CLAUDE API (CON PSEUDONIMIZACIÓN OBLIGATORIA)")
    print("=" * 80)

    if session_id:
        print(f"🔑 Usando Session ID existente: {session_id}")
        print("   (de validación previa - datos ya verificados por usuario)")

    # Obtener API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no configurada")

    # ========== PASO 1: VALIDAR CLIENTE DE PSEUDONIMIZACIÓN ==========
    if not pseudonym_client:
        raise Exception(
            "❌ ABORTADO: Cliente de pseudonimización NO disponible.\n"
            "No se puede procesar documentos sin pseudonimización (LOPDP Art. 10.e).\n"
            "Verifica que el servicio pseudonym-api esté running."
        )

    # ========== PASO 2: PSEUDONIMIZAR TEXTO (OBLIGATORIO) ==========
    print("\n🔒 Pseudonimizando datos personales...")
    print(f"📄 Longitud texto original: {len(texto_pdf):,} caracteres")

    try:
        pseudonym_result = await pseudonym_client.pseudonymize_text(
            texto_pdf,
            session_id=session_id
        )

        texto_pseudonimizado = pseudonym_result["pseudonymized_text"]
        session_id_usado = pseudonym_result["session_id"]
        pseudonyms_count = pseudonym_result['pseudonyms_count']
        mapping = pseudonym_result.get('mapping', {})

        print(f"\n✅ Pseudonimización EXITOSA:")
        print(f"   🆔 Session ID: {session_id_usado}")

        if session_id and session_id == session_id_usado:
            print(f"   ♻️  Sesión reutilizada (de validación previa)")
        else:
            print(f"   🆕 Sesión nueva generada")

        print(f"   🔢 Pseudónimos creados: {pseudonyms_count}")

        # Mostrar mapeo de pseudónimos (para auditoría)
        if mapping:
            print(f"\n📋 Pseudónimos creados (primeros 10):")
            for i, (pseudonym, original) in enumerate(list(mapping.items())[:10], 1):
                original_preview = original[:30] + "..." if len(original) > 30 else original
                print(f"   {i}. {original_preview} → {pseudonym}")
            if len(mapping) > 10:
                print(f"   ... y {len(mapping) - 10} más")

        # VALIDACIÓN CRÍTICA: Verificar que se crearon pseudónimos
        if pseudonyms_count == 0:
            print("\n⚠️  ADVERTENCIA: No se detectaron datos personales para pseudonimizar")
            print("⚠️  Esto puede indicar un problema con los patrones de detección")
            print("⚠️  Continuando de todos modos (el documento puede no tener datos personales)")

    except Exception as e:
        raise Exception(
            f"❌ ABORTADO: Error en pseudonimización: {str(e)}\n"
            f"No se puede enviar datos a Claude sin pseudonimización (LOPDP Art. 10.e).\n"
            f"Verifica el servicio pseudonym-api y reintenta."
        )

    # ========== PASO 3: AUDITORÍA - GUARDAR Y MOSTRAR TEXTO PSEUDONIMIZADO ==========
    print("\n" + "=" * 80)
    print("📤 TEXTO PSEUDONIMIZADO QUE SE ENVIARÁ A CLAUDE API")
    print("=" * 80)
    print("🔍 Primeros 2000 caracteres:")
    print("-" * 80)
    print(texto_pseudonimizado[:2000])
    print("-" * 80)
    print(f"📊 Longitud total: {len(texto_pseudonimizado):,} caracteres")
    print("=" * 80 + "\n")

    # Guardar texto completo en archivo temporal para auditoría
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        temp_dir = "/tmp/claude_inputs"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = f"{temp_dir}/input_{session_id_usado}_{timestamp}.txt"

        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("TEXTO PSEUDONIMIZADO ENVIADO A CLAUDE API\n")
            f.write("=" * 80 + "\n")
            f.write(f"Session ID: {session_id_usado}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Pseudónimos creados: {pseudonyms_count}\n")
            f.write(f"Longitud: {len(texto_pseudonimizado):,} caracteres\n")
            f.write("=" * 80 + "\n\n")
            f.write("MAPEO DE PSEUDÓNIMOS:\n")
            f.write("-" * 80 + "\n")
            for pseudonym, original in mapping.items():
                f.write(f"{pseudonym} ← {original}\n")
            f.write("\n" + "=" * 80 + "\n\n")
            f.write("TEXTO PSEUDONIMIZADO:\n")
            f.write("=" * 80 + "\n\n")
            f.write(texto_pseudonimizado)

        print(f"💾 Texto pseudonimizado guardado en: {temp_file}")
        print(f"   Comando para ver: docker exec arcotel_backend cat {temp_file}\n")

    except Exception as e:
        print(f"⚠️ No se pudo guardar archivo temporal: {e}\n")

    # ========== PASO 4: ENVIAR A CLAUDE API (CON RETRY LOGIC) ==========
    print("🚀 Enviando texto pseudonimizado a Claude API...")

    client = anthropic.Anthropic(api_key=api_key)

    # ============================================================
    # PROMPT v4.5 — ANÁLISIS DE 22 INFORMES TÉCNICOS REALES (ARCOTEL 2022-2025):
    #
    # Distribución de tipos en scope del TFE:
    #   - garantia_gfc_tardia:        13 docs
    #   - garantia_gfc_no_presentada:  8 docs
    #   - (obligaciones_economicas):   1 doc → fuera de scope, Claude devuelve null
    #
    # Patrones reales en CONCLUSIONES:
    #   - "ha presentado... sin dar cumplimiento" (SIN "NO"):  10 docs → tardia
    #   - "NO ha presentado... sin dar cumplimiento":           3 docs → no_presentada
    #   - "no ha presentado" (standalone):                     3 docs → no_presentada
    #   - "fuera de término":                                  2 docs → tardia
    #   - tabla fechas solo (sin texto explícito):             1 doc  → tardia (por fechas)
    #
    # Lógica PASO 1 + PASO 2:
    #   PASO 1: texto de conclusiones → tipo candidato
    #   PASO 2: fechas (si existen) → confirman o corrigen el candidato
    #   Las fechas son datos objetivos; tienen prioridad sobre redacción ambigua.
    # ============================================================
    prompt = f"""Eres un experto en extracción de datos de documentos legales de ARCOTEL.

REGLA DE ORO: SOLO EXTRAES datos que aparezcan EXPLÍCITAMENTE en el documento.
NO calcules, NO inferas, NO asumas nada. Si un dato no está, usa null.

Extrae TODOS los datos del Informe Técnico de ARCOTEL.
Responde ÚNICAMENTE con JSON válido, sin texto adicional.

IMPORTANTE: Los datos personales están PSEUDONIMIZADOS (CEDULA_XXXXXXXX, EMAIL_XXXXXXXX, NOMBRE_XXXXXXXX, etc.).
Extrae estos pseudónimos TAL CUAL aparecen - serán revertidos automáticamente después.

FORMATO JSON ESPERADO:
{{
    "numero": "string",
    "fecha": "YYYY-MM-DD",
    "servicio_controlado": "string o null",
    "prestador": {{
        "nombre": "string (puede ser NOMBRE_XXXXXXXX si está pseudonimizado)",
        "nombre_comercial": "string o null",
        "ruc": "string (puede ser CEDULA_XXXXXXXX o RUC_XXXXXXXX si está pseudonimizado)",
        "representante_legal": "string o null (puede ser NOMBRE_XXXXXXXX). Si dice N/A usa null.",
        "emails": ["EMAIL_XXXXXXXX o email real"]
    }},
    "infraccion": {{
        "tipo": "<VALOR DEL ENUM — ver regla TIPO más abajo>",
        "hecho": "string",
        "fecha_vencimiento_gfc": "YYYY-MM-DD o null",
        "fecha_maxima_entrega_gfc": "YYYY-MM-DD o null",
        "fecha_real_entrega": "YYYY-MM-DD o null",
        "dias_retraso_extraido": numero o null,
        "articulos_violados": ["LOT Art X", "ROTH Art Y", ...]
    }}
}}

=== REGLA: CAMPO tipo ===
DEBES usar EXACTAMENTE uno de estos DOS valores (sin variaciones de texto):
  "garantia_gfc_tardia"        — El prestador SÍ presentó la GFC pero FUERA del plazo
  "garantia_gfc_no_presentada" — El prestador NO presentó la GFC

Si el documento trata sobre tarifas, pagos u obligaciones económicas (distinto de GFC),
usa null — ese tipo de informe está fuera del alcance del sistema.

PASO 1 — Lee la CONCLUSIÓN (sección 4 o 5 según el documento) y determina un tipo candidato:

→ Candidato "garantia_gfc_tardia" si encuentras ALGUNO de estos:
   • "presentó... fuera de término" o "entregó... fuera de término"
   • "ha presentado... sin dar cumplimiento" (ATENCIÓN: sin la palabra NO antes de "ha presentado")

→ Candidato "garantia_gfc_no_presentada" si encuentras ALGUNO de estos:
   • "no ha presentado" / "NO ha presentado" / "no presentó"
   • "NO ha presentado... sin dar cumplimiento" (con NO explícito antes de "ha presentado")

⚠️ ARTEFACTO OCR FRECUENTE: El PDF puede unir palabras por error de OCR.
   Ejemplo: "RADIOELECTRICONO ha presentado" → es "RADIOELECTRICO" + "NO ha presentado"
   → candidato: "garantia_gfc_no_presentada"

PASO 2 — Si el documento contiene fecha_maxima_entrega_gfc Y fecha_real_entrega,
úsalas para CONFIRMAR o CORREGIR el candidato del Paso 1:

   • fecha_real_entrega EXISTE y es POSTERIOR a fecha_maxima_entrega_gfc
     → confirma o corrige a "garantia_gfc_tardia"
     (el prestador sí entregó pero tarde)

   • fecha_real_entrega es NULL o NO aparece en el documento
     → confirma o corrige a "garantia_gfc_no_presentada"
     (no hay evidencia de entrega)

   Las fechas son datos objetivos. Si contradicen el texto, PRIORIZA las fechas.
   Si no existen fechas en el documento, usa solo el resultado del Paso 1.

NUNCA uses el texto libre del asunto o título del documento para este campo.

=== REGLA: CAMPO articulos_violados ===
Extrae TODOS los artículos mencionados en el documento. Busca en ESTAS secciones:
  1. Sección "3.1 NORMA VERIFICADA" o "2.1 NORMA CONTROLADA" — artículos transcritos
  2. Sección "3.2 ANÁLISIS" o "2.2 ANÁLISIS" — artículos mencionados en el texto analítico
  3. Sección "4. CONCLUSIONES" o "5. CONCLUSIONES" — artículos citados al final

Formato de cada artículo: "PREFIJO Art NÚM"
Ejemplos: "LOT Art 24", "ROTH Art 204", "ROTH Art 206", "ROTH Art 207", "ROTH Art 210"
Incluye Disposiciones Generales si aparecen: "ROTH Disposición General Quinta"
NO incluyas artículos del Estatuto Orgánico ni de resoluciones internas.
El array NO debe tener duplicados.

REGLAS GENERALES:
1. Fechas SIEMPRE en formato YYYY-MM-DD
2. RUC: Extraer tal cual (puede ser pseudónimo CEDULA_XXXXXXXX)
3. emails: ARRAY aunque sea 1 solo. Array vacío [] si no hay.
4. dias_retraso_extraido: SOLO si aparece textualmente como número en el doc
5. NO intentes "descifrar" los pseudónimos — extráelos tal cual

=== TEXTO DEL INFORME ===

{texto_pseudonimizado}

=== RESPONDE SOLO CON EL JSON ==="""

    # ========== RETRY LOGIC PARA ERROR 529 OVERLOADED ==========
    max_retries = 3
    last_error = None
    response = None

    for intento in range(max_retries):
        try:
            if intento > 0:
                print(f"🔄 Reintento {intento + 1}/{max_retries}...")

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2500,
                messages=[{"role": "user", "content": prompt}]
            )

            # ✅ Éxito, salir del loop
            print("✅ Claude API respondió exitosamente")
            break

        except anthropic.APIError as e:
            last_error = e
            error_str = str(e).lower()

            # Verificar si es error 529 overloaded
            if "overloaded" in error_str or "529" in error_str:
                if intento < max_retries - 1:
                    wait_time = (2 ** intento) * 5  # 5s, 10s, 20s
                    print(f"⚠️ Claude API sobrecargada (error 529).")
                    print(f"   Reintentando en {wait_time}s... (intento {intento + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise Exception(
                        f"❌ Error en Claude API: Claude está temporalmente sobrecargado.\n"
                        f"Se intentó {max_retries} veces sin éxito.\n"
                        f"Por favor intenta nuevamente en 2-5 minutos."
                    )
            else:
                # Otro tipo de error, lanzar inmediatamente
                raise Exception(f"❌ Error en Claude API: {str(e)}")

    # Si salimos del loop sin éxito, lanzar el último error
    if response is None:
        if last_error:
            raise last_error
        else:
            raise Exception("❌ Error desconocido en Claude API")

    # ========== FIN RETRY LOGIC ==========

    # Capturar tokens y calcular costo
    usage = response.usage
    print(f"\n📊 Tokens: {usage.input_tokens:,} input + {usage.output_tokens:,} output")

    costo_info = {
        "costo_usd": round(
            (usage.input_tokens * 3.00 / 1_000_000) +
            (usage.output_tokens * 15.00 / 1_000_000),
            4
        ),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
        "model": "claude-sonnet-4-20250514",
        "pricing_date": "2025-01-29"
    }
    print(f"💰 Costo: ${costo_info['costo_usd']} USD")

    # Extraer JSON
    json_text = response.content[0].text

    # Limpiar markdown
    if json_text.strip().startswith('```'):
        json_text = json_text.strip()
        lines = json_text.split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        json_text = '\n'.join(lines)

    print("\n" + "=" * 80)
    print("📥 RESPUESTA CLAUDE (CON PSEUDÓNIMOS):")
    print("=" * 80)
    print(json_text[:500] + "..." if len(json_text) > 500 else json_text)
    print("=" * 80 + "\n")

    # Parsear JSON
    datos = json.loads(json_text)

    # ========== PASO 4.5: CALCULAR CAMPOS DERIVADOS ==========
    # dias_retraso y fecha_vencimiento_gfc son campos CALCULADOS, no extraídos.
    # Se derivan de fecha_maxima_entrega_gfc según ROTH Art. 204.
    print("📐 Calculando campos derivados (si no vienen de Claude)...")

    infraccion = datos.get('infraccion', {})

    fecha_max_str = infraccion.get('fecha_maxima_entrega_gfc')
    fecha_real_str = infraccion.get('fecha_real_entrega')

    fecha_max_dt = None
    fecha_real_dt = None

    if fecha_max_str:
        try:
            fecha_max_dt = datetime.strptime(fecha_max_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    if fecha_real_str:
        try:
            fecha_real_dt = datetime.strptime(fecha_real_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            pass

    # Calcular dias_retraso si no vino de Claude
    if fecha_max_dt and fecha_real_dt and not infraccion.get('dias_retraso_extraido'):
        dias = (fecha_real_dt - fecha_max_dt).days
        if dias > 0:
            infraccion['dias_retraso_extraido'] = dias
            print(f"   ✅ dias_retraso_extraido calculado: {dias} días")
        else:
            print(f"   ℹ️  días calculado ≤ 0 ({dias}), no se asigna")

    # Calcular fecha_vencimiento_gfc si no vino de Claude (= fecha_max + 15 días, ROTH Art. 204)
    if fecha_max_dt and not infraccion.get('fecha_vencimiento_gfc'):
        infraccion['fecha_vencimiento_gfc'] = (fecha_max_dt + timedelta(days=15)).isoformat()
        print(f"   ✅ fecha_vencimiento_gfc calculada: {infraccion['fecha_vencimiento_gfc']} (ROTH Art. 204)")

    datos['infraccion'] = infraccion
    print("✅ Campos derivados procesados\n")

    # ========== PASO 5: DES-PSEUDONIMIZAR DATOS ==========
    print("🔓 Des-pseudonimizando datos...")

    try:
        datos_reales = await pseudonym_client.depseudonymize_data(
            datos,
            session_id=session_id_usado
        )
        print("✅ Des-pseudonimización exitosa\n")
        datos = datos_reales

    except Exception as e:
        raise Exception(
            f"❌ Error en des-pseudonimización: {str(e)}\n"
            f"Los datos están pseudonimizados y no se pueden recuperar.\n"
            f"Session ID: {session_id_usado}"
        )

    # ========== PASO 6: CONVERTIR FECHAS ==========
    if 'fecha' in datos and isinstance(datos['fecha'], str):
        datos['fecha'] = datetime.strptime(datos['fecha'], '%Y-%m-%d').date()

    if 'infraccion' in datos:
        for campo_fecha in ['fecha_vencimiento_gfc', 'fecha_maxima_entrega_gfc', 'fecha_real_entrega']:
            if campo_fecha in datos['infraccion'] and datos['infraccion'][campo_fecha]:
                if isinstance(datos['infraccion'][campo_fecha], str):
                    datos['infraccion'][campo_fecha] = datetime.strptime(
                        datos['infraccion'][campo_fecha], '%Y-%m-%d'
                    ).date()

    print("=" * 80)
    print("✅ EXTRACCIÓN COMPLETADA CON ÉXITO")
    print("=" * 80 + "\n")

    return datos, costo_info


def validar_datos(datos: dict) -> InformeTecnicoSchema:
    """Valida datos extraídos con Pydantic."""
    print("✅ Validando tipos y formatos...")

    try:
        resultado = InformeTecnicoSchema(**datos)
        print(f"✅ Validación exitosa: {resultado.numero}\n")
        return resultado
    except ValidationError as e:
        print("❌ Error de validación:")
        print(e.json(indent=2))
        raise


# ========================================
# FUNCIÓN PRINCIPAL
# ========================================

async def extraer_informe_tecnico(
        pdf_path: str,
        session_id: Optional[str] = None
) -> Tuple[InformeTecnicoSchema, dict]:
    """
    Función principal para extraer datos de Informe Técnico con PSEUDONIMIZACIÓN.

    Args:
        pdf_path: Ruta al archivo PDF
        session_id: Session ID de validación previa (opcional)
                   Si se proporciona, reutiliza esa sesión de pseudonimización
                   garantizando que los datos coincidan con lo que el usuario validó

    Returns:
        Tuple[InformeTecnicoSchema, dict]: (datos_validados, info_costo)
    """
    # 1. Extraer texto del PDF
    texto = extraer_texto_pdf(pdf_path)

    # Mostrar preview
    print("=" * 60)
    print(f"TEXTO EXTRAÍDO ({len(texto)} caracteres):")
    print("=" * 60)
    print(texto[:2000])
    print("\n...\n")

    # 2. Extraer con Claude (con pseudonimización)
    datos, costo_info = await extraer_con_claude(
        texto,
        session_id=session_id
    )

    # 3. Validar datos
    resultado = validar_datos(datos)

    return resultado, costo_info


# ========================================
# TEST/DEMO
# ========================================

async def test_extractor(pdf_path: str, session_id: Optional[str] = None):
    """Función de test"""
    print("\n" + "=" * 60)
    print("TEST EXTRACTOR CON PSEUDONIMIZACIÓN v4.2")
    print("=" * 60 + "\n")

    try:
        resultado, costo_info = await extraer_informe_tecnico(pdf_path, session_id)

        print("=" * 60)
        print("DATOS EXTRAÍDOS (des-pseudonimizados):")
        print("=" * 60)
        print(json.dumps(resultado.model_dump(), indent=2, ensure_ascii=False, default=str))

        print("\n" + "=" * 60)
        print("COSTOS:")
        print("=" * 60)
        print(json.dumps(costo_info, indent=2))

        print("\n✅ Test completado exitosamente")
        print("✅ Cumplimiento LOPDP: 100%")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        # Opcional: Pasar session_id como segundo argumento
        session = sys.argv[2] if len(sys.argv) > 2 else None
        asyncio.run(test_extractor(sys.argv[1], session))
    else:
        print("Uso: python informe_tecnico_extractor.py <ruta_pdf> [session_id]")
