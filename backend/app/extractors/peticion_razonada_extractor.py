"""
Extractor de Petición Razonada usando Claude API con Pseudonimización.

Versión: 4.2
Cambios respecto a 4.0:
  - Retry logic para error 529 (Overloaded) igual que informe_tecnico_extractor
  - Prompt actualizado con todos los formatos reales identificados:
      * CCDS-PR-YYYY-XXXX / CCDE-PR-YYYY-XXX (formato antiguo)
      * CTDG-YYYY-GE-XXXX (formato nuevo FO-DEAR-48)
  - Nuevos campos del formato FO-DEAR-48:
      * fecha_oficio_notificacion, fecha_tope_entrega
      * documento_entrega_garantia, fecha_entrega_garantia
  - 3 tipos de infracción: garantia_gfc_tardia, garantia_gfc_no_presentada,
    obligaciones_economicas
  - Firmantes como array (múltiples firmantes en formato FO-DEAR-48)
  - Log de auditoría (texto pseudonimizado guardado en /tmp)

Autor: Iván Suárez
Fecha: 2026-02-19
"""
import os
import json
import asyncio
import anthropic
import PyPDF2
from datetime import datetime, date
from typing import Tuple, Optional
from pathlib import Path

try:
    from backend.app.services.pseudonym_client import pseudonym_client
except ImportError:
    print("⚠️ pseudonym_client no disponible - ejecutando sin pseudonimización")
    pseudonym_client = None

try:
    from backend.app.schemas.peticion_razonada import (
        PeticionRazonadaSchema,
        InformeBaseSchema,
        FirmanteSchema,
        DocumentosAnexosSchema
    )
except ImportError:
    import sys

    sys.path.append(str(Path(__file__).parent.parent))
    from schemas.peticion_razonada import (
        PeticionRazonadaSchema,
        InformeBaseSchema,
        FirmanteSchema,
        DocumentosAnexosSchema
    )

# ========================================
# PROMPT DE EXTRACCIÓN
# ========================================

