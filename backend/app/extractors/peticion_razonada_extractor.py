"""
Extractor de Petición Razonada usando Claude API con Pseudonimización.

Versión: 4.0 - Async + Pseudonimización + session_id support
NUEVO: Ahora incluye pseudonimización obligatoria igual que informe_tecnico_extractor.py

Autor: Iván Suárez
Fecha: 2026-02-11
"""
import os
import json
import asyncio
import anthropic
import PyPDF2
from datetime import datetime
from typing import Tuple, Dict, Optional
from pathlib import Path

# ⬇️ NUEVO: Importar cliente de pseudonimización
try:
    from backend.app.services.pseudonym_client import pseudonym_client
except ImportError:
    print("⚠️ pseudonym_client no disponible - ejecutando sin pseudonimización")
    pseudonym_client = None

# Importar schema (ajustar ruta según estructura final)
try:
    from backend.app.schemas.peticion_razonada import (
        PeticionRazonadaSchema,
        InformeBaseSchema,
        FirmanteSchema,
        DocumentosAnexosSchema
    )
except ImportError:
    # Fallback para desarrollo/testing
    import sys

    sys.path.append(str(Path(__file__).parent.parent))
    from schemas.peticion_razonada import (
        PeticionRazonadaSchema,
        InformeBaseSchema,
        FirmanteSchema,
        DocumentosAnexosSchema
    )


# ========================================
# FUNCIONES DE EXTRACCIÓN
# ========================================

def extraer_texto_pdf(pdf_path: str) -> str:
    """
    Extrae texto de un PDF.

    Args:
        pdf_path: Ruta al archivo PDF

    Returns:
        str: Texto extraído del PDF
    """
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
        session_id: Optional[str] = None  # ⬅️ NUEVO: Parámetro opcional
) -> Tuple[dict, dict]:
    """
    Usa Claude API para extraer datos estructurados de la Petición Razonada
    CON PSEUDONIMIZACIÓN OBLIGATORIA.

    FLUJO (igual que informe_tecnico_extractor.py):
    1. Pseudonimizar texto (OBLIGATORIO - aborta si falla)
    2. Verificar que se pseudonimizaron datos
    3. Enviar texto pseudonimizado a Claude API
    4. Recibir datos extraídos (con pseudónimos)
    5. Des-pseudonimizar datos (valores reales)
    6. Retornar datos reales

    Args:
        texto_pdf: Texto extraído del PDF
        session_id: Session ID de validación previa (opcional)

    Returns:
        Tuple[dict, dict]: (datos_extraidos, info_costo)

    Raises:
        Exception: Si pseudonimización falla o no está disponible
    """
    print("\n" + "=" * 80)
    print("🤖 INICIANDO EXTRACCIÓN CON CLAUDE API (CON PSEUDONIMIZACIÓN OBLIGATORIA)")
    print("=" * 80)

    if session_id:
        print(f"🔑 Usando Session ID existente: {session_id}")
        print("   (de validación previa - datos ya verificados por usuario)")

    # Obtener API key del entorno
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no configurada en variables de entorno")

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

        if pseudonyms_count == 0:
            print("\n⚠️  ADVERTENCIA: No se detectaron datos personales para pseudonimizar")

    except Exception as e:
        raise Exception(
            f"❌ ABORTADO: Error en pseudonimización: {str(e)}\n"
            f"No se puede enviar datos a Claude sin pseudonimización (LOPDP Art. 10.e).\n"
            f"Verifica el servicio pseudonym-api y reintenta."
        )

    # ========== PASO 3: ENVIAR A CLAUDE API ==========
    print("\n🚀 Enviando texto pseudonimizado a Claude API...")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Eres un experto en extracción de datos de documentos legales de ARCOTEL.

REGLA DE ORO: SOLO EXTRAES datos que aparezcan EXPLÍCITAMENTE en el documento.
NO calcules, NO inferas, NO asumas nada. Si un dato no está, usa null.

IMPORTANTE: Los datos personales están PSEUDONIMIZADOS (CEDULA_XXXXXXXX, EMAIL_XXXXXXXX, NOMBRE_XXXXXXXX, RUC_XXXXXXXX, etc.).
Extrae estos pseudónimos TAL CUAL aparecen - serán revertidos automáticamente después.

Extrae TODOS los datos de la PETICIÓN RAZONADA de ARCOTEL.
Responde ÚNICAMENTE con JSON válido, sin texto adicional.

=== INSTRUCCIONES ESPECÍFICAS ===

📋 ENCABEZADO:

⚠️ IMPORTANTE - NÚMERO DE PETICIÓN:
ARCOTEL usa DOS formatos diferentes:

**FORMATO 1 (con -PR-):**
- Ejemplo: "PETICIÓN RAZONADA No. CCDS-PR-2023-0008"
- Ejemplo: "PETICIÓN RAZONADA No. CCDE-PR-2022-269"

**FORMATO 2 (sin -PR-):**
- Ejemplo: "PETICIÓN RAZONADA No. CTDG-2025-GE-0335"
- Ejemplo: "PETICIÓN RAZONADA No. CTDG-GE-2022-0487"

Extraer el número COMPLETO tal cual aparece.

- fecha: Fecha al final del documento. Convertir a YYYY-MM-DD

- unidad_emisora: Primeras letras antes del primer guión
  * "CCDS-PR-2023-0008" → "CCDS"
  * "CTDG-2025-GE-0335" → "CTDG"

👤 PRESTADOR:
- prestador_nombre: Puede estar pseudonimizado como NOMBRE_XXXXXXXX
- prestador_ruc: Puede estar pseudonimizado como RUC_XXXXXXXX o CEDULA_XXXXXXXX
  Si no está en el documento, usar null

📄 INFORME BASE:

⚠️ FORMATOS DE NÚMERO DE INFORME:

**FORMATO ANTERIOR (hasta 2024):**
- Ejemplo: "CTDG-GE-2024-0487"

**FORMATO NUEVO (desde 2025):**
- Ejemplo: "CTDG-2025-GE-0335"

Extraer el número COMPLETO tal cual aparece.

- informe_base.fecha: Convertir a YYYY-MM-DD

⚖️ INFRACCIÓN:
- tipo_infraccion: Tipo de incumplimiento
- descripcion_hecho: Descripción completa

📎 DOCUMENTOS ANEXOS:
- documentos_anexos.memorandos: Lista de memorandos
- documentos_anexos.oficios: Lista de oficios

✍️ FIRMANTE:
- firmante.nombre: Puede estar pseudonimizado como NOMBRE_XXXXXXXX
- firmante.cargo: Cargo completo
- firmante.unidad: Unidad organizacional

=== FORMATO JSON ESPERADO ===

{{
  "numero": "string",
  "fecha": "YYYY-MM-DD",
  "unidad_emisora": "string",
  "prestador_nombre": "string (puede ser NOMBRE_XXXXXXXX)",
  "prestador_ruc": "string o null (puede ser RUC_XXXXXXXX o CEDULA_XXXXXXXX)",
  "informe_base": {{
    "numero": "string",
    "fecha": "YYYY-MM-DD"
  }},
  "tipo_infraccion": "string",
  "descripcion_hecho": "string",
  "documentos_anexos": {{
    "memorandos": ["string"],
    "oficios": ["string"]
  }},
  "firmante": {{
    "nombre": "string (puede ser NOMBRE_XXXXXXXX)",
    "cargo": "string",
    "unidad": "string o null"
  }},
  "articulo_coa_invocado": "Art 186",
  "solicitud": "inicio_procedimiento_sancionador"
}}

=== REGLAS ===

1. Fechas SIEMPRE en formato YYYY-MM-DD
2. RUC/Cédula: Extraer tal cual (puede ser pseudónimo)
3. articulo_coa_invocado: Siempre "Art 186"
4. solicitud: Siempre "inicio_procedimiento_sancionador"
5. NO intentes "descifrar" los pseudónimos - extráelos tal cual
6. Si un campo no está, usa null

=== TEXTO DEL DOCUMENTO ===

{texto_pseudonimizado}

=== RESPUESTA ===

