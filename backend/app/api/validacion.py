"""
API Endpoints para validación visual de pseudonimización.
OBLIGATORIO antes de procesar documentos.

Versión: 1.1 - IMPORTS CORREGIDOS
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime
import uuid

# ✅ IMPORTS CORREGIDOS
from backend.app.database import get_db  # ⬅️ CAMBIADO: era "from app.database"
from backend.app.services.pseudonym_client import pseudonym_client
from backend.app.extractors.informe_tecnico_extractor import extraer_texto_pdf

router = APIRouter(prefix="/api/validacion", tags=["validacion"])

# Configuración
DATA_DIR = Path("/app/data")
OUTPUTS_DIR = Path("/app/outputs")  # ⬅️ CAMBIADO: directorio dentro del contenedor
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


# ========================================
# SCHEMAS
# ========================================

class PreviewRequest(BaseModel):
    archivo: str
    tipo_documento: str  # 'informe_tecnico' o 'peticion_razonada'


class PreviewResponse(BaseModel):
    session_id: str
    html_filename: str
    pseudonyms_count: int
    pseudonyms_by_type: dict
    mensaje: str


# ========================================
# FUNCIONES AUXILIARES
# ========================================

def generar_html_validacion(
        texto_pseudonimizado: str,
        mapping: dict,
        session_id: str,
        archivo: str,
        stats: dict
) -> str:
    """
    Genera HTML interactivo con texto pseudonimizado resaltado.

    Args:
        texto_pseudonimizado: Texto con pseudónimos
        mapping: Diccionario {pseudonimo: valor_real}
        session_id: ID de sesión
        archivo: Nombre del archivo
        stats: Estadísticas de pseudonimización

    Returns:
        str: HTML completo
    """

    # Crear mapa inverso para resaltar en el HTML
    texto_html = texto_pseudonimizado

    # Diccionario de colores por tipo
    colores = {
        'CEDULA': '#FFD700',  # Dorado
        'RUC': '#FFD700',  # Dorado
        'EMAIL': '#87CEEB',  # Azul cielo
        'TELEFONO': '#90EE90',  # Verde claro
        'NOMBRE': '#FFB6C1',  # Rosa claro
        'DIRECCION': '#FFA07A'  # Salmón
    }

    # Resaltar cada pseudónimo
    for pseudonimo, original in mapping.items():
        # Determinar tipo
        tipo = pseudonimo.split('_')[0]
        color = colores.get(tipo, '#FFFF99')  # Amarillo por defecto

        # Reemplazar con span coloreado
        texto_html = texto_html.replace(
            pseudonimo,
            f'<span class="pseudonym" data-type="{tipo}" data-code="{pseudonimo}" '
            f'style="background-color: {color}; padding: 2px 4px; border-radius: 3px; '
            f'font-weight: bold; cursor: help;" title="{tipo}: {pseudonimo}">{pseudonimo}</span>'
        )

    # Generar HTML completo
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Validación de Pseudonimización - {archivo}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2em;
            margin-bottom: 10px;
        }}

        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .warning {{
            background: #fff3cd;
            border-left: 5px solid #ffc107;
            padding: 20px;
            margin: 20px;
            border-radius: 8px;
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.8; }}
        }}

        .warning h2 {{
            color: #856404;
            margin-bottom: 10px;
            font-size: 1.3em;
        }}

        .warning ul {{
            list-style: none;
            padding-left: 0;
        }}

        .warning li {{
            padding: 5px 0;
            color: #856404;
        }}

        .warning li:before {{
            content: "⚠️ ";
            margin-right: 8px;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            padding: 20px;
            background: #f8f9fa;
        }}

        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .stat-card h3 {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }}

        .stat-card p {{
            font-size: 1.8em;
            font-weight: bold;
            color: #667eea;
        }}

        .document {{
            padding: 20px;
            background: white;
            max-height: 600px;
            overflow-y: auto;
            border-top: 2px solid #e9ecef;
        }}

        .document pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.6;
            color: #333;
        }}

        .pseudonym:hover {{
            transform: scale(1.05);
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}

        .legend {{
            padding: 20px;
            background: #f8f9fa;
            border-top: 2px solid #e9ecef;
        }}

        .legend h3 {{
            margin-bottom: 15px;
            color: #333;
        }}

        .legend-items {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .legend-color {{
            width: 30px;
            height: 20px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}

        .checklist {{
            padding: 20px;
            background: #e3f2fd;
            border-top: 2px solid #2196f3;
        }}

        .checklist h3 {{
            margin-bottom: 15px;
            color: #1976d2;
        }}

        .checklist ul {{
            list-style: none;
        }}

        .checklist li {{
            padding: 8px 0;
            color: #1565c0;
        }}

        .checklist li:before {{
            content: "☐ ";
            margin-right: 8px;
            font-size: 1.2em;
        }}

        .footer {{
            padding: 20px;
            background: #333;
            color: white;
            text-align: center;
        }}

        .footer p {{
            margin: 5px 0;
            font-size: 0.9em;
        }}

        .command {{
            background: #2d2d2d;
            color: #f8f8f2;
            padding: 15px;
            margin: 20px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            overflow-x: auto;
        }}

        .command pre {{
            margin: 0;
            white-space: pre-wrap;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔒 VALIDACIÓN DE PSEUDONIMIZACIÓN</h1>
            <p>Revise CUIDADOSAMENTE que TODOS los datos personales están pseudonimizados</p>
        </div>

        <div class="warning">
            <h2>⚠️ ADVERTENCIA CRÍTICA - CUMPLIMIENTO LOPDP</h2>
            <ul>
                <li>Debe revisar MANUALMENTE todo el texto antes de confirmar</li>
                <li>Verifique que NO aparecen nombres, cédulas, RUCs, emails o direcciones REALES</li>
                <li>Solo se enviarán datos a Claude API si confirma que TODO está pseudonimizado</li>
                <li>Esta validación es OBLIGATORIA según LOPDP Ecuador Arts. 8, 10.e, 33, 37</li>
            </ul>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>Archivo</h3>
                <p style="font-size: 1.2em;">{archivo}</p>
            </div>
            <div class="stat-card">
                <h3>Session ID</h3>
                <p style="font-size: 0.9em;">{session_id}</p>
            </div>
            <div class="stat-card">
                <h3>Total Pseudónimos</h3>
                <p>{stats.get('total', 0)}</p>
            </div>
            <div class="stat-card">
                <h3>Timestamp</h3>
                <p style="font-size: 1em;">{datetime.now().strftime('%H:%M:%S')}</p>
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>📇 Cédulas/RUCs</h3>
                <p>{stats.get('CEDULA', 0) + stats.get('RUC', 0)}</p>
            </div>
            <div class="stat-card">
                <h3>👤 Nombres</h3>
                <p>{stats.get('NOMBRE', 0)}</p>
            </div>
            <div class="stat-card">
                <h3>📧 Emails</h3>
                <p>{stats.get('EMAIL', 0)}</p>
            </div>
            <div class="stat-card">
                <h3>📞 Teléfonos</h3>
                <p>{stats.get('TELEFONO', 0)}</p>
            </div>
            <div class="stat-card">
                <h3>📍 Direcciones</h3>
                <p>{stats.get('DIRECCION', 0)}</p>
            </div>
        </div>

        <div class="legend">
            <h3>🎨 Leyenda de Colores</h3>
            <div class="legend-items">
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #FFD700;"></div>
                    <span>Cédulas/RUCs</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #FFB6C1;"></div>
                    <span>Nombres</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #87CEEB;"></div>
                    <span>Emails</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #90EE90;"></div>
                    <span>Teléfonos</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background-color: #FFA07A;"></div>
                    <span>Direcciones</span>
                </div>
            </div>
        </div>

        <div class="document">
            <h3 style="margin-bottom: 15px;">📄 DOCUMENTO PSEUDONIMIZADO</h3>
            <pre>{texto_html}</pre>
        </div>

        <div class="checklist">
            <h3>✅ CHECKLIST DE VALIDACIÓN</h3>
            <p style="margin-bottom: 15px;">Antes de confirmar, verifica:</p>
            <ul>
                <li>Todos los nombres de personas están como <strong>NOMBRE_XXXXXXXX</strong></li>
                <li>Todas las cédulas están como <strong>CEDULA_XXXXXXXX</strong></li>
                <li>Todos los RUCs están como <strong>RUC_XXXXXXXX</strong></li>
                <li>Todos los emails están como <strong>EMAIL_XXXXXXXX</strong></li>
                <li>Todos los teléfonos están como <strong>TELEFONO_XXXXXXXX</strong></li>
                <li>Todas las direcciones están como <strong>DIRECCION_XXXXXXXX</strong></li>
                <li>NO aparece ningún dato personal en texto plano</li>
            </ul>
        </div>

        <div class="command">
            <h3 style="color: #50fa7b; margin-bottom: 10px;">📋 PASO SIGUIENTE: Procesar con Confirmación</h3>
            <pre>$proceso = @{{
    archivos = @("{archivo}")
    session_id = "{session_id}"
    confirmado = $true
}} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/archivos/procesar" `
    -Method POST -ContentType "application/json" -Body $proceso</pre>
        </div>

        <div class="footer">
            <p><strong>CUMPLIMIENTO LOPDP Ecuador</strong></p>
            <p>Arts. 8 (Consentimiento Informado), 10.e (Finalidad), 33 (Transferencia Internacional), 37 (Seguridad)</p>
            <p>Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
</body>
</html>"""

    return html


