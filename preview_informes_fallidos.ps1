# ============================================================
#  ARCOTEL PAS — ANÁLISIS PSEUDONIMIZACIÓN INFORMES FALLIDOS
#  6 informes rechazados manualmente en sesión anterior
#  Solo preview — sin DB, sin procesamiento
# ============================================================

$BASE_URL = "http://localhost:8000"
$DATA_DIR = ".\data\informes_tecnicos"

# Lista fija — los 6 que fallaron
$INFORMES_FALLIDOS = @(
    "CTDG-GE-2022-0169.pdf",
    "CTDG-GE-2022-0337.pdf",
    "CTDG-GE-2022-0382.pdf",
    "CTDG-GE-2022-0392.pdf",
    "CTDG-GE-2022-0485.pdf",
    "CTDG-GE-2023-0255.pdf"
)

# ============================================================
# FUNCIÓN: Preview pseudonimización
# ============================================================
function Get-Preview {
    param([string]$Archivo)
    $body = @{
        archivo        = $Archivo
        tipo_documento = "informe_tecnico"
    } | ConvertTo-Json
    return Invoke-RestMethod "$BASE_URL/api/validacion/previsualizar" `
        -Method POST -ContentType "application/json" -Body $body -TimeoutSec 60
}

# ============================================================
# INICIO
# ============================================================
Clear-Host
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ANÁLISIS PSEUDONIMIZACIÓN — 6 INFORMES FALLIDOS      " -ForegroundColor Cyan
Write-Host "  Objetivo: identificar qué dato no fue pseudonimizado  " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# Verificar que los archivos existen
Write-Host "`n📂 Verificando archivos..." -ForegroundColor Yellow
$informes = @()
foreach ($nombre in $INFORMES_FALLIDOS) {
    $ruta = Join-Path $DATA_DIR $nombre
    if (Test-Path $ruta) {
        $informes += Get-Item $ruta
        Write-Host "   ✅ $nombre" -ForegroundColor Green
    } else {
        Write-Host "   ❌ No encontrado: $nombre" -ForegroundColor Red
    }
}

if ($informes.Count -eq 0) {
    Write-Host "`n❌ Ningún archivo encontrado en $DATA_DIR" -ForegroundColor Red
    exit 1
}

Write-Host "`n▶ Procesando $($informes.Count) informes`n" -ForegroundColor Yellow

$ok = 0
$incompleta = 0
$casos_mal = [System.Collections.Generic.List[hashtable]]::new()

foreach ($pdf in $informes) {
    $idx = $informes.IndexOf($pdf) + 1

    Write-Host "========================================================" -ForegroundColor Magenta
    Write-Host "  $idx / $($informes.Count)  |  ✅ $ok  ❌ $incompleta" -ForegroundColor Gray
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

    # Estadísticas (compatible con PSCustomObject)
    $pseudonimos_count = $preview.pseudonyms_count
    $tiposStr = ""
    try {
        $tiposStr = ($preview.pseudonyms_by_type.PSObject.Properties |
            ForEach-Object { "$($_.Name):$($_.Value)" }) -join ", "
    } catch {}
    Write-Host " $pseudonimos_count pseudónimos ($tiposStr)" -ForegroundColor Yellow

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
    Write-Host "  Verifica en el navegador qué dato real quedó expuesto." -ForegroundColor Yellow
    Write-Host "  Busca nombres, cédulas, emails o direcciones sin pseudonimizar." -ForegroundColor White

    # Confirmación
    do {
        $r = (Read-Host "`n  ¿Pseudonimización completa? (OK / MAL)").Trim().ToUpper()
    } while ($r -notin @("OK", "MAL"))

    if ($r -eq "OK") {
        Write-Host "  ✅ Correcto — era falsa alarma en la sesión anterior`n" -ForegroundColor Green
        $ok++
    } else {
        $detalle = Read-Host "  ¿Qué dato NO fue pseudonimizado?"
        Write-Host "  ❌ Registrado: '$detalle'`n" -ForegroundColor Red
        $casos_mal.Add(@{
            archivo              = $pdf.Name
            detalle              = $detalle
            pseudonimos_count    = $pseudonimos_count
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
Write-Host "  ✅ Correctos    : $ok"                                      -ForegroundColor Green
Write-Host "  ❌ Incompletos  : $incompleta"                              -ForegroundColor Red
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

    # Guardar reporte en .txt
    $report_path = ".\reporte_informes_fallidos_$((Get-Date -Format 'yyyyMMdd_HHmmss')).txt"
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine("REPORTE INFORMES TÉCNICOS — PSEUDONIMIZACIÓN INCOMPLETA")
    [void]$sb.AppendLine("Fecha: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')")
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
