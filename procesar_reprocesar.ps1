# ==============================================================================
# ARCOTEL PAS v4.5 — PROCESAMIENTO LIMPIO (BD VACÍA)
# Informes Técnicos (14 docs) + Peticiones Razonadas (8 docs)
# ==============================================================================
# USO: .\procesar_reprocesar.ps1
#
# CONTEXTO: docker-compose down -v + build + up -d → BD vacía, prompt v4.5.
# Solo los 22 documentos que aprobaron validación de pseudonimización.
# forzar_reprocesar=false (BD limpia, no hay documentos previos).
#
# FLUJO POR DOCUMENTO:
#   1. POST /api/validacion/previsualizar  → obtiene session_id nuevo
#   2. POST /api/archivos/procesar         → confirmado=true
#
# EXCLUYE: todo lo que no está en las listas hardcodeadas de abajo
# ==============================================================================

$ErrorActionPreference = "Continue"

# ------------------------------------------------------------------------------
# CONFIGURACIÓN
# ------------------------------------------------------------------------------
$BACKEND_URL  = "http://localhost:8000"
$REPORTE_PATH = "./reporte_reprocesar_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
$DELAY_SEG    = 2   # Pausa entre documentos (evitar sobrecarga API)

# Nombres de subdirectorios dentro de .\data\
$DIR_INFORMES   = "informes_tecnicos"
$DIR_PETICIONES = "peticiones_razonadas"

# Informes en scope (CTDGGE20220337 excluido - obligaciones económicas)
$INFORMES_EXCLUIDOS = @("CTDGGE20220337.pdf")

# ------------------------------------------------------------------------------
# FUNCIONES
# ------------------------------------------------------------------------------

function Test-Backend {
    try {
        $health = Invoke-RestMethod -Uri "$BACKEND_URL/health" -Method GET -TimeoutSec 5
        return $health
    } catch {
        return $null
    }
}

function Invoke-Previsualizar {
    param(
        [string]$NombreArchivo,
        [string]$TipoDocumento   # "informe_tecnico" o "peticion_razonada"
    )
    $body = @{
        archivo        = $NombreArchivo
        tipo_documento = $TipoDocumento
    } | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod `
            -Uri "$BACKEND_URL/api/validacion/previsualizar" `
            -Method POST `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec 60
        return $resp
    } catch {
        $msg = $_.Exception.Message
        if ($_.ErrorDetails.Message) { $msg = $_.ErrorDetails.Message }
        return @{ error = $msg }
    }
}

function Invoke-Procesar {
    param(
        [string]$NombreArchivo,
        [string]$SessionId
    )
    $body = @{
        archivos          = @($NombreArchivo)
        session_id        = $SessionId
        confirmado        = $true
        forzar_reprocesar = $false
    } | ConvertTo-Json
    try {
        $resp = Invoke-RestMethod `
            -Uri "$BACKEND_URL/api/archivos/procesar" `
            -Method POST `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec 120
        return $resp
    } catch {
        $msg = $_.Exception.Message
        if ($_.ErrorDetails.Message) { $msg = $_.ErrorDetails.Message }
        return @{ error = $msg }
    }
}