PROMPT_TEMPLATE = """Eres un experto en extracción de datos de documentos legales de ARCOTEL.

REGLA DE ORO: SOLO EXTRAES datos que aparezcan EXPLÍCITAMENTE en el documento.
NO calcules, NO inferas, NO asumas nada. Si un dato no está en el texto, usa null.

IMPORTANTE: Los datos personales están PSEUDONIMIZADOS (NOMBRE_XXXXXXXX, CEDULA_XXXXXXXX,
RUC_XXXXXXXX, EMAIL_XXXXXXXX, DIRECCION_XXXXXXXX, etc.).
Extrae estos pseudónimos TAL CUAL aparecen — serán revertidos automáticamente después.

Extrae todos los datos de la PETICIÓN RAZONADA de ARCOTEL.
Responde ÚNICAMENTE con JSON válido, sin texto adicional ni bloques de código.

=== CAMPO: numero ===
ARCOTEL usa TRES formatos de numeración. Extrae el número COMPLETO tal cual aparece:

  Formato 1 (CCDS con número largo): "CCDS-PR-2023-0156", "CCDS-PR-2022-0212"
  Formato 2 (CCDS/CCDE con número corto): "CCDS-PR-2022-272", "CCDE-PR-2022-269"
  Formato 3 (CTDG, 2025 en adelante): "CTDG-2025-GE-0335"

=== CAMPO: unidad_emisora ===
Primeras letras antes del primer guión:
  "CCDS-PR-2023-0156" → "CCDS"
  "CCDE-PR-2022-269"  → "CCDE"
  "CTDG-2025-GE-0335" → "CTDG"

=== CAMPO: fecha ===
Fecha al final del documento (firma). Formato: YYYY-MM-DD.

=== CAMPO: prestador_nombre ===
Nombre del presunto responsable. Puede aparecer como NOMBRE_XXXXXXXX si está pseudonimizado.
Extrae el pseudónimo tal cual.

=== CAMPO: prestador_ruc ===
RUC o cédula del prestador. Puede aparecer como RUC_XXXXXXXX o CEDULA_XXXXXXXX.
Si NO aparece en el documento, usa null. (Frecuente en formato antiguo.)

=== CAMPO: informe_base ===
Número del informe técnico base. ARCOTEL usa DOS formatos:
  Formato antiguo (hasta 2024): "CTDG-GE-2022-0461", "CTDG-GE-2023-0197"
  Formato nuevo (2025+):        "CTDG-2025-GE-0335"
Extrae el número COMPLETO tal cual aparece.
La fecha del informe base (si aparece) en formato YYYY-MM-DD.

=== CAMPO: tipo_infraccion ===
Determina el tipo basándote en el texto:
  "garantia_gfc_tardia"       — Presentó la GFC fuera de término / fuera del plazo
  "garantia_gfc_no_presentada"— NO presentó la GFC / no ha presentado
  "obligaciones_economicas"   — No pagó tarifas / incumplimiento de obligaciones económicas

=== CAMPO: descripcion_hecho ===
Descripción del hecho infractor tal como aparece en el documento.
Ejemplo: "Renovación de Garantía de Fiel Cumplimiento presentada fuera del plazo legal"
Si no está explícita, infiere un resumen breve del hecho basado en el texto.

=== CAMPO: documentos_anexos ===
Clasifica los documentos adjuntos en memorandos u oficios:
- memorandos: documentos que terminan en -M (ej: "ARCOTEL-CTHB-2022-2328-M")
- oficios: documentos que terminan en -E o -O o son de otros tipos

=== CAMPO: firmante ===
Datos del firmante principal (el último o más relevante). Objeto singular, no array.
El nombre puede estar pseudonimizado — extrae el pseudónimo tal cual.

=== JSON ESPERADO ===
{{
  "numero": "CCDS-PR-2023-0008",
  "unidad_emisora": "CCDS",
  "fecha": "2023-01-09",
  "prestador_nombre": "NOMBRE_XXXXXXXX o nombre real",
  "prestador_ruc": "RUC_XXXXXXXX o null",
  "informe_base": {{
    "numero": "CTDG-GE-2022-0487",
    "fecha": "2022-12-28"
  }},
  "tipo_infraccion": "garantia_gfc_tardia",
  "descripcion_hecho": "Renovación de GFC presentada fuera del plazo legal",
  "documentos_anexos": {{
    "memorandos": ["ARCOTEL-CTHB-2022-2328-M"],
    "oficios": ["CTDG-GE-2022-0487"]
  }},
  "firmante": {{
    "nombre": "NOMBRE_XXXXXXXX",
    "cargo": "Director Técnico de Control de Servicios de Telecomunicaciones",
    "unidad": null
  }},
  "articulo_coa_invocado": "Art 186",
  "solicitud": "inicio_procedimiento_sancionador"
}}

NOTAS FINALES:
- articulo_coa_invocado: Siempre "Art 186" (sin punto después de Art)
- solicitud: Siempre "inicio_procedimiento_sancionador"
- Fechas siempre en YYYY-MM-DD
- firmante: objeto singular (no array), el firmante principal del documento
- documentos_anexos: objeto con listas "memorandos" y "oficios", NO lista plana
- NO descifres los pseudónimos, extráelos tal cual

=== TEXTO DEL DOCUMENTO ===

{texto_pseudonimizado}

=== RESPUESTA (solo JSON) ==="""


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
                print(f"   - Página {i}: {len(texto_pagina)} caracteres")
            print(f"   - Total: {num_pages} páginas, {len(texto_completo)} caracteres\n")
            return texto_completo
    except Exception as e:
        raise Exception(f"Error extrayendo texto del PDF: {str(e)}")


