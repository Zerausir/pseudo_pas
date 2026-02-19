# ============================================================
#  ARCOTEL PAS — VALIDACIÓN VISUAL PSEUDONIMIZACIÓN v2.1.5
#  Solo peticiones razonadas — preview sin DB ni procesamiento
# ============================================================

$BASE_URL = "http://localhost:8000"
$DATA_DIR = ".\data\peticiones_razonadas"

# ============================================================
# FUNCIÓN: Preview pseudonimización
# ============================================================
function Get-Preview {
    param([string]$Archivo)
    $body = @{
        archivo        = $Archivo
        tipo_documento = "peticion_razonada"
    } | ConvertTo-Json
    return Invoke-RestMethod "$BASE_URL/api/validacion/previsualizar" `
        -Method POST -ContentType "application/json" -Body $body -TimeoutSec 60
}

# ============================================================
# INICIO
# ============================================================
Clear-Host
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  VALIDACIÓN VISUAL — PETICIONES RAZONADAS (v2.1.5)   " -ForegroundColor Cyan
Write-Host "  Solo preview — sin DB, sin procesamiento             " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$peticiones = Get-ChildItem "$DATA_DIR\*.pdf" | Sort-Object Name

if ($peticiones.Count -eq 0) {
    Write-Host "❌ No se encontraron PDFs en $DATA_DIR" -ForegroundColor Red
    exit 1
}

Write-Host "`n📂 $($peticiones.Count) peticiones detectadas`n" -ForegroundColor Yellow

$ok = 0
$incompleta = 0
$casos_mal = [System.Collections.Generic.List[hashtable]]::new()

foreach ($pdf in $peticiones) {
    $idx = $peticiones.IndexOf($pdf) + 1

    Write-Host "========================================================" -ForegroundColor Magenta
    Write-Host "  $idx / $($peticiones.Count)  |  ✅ $ok  ❌ $incompleta" -ForegroundColor Gray
    Write-Host "  📄 $($pdf.Name)" -ForegroundColor White
    Write-Host "========================================================" -ForegroundColor Magenta

    # Preview
    Write-Host "`n🔍 Generando preview..." -NoNewline -ForegroundColor Yellow
    try {
        $preview = Get-Preview -Archivo $pdf.Name
    } catch {
        Write-Host " ❌ Error: $($_.Exception.Message)" -ForegroundColor Red
        $incompleta++
        continue
    }

    $tiposStr = ($preview.pseudonyms_by_type.GetEnumerator() |
        ForEach-Object { "$($_.Key):$($_.Value)" }) -join ", "
    Write-Host " $($preview.pseudonyms_count) pseudónimos ($tiposStr)" -ForegroundColor Yellow

    # Obtener texto del HTML antes de abrir el navegador
    $html_url = "$BASE_URL/outputs/$($preview.html_filename)"
    $texto_pseudonimizado = ""
    try {
        $html_content = Invoke-WebRequest $html_url -UseBasicParsing
        if ($html_content.Content -match '(?s)<pre>(.*?)</pre>') {
            $texto_pseudonimizado = [System.Net.WebUtility]::HtmlDecode($Matches[1].Trim())
        }
    } catch {
        $texto_pseudonimizado = "[No se pudo obtener el texto: $($_.Exception.Message)]"
    }

    # Abrir navegador
    Start-Process $html_url
    Write-Host "🌐 $html_url" -ForegroundColor DarkGray

    Write-Host ""
    Write-Host "  Verifica en el navegador:" -ForegroundColor Yellow
    Write-Host "  · Persona natural  → nombre como NOMBRE_XXXXXXXX" -ForegroundColor White
    Write-Host "  · Persona jurídica → representante como NOMBRE_XXXXXXXX" -ForegroundColor White

    # Confirmación
    do {
        $r = (Read-Host "`n  ¿Pseudonimización completa? (OK / MAL)").Trim().ToUpper()
    } while ($r -notin @("OK", "MAL"))

    if ($r -eq "OK") {
        Write-Host "  ✅ Correcto`n" -ForegroundColor Green
        $ok++
    } else {
        $detalle = Read-Host "  ¿Qué dato NO fue pseudonimizado?"
        Write-Host "  ❌ Registrado: '$detalle'`n" -ForegroundColor Red
        $casos_mal.Add(@{
            archivo              = $pdf.Name
            detalle              = $detalle
            pseudonimos_count    = $preview.pseudonyms_count
            pseudonimos_tipos    = $tiposStr
            html_url             = $html_url
            texto_pseudonimizado = $texto_pseudonimizado
        })
        $incompleta++
    }
}