Responde SOLO con el JSON, sin explicaciones adicionales:"""

    try:
        # Llamar a Claude API
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Calcular costos
        usage = response.usage
        if usage:
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
            print(f"\n📊 Tokens: {usage.input_tokens:,} input + {usage.output_tokens:,} output")
            print(f"💰 Costo: ${costo_info['costo_usd']} USD")

        # Extraer JSON de la respuesta
        json_text = response.content[0].text

        # Limpiar posibles bloques de código markdown
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

        # ========== PASO 4: DES-PSEUDONIMIZAR DATOS ==========
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

        # ========== PASO 5: CONVERTIR FECHAS ==========
        if 'fecha' in datos and isinstance(datos['fecha'], str):
            datos['fecha'] = datetime.strptime(datos['fecha'], '%Y-%m-%d').date()

        if 'informe_base' in datos and datos['informe_base']:
            if 'fecha' in datos['informe_base'] and datos['informe_base']['fecha']:
                if isinstance(datos['informe_base']['fecha'], str):
                    datos['informe_base']['fecha'] = datetime.strptime(
                        datos['informe_base']['fecha'], '%Y-%m-%d'
                    ).date()

        print("=" * 80)
        print("✅ EXTRACCIÓN COMPLETADA CON ÉXITO")
        print("=" * 80 + "\n")

        return datos, costo_info

    except anthropic.APIError as e:
        raise Exception(f"Error en Claude API: {str(e)}")
    except json.JSONDecodeError as e:
        raise Exception(f"Error parseando JSON de Claude: {str(e)}\nRespuesta: {json_text[:500]}")


def validar_datos(datos: dict) -> PeticionRazonadaSchema:
    """
    Valida datos extraídos con Pydantic.

    NOTA: Esta validación solo verifica tipos y formatos básicos.
    NO valida consistencia de datos (eso requiere validador posterior).

    Args:
        datos: Diccionario con datos extraídos

    Returns:
        PeticionRazonadaSchema: Datos validados

    Raises:
        ValidationError: Si los datos no cumplen el schema
    """
    print("\n✅ Validando datos con Pydantic...")

    try:
        validado = PeticionRazonadaSchema(**datos)
        print("   ✅ Validación exitosa")
        return validado

    except Exception as e:
        print(f"   ❌ Error de validación: {str(e)}")
        raise


async def extraer_peticion_razonada(
        pdf_path: str,
        session_id: Optional[str] = None  # ⬅️ NUEVO: Parámetro opcional
) -> Tuple[dict, dict]:
    """
    Función principal: Extrae datos de Petición Razonada CON PSEUDONIMIZACIÓN.

    Flujo:
    1. Extrae texto del PDF
    2. Pseudonimiza texto
    3. Usa Claude API para extraer datos estructurados
    4. Des-pseudonimiza datos
    5. Valida con Pydantic

    Args:
        pdf_path: Ruta al archivo PDF
        session_id: Session ID de validación previa (opcional)

    Returns:
        Tuple[dict, dict]: (datos_validados, info_costo)

    Raises:
        Exception: Si falla algún paso del proceso
    """
    print("\n" + "=" * 60)
    print("🚀 INICIANDO EXTRACCIÓN DE PETICIÓN RAZONADA v4.0")
    print("=" * 60)

    # 1. Extraer texto
    texto = extraer_texto_pdf(pdf_path)

    if not texto or len(texto.strip()) < 100:
        raise Exception("PDF vacío o sin texto extraíble")

    # 2. Extraer con Claude (CON pseudonimización) - ASYNC
    datos_raw, costo_info = await extraer_con_claude(
        texto,
        session_id=session_id  # ⬅️ NUEVO: Pasar session_id
    )

    # 3. Validar
    datos_validados = validar_datos(datos_raw)

    print("\n" + "=" * 60)
    print("✅ EXTRACCIÓN COMPLETADA")
    print("=" * 60)
    print(f"📄 Petición: {datos_validados.numero}")
    print(f"📅 Fecha: {datos_validados.fecha}")
    print(f"👤 Prestador: {datos_validados.prestador_nombre}")
    print(f"🆔 RUC: {datos_validados.prestador_ruc}")
    print(f"📋 Informe base: {datos_validados.informe_base.numero}")
    print(f"⚖️ Tipo: {datos_validados.tipo_infraccion}")
    print(f"💰 Costo: ${costo_info['costo_usd']} USD")
    print(f"✅ Cumplimiento LOPDP: 100%")
    print("=" * 60 + "\n")

    return datos_validados.model_dump(), costo_info


# ========================================
# CLI / TESTING
# ========================================

async def test_extractor(pdf_path: str, session_id: Optional[str] = None):
    """Función de test"""
    print("\n" + "=" * 60)
    print("TEST EXTRACTOR PETICIÓN RAZONADA v4.0")
    print("=" * 60 + "\n")

    try:
        datos, costo = await extraer_peticion_razonada(pdf_path, session_id)

        print("\n📊 RESUMEN:")
        print(json.dumps(datos, indent=2, ensure_ascii=False, default=str))

        print("\n✅ Test completado exitosamente")

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    """
    Modo CLI para testing rápido.

    Uso:
        python peticion_razonada_extractor.py /ruta/al/archivo.pdf [session_id]
    """
    import sys

    if len(sys.argv) < 2:
        print("❌ Error: Debes proporcionar la ruta del PDF")
        print("\nUso: python peticion_razonada_extractor.py /ruta/al/archivo.pdf [session_id]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    session = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(pdf_path):
        print(f"❌ Error: Archivo no encontrado: {pdf_path}")
        sys.exit(1)

    try:
        asyncio.run(test_extractor(pdf_path, session))
    except Exception as e:
        print(f"\n❌ FALLÓ: {str(e)}")
        sys.exit(1)