function Procesar-Documento {
    param(
        [string]$Archivo,
        [string]$Fase,
        [int]$Idx,
        [int]$Total
    )

    $pct = [Math]::Round(($Idx / $Total) * 100, 1)
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Cyan
    Write-Host "  $Fase  |  $Idx / $Total  ($pct%)" -ForegroundColor Cyan
    Write-Host "  📄 $Archivo" -ForegroundColor White
    Write-Host "================================================================" -ForegroundColor Cyan

    # PASO 1: Previsualizar (obtener session_id)
    Write-Host "  🔒 PASO 1: Pseudonimizando..." -ForegroundColor Yellow
    # Determinar tipo_documento por fase
    $tipoDoc = if ($Fase -like "*INFORME*") { "informe_tecnico" } else { "peticion_razonada" }
    $prev = Invoke-Previsualizar -NombreArchivo $Archivo -TipoDocumento $tipoDoc

    if ($prev.error) {
        Write-Host "  ❌ Error en previsualización: $($prev.error)" -ForegroundColor Red
        return [PSCustomObject]@{
            fase       = $Fase
            idx        = $Idx
            archivo    = $Archivo
            estado     = "error_previz"
            session_id = ""
            costo_usd  = 0
            tokens_in  = 0
            tokens_out = 0
            mensaje    = $prev.error
            timestamp  = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        }
    }

    $sessionId = $prev.session_id
    $pseudCount = if ($prev.pseudonimos_creados) { $prev.pseudonimos_creados } else { "?" }
    Write-Host "  ✅ Session ID: $sessionId  |  Pseudónimos: $pseudCount" -ForegroundColor Green

    # PASO 2: Procesar con auto-confirmación
    Write-Host "  🚀 PASO 2: Enviando a Claude API (auto-confirmado)..." -ForegroundColor Yellow
    $proc = Invoke-Procesar -NombreArchivo $Archivo -SessionId $sessionId

    if ($proc.error) {
        Write-Host "  ❌ Error en procesamiento: $($proc.error)" -ForegroundColor Red
        return [PSCustomObject]@{
            fase       = $Fase
            idx        = $Idx
            archivo    = $Archivo
            estado     = "error_proc"
            session_id = $sessionId
            costo_usd  = 0
            tokens_in  = 0
            tokens_out = 0
            mensaje    = $proc.error
            timestamp  = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        }
    }

    # Extraer métricas del response
    $detalle   = if ($proc.detalles -and $proc.detalles.Count -gt 0) { $proc.detalles[0] } else { $null }
    $costoUsd  = if ($detalle.costo_usd)  { $detalle.costo_usd }  else { 0 }
    $tokensIn  = if ($detalle.tokens_in)  { $detalle.tokens_in }  else { 0 }
    $tokensOut = if ($detalle.tokens_out) { $detalle.tokens_out } else { 0 }
    $numero    = if ($detalle.numero)     { $detalle.numero }     else { "?" }
    $ruc       = if ($detalle.ruc)        { $detalle.ruc }        else { "?" }
    $estado    = if ($proc.exitosos -gt 0) { "exitoso" } else { "fallido" }

    if ($estado -eq "exitoso") {
        Write-Host "  ✅ OK — Nro: $numero  |  RUC: $ruc  |  Costo: `$$costoUsd USD" -ForegroundColor Green
    } else {
        $errMsg = if ($proc.mensaje) { $proc.mensaje } else { "Sin detalle" }
        Write-Host "  ❌ Fallido: $errMsg" -ForegroundColor Red
    }

    return [PSCustomObject]@{
        fase       = $Fase
        idx        = $Idx
        archivo    = $Archivo
        estado     = $estado
        session_id = $sessionId
        costo_usd  = $costoUsd
        tokens_in  = $tokensIn
        tokens_out = $tokensOut
        mensaje    = $numero
        timestamp  = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    }
}

# ------------------------------------------------------------------------------
# INICIO
# ------------------------------------------------------------------------------
Clear-Host
Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "  ARCOTEL PAS v4.5 — PROCESAMIENTO LIMPIO (BD VACÍA)" -ForegroundColor Magenta
Write-Host "  14 informes + 8 peticiones validados" -ForegroundColor Magenta
Write-Host "  Pseudonimización aprobada → AUTO-CONFIRMA" -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host ""

# Verificar backend
Write-Host "📡 Verificando backend..." -ForegroundColor Yellow
$health = Test-Backend
if (-not $health) {
    Write-Host "❌ Backend NO responde. Ejecuta: docker-compose up -d" -ForegroundColor Red
    Read-Host "Presiona ENTER para salir"
    exit 1
}
Write-Host "✅ Backend UP — v$($health.version) — DB: $($health.database)`n" -ForegroundColor Green