async def extraer_con_claude(
        texto_pdf: str,
        session_id: Optional[str] = None
) -> Tuple[dict, dict]:
    """
    Extrae datos de Petición Razonada con pseudonimización obligatoria y retry logic.

    Flujo:
    1. Validar cliente pseudonimización
    2. Pseudonimizar texto (OBLIGATORIO)
    3. Log de auditoría
    4. Enviar a Claude API (con retry para 529)
    5. Des-pseudonimizar
    6. Retornar datos reales
    """
    print("\n" + "=" * 80)
    print("🤖 EXTRACCIÓN CON CLAUDE API - PETICIÓN RAZONADA v4.2")
    print("=" * 80)

    if session_id:
        print(f"🔑 Usando Session ID existente: {session_id}")

    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY no configurada")

    # ========== PASO 1: VALIDAR PSEUDONIMIZACIÓN ==========
    if not pseudonym_client:
        raise Exception(
            "❌ ABORTADO: Cliente de pseudonimización NO disponible.\n"
            "No se puede procesar sin pseudonimización (LOPDP Art. 10.e).\n"
            "Verifica que el servicio pseudonym-api esté running."
        )

    # ========== PASO 2: PSEUDONIMIZAR (OBLIGATORIO) ==========
    print(f"\n🔒 Pseudonimizando... ({len(texto_pdf):,} caracteres)")

    try:
        pseudonym_result = await pseudonym_client.pseudonymize_text(
            texto_pdf,
            session_id=session_id
        )
        texto_pseudonimizado = pseudonym_result["pseudonymized_text"]
        session_id_usado = pseudonym_result["session_id"]
        pseudonyms_count = pseudonym_result['pseudonyms_count']
        mapping = pseudonym_result.get('mapping', {})

        print(f"✅ Pseudonimización exitosa:")
        print(f"   🆔 Session ID: {session_id_usado}")
        print(f"   🔢 Pseudónimos: {pseudonyms_count}")
        if pseudonyms_count == 0:
            print("   ⚠️  ADVERTENCIA: No se detectaron datos personales")

    except Exception as e:
        raise Exception(
            f"❌ ABORTADO: Error en pseudonimización: {str(e)}\n"
            f"Verifica el servicio pseudonym-api y reintenta."
        )

    # ========== PASO 3: LOG DE AUDITORÍA ==========
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    try:
        temp_dir = "/tmp/claude_inputs"
        os.makedirs(temp_dir, exist_ok=True)
        temp_file = f"{temp_dir}/peticion_{session_id_usado}_{timestamp}.txt"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(f"Session ID: {session_id_usado}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Pseudónimos: {pseudonyms_count}\n")
            f.write("=" * 60 + "\nMAPEO:\n")
            for p, o in mapping.items():
                f.write(f"  {p} ← {o}\n")
            f.write("=" * 60 + "\nTEXTO PSEUDONIMIZADO:\n" + texto_pseudonimizado)
        print(f"💾 Auditoría guardada: {temp_file}")
    except Exception as e:
        print(f"⚠️  No se pudo guardar auditoría: {e}")

    # ========== PASO 4: CLAUDE API CON RETRY LOGIC ==========
    print("\n🚀 Enviando a Claude API...")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = PROMPT_TEMPLATE.format(texto_pseudonimizado=texto_pseudonimizado)

    max_retries = 5
    response = None
    last_error = None

    for intento in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            break  # Éxito

        except anthropic.APIStatusError as e:
            last_error = e
            if e.status_code == 529:
                wait_time = (2 ** intento) * 30  # 30s, 60s, 120s, 240s, 480s
                if intento < max_retries - 1:
                    print(f"⚠️  Claude sobrecargado (529). Reintentando en {wait_time}s... "
                          f"(intento {intento + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    raise Exception(
                        f"❌ Claude sobrecargado. Se intentó {max_retries} veces sin éxito.\n"
                        f"Intenta nuevamente en 2-5 minutos."
                    )
            else:
                raise Exception(f"❌ Error Claude API ({e.status_code}): {str(e)}")

    if response is None:
        raise last_error or Exception("❌ Error desconocido en Claude API")

    # Calcular costo
    usage = response.usage
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
    print(f"📊 Tokens: {usage.input_tokens:,} input + {usage.output_tokens:,} output")
    print(f"💰 Costo: ${costo_info['costo_usd']} USD")

    # Extraer y limpiar JSON
    json_text = response.content[0].text
    if json_text.strip().startswith('```'):
        lines = json_text.strip().split('\n')
        if lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        json_text = '\n'.join(lines)

    print("\n📥 RESPUESTA CLAUDE (con pseudónimos):")
    print(json_text[:500] + "..." if len(json_text) > 500 else json_text)

    datos = json.loads(json_text)

    # ========== PASO 5: DES-PSEUDONIMIZAR ==========
    print("\n🔓 Des-pseudonimizando...")
    try:
        datos_reales = await pseudonym_client.depseudonymize_data(
            datos,
            session_id=session_id_usado
        )
        print("✅ Des-pseudonimización exitosa")
        datos = datos_reales
    except Exception as e:
        raise Exception(
            f"❌ Error en des-pseudonimización: {str(e)}\n"
            f"Session ID usado: {session_id_usado}"
        )

    # ========== PASO 6: CONVERTIR FECHAS ==========
    for campo in ['fecha']:
        if datos.get(campo) and isinstance(datos[campo], str):
            try:
                datos[campo] = datetime.strptime(datos[campo], '%Y-%m-%d').date()
            except ValueError:
                pass

    if datos.get('informe_base') and datos['informe_base'].get('fecha'):
        if isinstance(datos['informe_base']['fecha'], str):
            try:
                datos['informe_base']['fecha'] = datetime.strptime(
                    datos['informe_base']['fecha'], '%Y-%m-%d'
                ).date()
            except ValueError:
                pass

    print("\n" + "=" * 80)
    print("✅ EXTRACCIÓN DE PETICIÓN RAZONADA COMPLETADA")
    print("=" * 80 + "\n")

    return datos, costo_info