# ============================================================
# RESUMEN FINAL
# ============================================================
Write-Host "`n========================================================"  -ForegroundColor Cyan
Write-Host "  RESUMEN FINAL"                                              -ForegroundColor Cyan
Write-Host "  ✅ Correctas   : $ok"                                       -ForegroundColor Green
Write-Host "  ❌ Incompletas : $incompleta"                               -ForegroundColor Red
Write-Host "========================================================"    -ForegroundColor Cyan

if ($casos_mal.Count -gt 0) {
    Write-Host "`n❌ DETALLE DE CASOS INCOMPLETOS:" -ForegroundColor Red

    foreach ($caso in $casos_mal) {
        Write-Host "`n  ──────────────────────────────────────────────────" -ForegroundColor DarkRed
        Write-Host "  📄 Archivo    : $($caso.archivo)"                    -ForegroundColor White
        Write-Host "  🔢 Pseudónimos: $($caso.pseudonimos_count) ($($caso.pseudonimos_tipos))" -ForegroundColor Yellow
        Write-Host "  ⚠️  Problema   : $($caso.detalle)"                   -ForegroundColor Red
        Write-Host "  🌐 HTML        : $($caso.html_url)"                  -ForegroundColor DarkGray
        Write-Host "`n  📝 TEXTO PSEUDONIMIZADO COMPLETO:"                 -ForegroundColor Yellow
        Write-Host "  ──────────────────────────────────────────────────"  -ForegroundColor DarkGray
        $caso.texto_pseudonimizado -split "`n" | ForEach-Object {
            Write-Host "  $_" -ForegroundColor Gray
        }
        Write-Host "  ──────────────────────────────────────────────────" -ForegroundColor DarkGray
    }

    # Guardar también en .txt para análisis posterior
    $report_path = ".\reporte_pseudonimizacion_mal_$((Get-Date -Format 'yyyyMMdd_HHmmss')).txt"
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine("REPORTE PSEUDONIMIZACIÓN INCOMPLETA — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
    [void]$sb.AppendLine("Fix aplicado: v2.1.5 (buscar_y_reemplazar_variaciones en Capa 2 spaCy)")
    [void]$sb.AppendLine("=" * 60)

    foreach ($caso in $casos_mal) {
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("ARCHIVO     : $($caso.archivo)")
        [void]$sb.AppendLine("PSEUDONIMOS : $($caso.pseudonimos_count) ($($caso.pseudonimos_tipos))")
        [void]$sb.AppendLine("PROBLEMA    : $($caso.detalle)")
        [void]$sb.AppendLine("HTML        : $($caso.html_url)")
        [void]$sb.AppendLine("")
        [void]$sb.AppendLine("TEXTO PSEUDONIMIZADO:")
        [void]$sb.AppendLine("-" * 60)
        [void]$sb.AppendLine($caso.texto_pseudonimizado)
        [void]$sb.AppendLine("-" * 60)
    }

    $sb.ToString() | Out-File $report_path -Encoding utf8
    Write-Host "`n📁 Reporte guardado en: $report_path" -ForegroundColor Yellow
}

Read-Host "`nPresiona ENTER para salir"