# Listas EXACTAS de documentos que aprobaron validación de pseudonimización
# NO usar Get-ChildItem — solo estos archivos están validados
$archivos_informes = @(
    "CTDG-2024-GE-0032.pdf",
    "CTDG-2025-GE-0335.pdf",
    "CTDG-GE-2022-0435.pdf",
    "CTDG-GE-2022-0449.pdf",
    "CTDG-GE-2022-0456.pdf",
    "CTDG-GE-2022-0473.pdf",
    "CTDG-GE-2022-0480.pdf",
    "CTDG-GE-2022-0483.pdf",
    "CTDG-GE-2022-0485.pdf",
    "CTDG-GE-2022-0487.pdf",
    "CTDG-GE-2022-0488.pdf",
    "CTDG-GE-2022-0490.pdf",
    "CTDG-GE-2023-0041.pdf",
    "CTDG-GE-2023-0096.pdf"
)

$archivos_peticiones = @(
    "CCDS-PR-2022-412.pdf",
    "CCDS-PR-2023-0005.pdf",
    "CCDS-PR-2023-0008.pdf",
    "CCDS-PR-2023-0012.pdf",
    "CCDS-PR-2023-0018.pdf",
    "CCDS-PR-2023-0021.pdf",
    "CCDS-PR-2023-0090.pdf",
    "PR-CTDG-2025-GE-0335.pdf"
)

$total_inf = $archivos_informes.Count
$total_pet = $archivos_peticiones.Count
$total_all = $total_inf + $total_pet

Write-Host "📂 Documentos a procesar:" -ForegroundColor Cyan
Write-Host "   Informes técnicos    : $total_inf  (validados, pseudonimización aprobada)" -ForegroundColor White
Write-Host "   Peticiones razonadas : $total_pet  (validadas, pseudonimización aprobada)" -ForegroundColor White
Write-Host "   Total                : $total_all documentos" -ForegroundColor White
Write-Host "   Modo                 : forzar_reprocesar=true (nueva versión en BD)`n" -ForegroundColor Yellow

if ($total_all -eq 0) {
    Write-Host "❌ No se encontraron archivos PDF en:" -ForegroundColor Red
    Write-Host "   .\data\$DIR_INFORMES\" -ForegroundColor Yellow
    Write-Host "   .\data\$DIR_PETICIONES\" -ForegroundColor Yellow
    Read-Host "Presiona ENTER para salir"
    exit 1
}

# Confirmar antes de empezar
Write-Host "⚠️  Este script REPROCESA todos los documentos (forzar_reprocesar=true)." -ForegroundColor Yellow
Write-Host "   Cada documento generará una nueva versión en la BD." -ForegroundColor Yellow
Write-Host "   La pseudonimización fue validada manualmente en sesión anterior." -ForegroundColor Yellow
$ok = Read-Host "`n¿Continuar? (SI/NO)"
if ($ok -ne "SI") {
    Write-Host "Cancelado." -ForegroundColor Gray
    exit 0
}

# Inicializar CSV
"fase,idx,archivo,estado,session_id,costo_usd,tokens_in,tokens_out,numero_doc,timestamp" |
    Out-File -FilePath $REPORTE_PATH -Encoding UTF8

# Contadores globales
$exitosos  = 0
$fallidos  = 0
$costo_total = 0.0
$tokens_in_total  = 0
$tokens_out_total = 0

# ------------------------------------------------------------------------------
# FASE 1: INFORMES TÉCNICOS
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "================================================================" -ForegroundColor Magenta
Write-Host "  FASE 1: INFORMES TÉCNICOS ($total_inf documentos)" -ForegroundColor Magenta
Write-Host "================================================================" -ForegroundColor Magenta