def validar_datos(datos: dict) -> PeticionRazonadaSchema:
    """Valida datos extraídos con Pydantic."""
    print("✅ Validando con Pydantic...")
    try:
        validado = PeticionRazonadaSchema(**datos)
        print("   ✅ Validación exitosa")
        return validado
    except Exception as e:
        print(f"   ❌ Error de validación: {str(e)}")
        raise


async def extraer_peticion_razonada(
        pdf_path: str,
        session_id: Optional[str] = None
) -> Tuple[dict, dict]:
    """
    Función principal: extrae datos de Petición Razonada con pseudonimización.

    Args:
        pdf_path: Ruta al archivo PDF
        session_id: Session ID de validación previa (opcional)

    Returns:
        Tuple[dict, dict]: (datos_validados, info_costo)
    """
    print("\n" + "=" * 60)
    print("🚀 INICIANDO EXTRACCIÓN DE PETICIÓN RAZONADA v4.2")
    print("=" * 60)

    texto = extraer_texto_pdf(pdf_path)
    if not texto or len(texto.strip()) < 50:
        raise Exception("PDF vacío o sin texto extraíble")

    datos_raw, costo_info = await extraer_con_claude(texto, session_id=session_id)
    datos_validados = validar_datos(datos_raw)

    print(f"📄 Petición: {datos_validados.numero}")
    print(f"📅 Fecha: {datos_validados.fecha}")
    print(f"👤 Prestador: {datos_validados.prestador_nombre}")
    print(f"📋 Informe base: {datos_validados.informe_base.numero}")
    print(f"⚖️  Tipo: {datos_validados.tipo_incumplimiento}")
    print(f"💰 Costo: ${costo_info['costo_usd']} USD")

    return datos_validados.model_dump(), costo_info


# ========================================
# CLI / TESTING
# ========================================

async def test_extractor(pdf_path: str, session_id: Optional[str] = None):
    """Test del extractor desde CLI."""
    try:
        datos, costo = await extraer_peticion_razonada(pdf_path, session_id)
        print("\n📊 RESULTADO:")
        print(json.dumps(datos, indent=2, ensure_ascii=False, default=str))
        print("\n✅ Test completado")
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python peticion_razonada_extractor.py /ruta/archivo.pdf [session_id]")
        sys.exit(1)
    pdf_path = sys.argv[1]
    session = sys.argv[2] if len(sys.argv) > 2 else None
    if not os.path.exists(pdf_path):
        print(f"❌ Archivo no encontrado: {pdf_path}")
        sys.exit(1)
    asyncio.run(test_extractor(pdf_path, session))