# ========================================
# ENDPOINTS
# ========================================

@router.post("/previsualizar", response_model=PreviewResponse)
async def previsualizar_pseudonimizacion(request: PreviewRequest):
    """
    Genera HTML con texto pseudonimizado para validación visual del usuario.

    FLUJO:
    1. Extrae texto del PDF
    2. Pseudonimiza con servicio de pseudonimización
    3. Genera HTML interactivo con pseudónimos resaltados
    4. Retorna session_id para usar en procesamiento

    El usuario DEBE:
    - Descargar el HTML
    - Revisar que TODO está pseudonimizado
    - Solo si confirma, llamar a /api/archivos/procesar con session_id
    """

    print(f"\n{'=' * 60}")
    print(f"🔍 PREVISUALIZACIÓN DE PSEUDONIMIZACIÓN")
    print(f"{'=' * 60}")
    print(f"📄 Archivo: {request.archivo}")
    print(f"📂 Tipo: {request.tipo_documento}")

    # 1. Buscar archivo
    subdirs = {
        'informe_tecnico': 'informes_tecnicos',
        'peticion_razonada': 'peticiones_razonadas'
    }

    subdir = subdirs.get(request.tipo_documento)
    if not subdir:
        raise HTTPException(400, f"Tipo de documento no soportado: {request.tipo_documento}")

    pdf_path = DATA_DIR / subdir / request.archivo

    if not pdf_path.exists():
        # Buscar en raíz como fallback
        pdf_path = DATA_DIR / request.archivo
        if not pdf_path.exists():
            raise HTTPException(404, f"Archivo no encontrado: {request.archivo}")

    print(f"✅ Archivo encontrado: {pdf_path}")

    # 2. Extraer texto
    print(f"\n📄 Extrayendo texto del PDF...")
    try:
        texto = extraer_texto_pdf(str(pdf_path))
        print(f"✅ Texto extraído: {len(texto):,} caracteres")
    except Exception as e:
        raise HTTPException(500, f"Error extrayendo texto: {str(e)}")

    # 3. Pseudonimizar
    print(f"\n🔒 Pseudonimizando datos personales...")
    try:
        result = await pseudonym_client.pseudonymize_text(texto)

        session_id = result['session_id']
        texto_pseudonimizado = result['pseudonymized_text']
        mapping = result.get('mapping', {})
        pseudonyms_count = result['pseudonyms_count']

        print(f"✅ Pseudonimización exitosa")
        print(f"   🆔 Session ID: {session_id}")
        print(f"   🔢 Pseudónimos: {pseudonyms_count}")

    except Exception as e:
        raise HTTPException(500, f"Error en pseudonimización: {str(e)}")

    # 4. Calcular estadísticas por tipo
    stats = {'total': pseudonyms_count}
    for pseudonimo in mapping.keys():
        tipo = pseudonimo.split('_')[0]
        stats[tipo] = stats.get(tipo, 0) + 1

    print(f"\n📊 Estadísticas:")
    for tipo, count in stats.items():
        if tipo != 'total':
            print(f"   {tipo}: {count}")

    # 5. Generar HTML
    print(f"\n🌐 Generando HTML de validación...")
    html = generar_html_validacion(
        texto_pseudonimizado,
        mapping,
        session_id,
        request.archivo,
        stats
    )

    # 6. Guardar HTML
    html_filename = f"validacion_{session_id}.html"
    html_path = OUTPUTS_DIR / html_filename

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✅ HTML guardado: {html_path}")
    print(f"\n{'=' * 60}")
    print(f"✅ PREVISUALIZACIÓN COMPLETADA")
    print(f"{'=' * 60}\n")

    return PreviewResponse(
        session_id=session_id,
        html_filename=html_filename,
        pseudonyms_count=pseudonyms_count,
        pseudonyms_by_type={k: v for k, v in stats.items() if k != 'total'},
        mensaje=f"HTML generado. Descargue desde: /outputs/{html_filename}"
    )