for ($i = 0; $i -lt $archivos_informes.Count; $i++) {
    $archivo = $archivos_informes[$i]
    $res = Procesar-Documento -Archivo $archivo -Fase "FASE 1 - INFORME" `
           -Idx ($i + 1) -Total $total_inf

    # Registrar en CSV
    "$($res.fase),$($res.idx),$($res.archivo),$($res.estado),$($res.session_id)," +
    "$($res.costo_usd),$($res.tokens_in),$($res.tokens_out),$($res.mensaje),$($res.timestamp)" |
        Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8

    if ($res.estado -eq "exitoso") { $exitosos++ } else { $fallidos++ }
    $costo_total      += $res.costo_usd
    $tokens_in_total  += $res.tokens_in
    $tokens_out_total += $res.tokens_out

    # Pausa entre documentos (excepto el último)
    if ($i -lt ($archivos_informes.Count - 1)) {
        Write-Host "  ⏳ Esperando $DELAY_SEG segundos..." -ForegroundColor Gray
        Start-Sleep -Seconds $DELAY_SEG
    }
}

Write-Host ""
Write-Host "  ✅ FASE 1 COMPLETADA — Exitosos: $exitosos | Fallidos: $fallidos" -ForegroundColor Magenta
Write-Host "     Costo acumulado: `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow

# ------------------------------------------------------------------------------
# FASE 2: PETICIONES RAZONADAS
# ------------------------------------------------------------------------------
if ($total_pet -eq 0) {
    Write-Host "`n⚠️  No se encontraron peticiones razonadas. Omitiendo Fase 2." -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "================================================================" -ForegroundColor Magenta
    Write-Host "  FASE 2: PETICIONES RAZONADAS ($total_pet documentos)" -ForegroundColor Magenta
    Write-Host "================================================================" -ForegroundColor Magenta

    $exitosos_pet = 0
    $fallidos_pet = 0

    for ($i = 0; $i -lt $archivos_peticiones.Count; $i++) {
        $archivo = $archivos_peticiones[$i]
        $res = Procesar-Documento -Archivo $archivo -Fase "FASE 2 - PETICIÓN" `
               -Idx ($i + 1) -Total $total_pet

        "$($res.fase),$($res.idx),$($res.archivo),$($res.estado),$($res.session_id)," +
        "$($res.costo_usd),$($res.tokens_in),$($res.tokens_out),$($res.mensaje),$($res.timestamp)" |
            Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8

        if ($res.estado -eq "exitoso") { $exitosos++; $exitosos_pet++ } else { $fallidos++; $fallidos_pet++ }
        $costo_total      += $res.costo_usd
        $tokens_in_total  += $res.tokens_in
        $tokens_out_total += $res.tokens_out

        if ($i -lt ($archivos_peticiones.Count - 1)) {
            Write-Host "  ⏳ Esperando $DELAY_SEG segundos..." -ForegroundColor Gray
            Start-Sleep -Seconds $DELAY_SEG
        }
    }

    Write-Host ""
    Write-Host "  ✅ FASE 2 COMPLETADA — Exitosos: $exitosos_pet | Fallidos: $fallidos_pet" -ForegroundColor Magenta
    Write-Host "     Costo acumulado: `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
}

# ------------------------------------------------------------------------------
# RESUMEN FINAL
# ------------------------------------------------------------------------------
Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  RESUMEN FINAL" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  ✅ Exitosos : $exitosos / $total_all" -ForegroundColor Green
Write-Host "  ❌ Fallidos : $fallidos / $total_all" -ForegroundColor Red
Write-Host "  💰 Costo    : `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "  🔢 Tokens   : $($tokens_in_total.ToString('N0')) in + $($tokens_out_total.ToString('N0')) out" -ForegroundColor White
Write-Host ""
Write-Host "  📁 Reporte CSV: $REPORTE_PATH" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ▶️  SIGUIENTE PASO:" -ForegroundColor Cyan
Write-Host "     1. Exportar gold standard:" -ForegroundColor White
Write-Host "        python exportar_gold_standard.py" -ForegroundColor Gray
Write-Host "     2. Completar validación manual en Excel" -ForegroundColor White
Write-Host "     3. Calcular F1:" -ForegroundColor White
Write-Host "        python calcular_f1_extraccion.py" -ForegroundColor Gray
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

Read-Host "Presiona ENTER para finalizar"