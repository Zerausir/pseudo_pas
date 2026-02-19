# ==================================================
# PROCESAMIENTO MASIVO: 22 Informes + 22 Peticiones
# ARCOTEL PAS v4.0 - Validación Individual LOPDP
# ==================================================
# Flujo:
#   FASE 1: Procesa los 22 informes técnicos
#   FASE 2: Procesa las 22 peticiones razonadas
#
# Cada documento requiere validación visual individual
# antes de enviarse a Claude API (LOPDP Arts. 8, 10.e, 33, 37)
# ==================================================

$ErrorActionPreference = "Continue"

# ----------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------
$BACKEND_URL    = "http://localhost:8000"
$REPORTE_PATH   = "./reporte_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
$PROGRESO_PATH  = "./progreso_sesion.json"

# Directorios donde están los PDFs (sin extensión .pdf → lo agrega el script)
$DIR_INFORMES   = "informes_tecnicos"
$DIR_PETICIONES = "peticiones_razonadas"

# Endpoints por tipo de documento
$TIPO_INFORME   = "informe_tecnico"
$TIPO_PETICION  = "peticion_razonada"

# ----------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------

function Mostrar-Encabezado {
    param($fase, $num, $total, $archivo, $exitosos, $fallidos, $saltados)
    $pct = [Math]::Round(($num / $total) * 100, 1)
    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  $fase  |  $num / $total ($pct%)" -ForegroundColor Cyan
    Write-Host "  ✅ $exitosos  ❌ $fallidos  ⏭️  $saltados" -ForegroundColor Cyan
    Write-Host "  📄 $archivo" -ForegroundColor White
    Write-Host "========================================================`n" -ForegroundColor Cyan
}

function Procesar-Documento {
    param(
        [string]$Archivo,        # Solo nombre del archivo (sin ruta)
        [string]$TipoDoc,        # "informe_tecnico" o "peticion_razonada"
        [string]$NumStr,         # "3/22"
        [string]$FaseLabel,      # "FASE 1 - INFORME" o "FASE 2 - PETICIÓN"
        [int]$ExitososRef,
        [int]$FallidosRef,
        [int]$SaltadosRef,
        [hashtable]$ProcesadosPrevios
    )

    $num   = $NumStr.Split('/')[0]
    $total = $NumStr.Split('/')[1]

    Mostrar-Encabezado -fase $FaseLabel -num $num -total $total `
        -archivo $Archivo `
        -exitosos $ExitososRef -fallidos $FallidosRef -saltados $SaltadosRef

    # ── Verificar si ya fue procesado ────────────────────────────
    if ($ProcesadosPrevios.ContainsKey($Archivo) -and
        $ProcesadosPrevios[$Archivo] -ne "saltado") {
        Write-Host "⏭️  Ya procesado en sesión anterior. Saltando...`n" -ForegroundColor Gray
        return @{ resultado = "ya_procesado"; session_id = $null }
    }

    # ── PASO 1: Previsualización ──────────────────────────────────
    Write-Host "🔍 Generando previsualización de pseudonimización..." -ForegroundColor Yellow

    $previoBody = @{
        archivo        = $Archivo
        tipo_documento = $TipoDoc
    } | ConvertTo-Json

    try {
        $validacion = Invoke-RestMethod `
            -Uri "$BACKEND_URL/api/validacion/previsualizar" `
            -Method POST `
            -ContentType "application/json" `
            -Body $previoBody

        Write-Host "✅ Pseudonimización lista:" -ForegroundColor Green
        Write-Host "   🆔 Session ID : $($validacion.session_id)" -ForegroundColor White
        Write-Host "   🔢 Pseudónimos: $($validacion.pseudonyms_count) " -NoNewline -ForegroundColor White
        $desglose = $validacion.pseudonyms_by_type.PSObject.Properties |
            ForEach-Object { "$($_.Name):$($_.Value)" }
        Write-Host "($($desglose -join ', '))" -ForegroundColor Gray

        $session_id = $validacion.session_id
        $html_file  = $validacion.html_filename

    } catch {
        Write-Host "❌ Error en previsualización: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.ErrorDetails.Message) {
            Write-Host $_.ErrorDetails.Message -ForegroundColor Red
        }
        return @{ resultado = "error_previo"; session_id = $null }
    }

    # ── PASO 2: Descargar y abrir HTML ────────────────────────────
    Write-Host "`n🌐 Abriendo en navegador para revisión..." -ForegroundColor Yellow
    try {
        $html_local = "./$html_file"
        Invoke-WebRequest -Uri "$BACKEND_URL/outputs/$html_file" -OutFile $html_local
        Start-Process $html_local
        Start-Sleep -Seconds 2
    } catch {
        Write-Host "⚠️  No se pudo abrir automáticamente. URL: $BACKEND_URL/outputs/$html_file" -ForegroundColor Yellow
    }

    # ── PASO 3: Confirmación obligatoria ──────────────────────────
    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│  ⚠️  VALIDACIÓN OBLIGATORIA - LOPDP Arts. 8, 10.e  │" -ForegroundColor Yellow
    Write-Host "│  Verifica que NO aparezca ningún dato personal real │" -ForegroundColor Yellow
    Write-Host "│  NOMBRE_XX · CEDULA_XX · EMAIL_XX · DIRECCION_XX   │" -ForegroundColor Yellow
    Write-Host "└─────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""

    $confirmacion = Read-Host "[$NumStr] ¿Documento 100% pseudonimizado? (SI / NO / SALTAR)"

    if ($confirmacion -eq "SALTAR") {
        Write-Host "⏭️  Saltado manualmente.`n" -ForegroundColor Gray
        return @{ resultado = "saltado"; session_id = $null }
    }

    if ($confirmacion -ne "SI") {
        Write-Host "❌ Validación rechazada. Documento NO procesado.`n" -ForegroundColor Red
        return @{ resultado = "rechazado"; session_id = $null }
    }

    # ── PASO 4: Procesar con Claude API ──────────────────────────
    Write-Host "`n🚀 Enviando a Claude API..." -ForegroundColor Yellow

    $procesoBody = @{
        archivos   = @($Archivo)
        session_id = $session_id
        confirmado = $true
    } | ConvertTo-Json

    try {
        $resultado = Invoke-RestMethod `
            -Uri "$BACKEND_URL/api/archivos/procesar" `
            -Method POST `
            -ContentType "application/json" `
            -Body $procesoBody `
            -TimeoutSec 180

        $detalle = $resultado.detalles[0]

        if ($detalle.estado -eq "exitoso") {
            $validIcon = if ($detalle.validacion.es_valido) { "✅ Válido" } else { "⚠️  Con inconsistencias" }
            Write-Host "✅ Procesado exitosamente" -ForegroundColor Green
            Write-Host "   Caso: $($detalle.caso_id) | Doc: $($detalle.documento_id)" -ForegroundColor White
            Write-Host "   Validación: $validIcon ($($detalle.validacion.inconsistencias) inconsistencias)" -ForegroundColor White
            Write-Host "   Costo: `$$($resultado.costo_total_usd) USD | Tokens: $($resultado.tokens_total)" -ForegroundColor White

            return @{
                resultado    = "exitoso"
                detalle      = $detalle
                costo_usd    = [double]$resultado.costo_total_usd
                tokens       = [int]$resultado.tokens_total
                tokens_input = [int]$resultado.tokens_total_input
                tokens_output= [int]$resultado.tokens_total_output
                session_id   = $session_id
            }
        } else {
            $msg = if ($detalle.mensaje) { $detalle.mensaje } else { "Error desconocido" }
            Write-Host "❌ Error procesamiento: $msg" -ForegroundColor Red
            return @{ resultado = $detalle.estado; mensaje = $msg; session_id = $null }
        }

    } catch {
        $err = $_.Exception.Message
        Write-Host "❌ Error HTTP: $err" -ForegroundColor Red
        if ($_.ErrorDetails.Message) {
            Write-Host $_.ErrorDetails.Message -ForegroundColor Red
        }
        return @{ resultado = "error_http"; mensaje = $err; session_id = $null }
    }
}

# ----------------------------------------------
# INICIALIZACIÓN
# ----------------------------------------------

Clear-Host
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ARCOTEL PAS v4.0 — PROCESAMIENTO MASIVO" -ForegroundColor Cyan
Write-Host "  22 Informes Técnicos + 22 Peticiones Razonadas" -ForegroundColor Cyan
Write-Host "  Validación individual LOPDP por documento" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# Verificar backend
Write-Host "📡 Verificando backend..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$BACKEND_URL/health" -TimeoutSec 5
    Write-Host "✅ Backend UP — Version: $($health.version)`n" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend NO responde. Ejecuta: docker-compose up -d`n" -ForegroundColor Red
    Read-Host "Presiona ENTER para salir"
    exit 1
}

# Leer archivos de los directorios (excluye README)
$archivos_informes   = Get-ChildItem ".\data\$DIR_INFORMES\*.pdf" |
    Select-Object -ExpandProperty Name | Sort-Object

$archivos_peticiones = Get-ChildItem ".\data\$DIR_PETICIONES\*.pdf" |
    Select-Object -ExpandProperty Name | Sort-Object

$total_informes   = $archivos_informes.Count
$total_peticiones = $archivos_peticiones.Count
$total_docs       = $total_informes + $total_peticiones

Write-Host "📂 Archivos detectados:" -ForegroundColor Cyan
Write-Host "   Informes técnicos  : $total_informes" -ForegroundColor White
Write-Host "   Peticiones razonadas: $total_peticiones" -ForegroundColor White
Write-Host "   Total              : $total_docs documentos`n" -ForegroundColor White

if ($total_informes -eq 0 -or $total_peticiones -eq 0) {
    Write-Host "❌ No se encontraron archivos en los directorios." -ForegroundColor Red
    Write-Host "   Verifica que existan:" -ForegroundColor Yellow
    Write-Host "   .\data\informes_tecnicos\*.pdf" -ForegroundColor White
    Write-Host "   .\data\peticiones_razonadas\*.pdf" -ForegroundColor White
    Read-Host "Presiona ENTER para salir"
    exit 1
}

# Verificar sesión previa para reanudar
$procesados_previos = @{}
if (Test-Path $PROGRESO_PATH) {
    Write-Host "⚠️  Se encontró sesión previa." -ForegroundColor Yellow
    $reanudar = Read-Host "¿Deseas reanudar desde donde quedaste? (SI/NO)"
    if ($reanudar -eq "SI") {
        $prev = Get-Content $PROGRESO_PATH | ConvertFrom-Json
        foreach ($item in $prev) {
            $procesados_previos[$item.archivo] = $item.estado
        }
        $ya = ($procesados_previos.Values | Where-Object { $_ -ne "saltado" }).Count
        Write-Host "✅ Reanudando: $ya documentos ya procesados`n" -ForegroundColor Green
    } else {
        Remove-Item $PROGRESO_PATH -ErrorAction SilentlyContinue
        Write-Host "🆕 Sesión nueva`n" -ForegroundColor Cyan
    }
}

# Inicializar CSV
"Fase,Numero,Archivo,Estado,CasoID,DocumentoID,EsValido,Inconsistencias,CostoUSD,TokensInput,TokensOutput,Timestamp,Mensaje" |
    Out-File -FilePath $REPORTE_PATH -Encoding UTF8

# Contadores globales
$exitosos    = 0
$fallidos    = 0
$saltados    = 0
$costo_total = 0.0
$tokens_in   = 0
$tokens_out  = 0
$progreso    = @()

# ----------------------------------------------
# FASE 1: INFORMES TÉCNICOS
# ----------------------------------------------

Write-Host ""
Write-Host "========================================================"  -ForegroundColor Magenta
Write-Host "  FASE 1: INFORMES TÉCNICOS ($total_informes documentos)" -ForegroundColor Magenta
Write-Host "========================================================`n" -ForegroundColor Magenta

for ($i = 0; $i -lt $archivos_informes.Count; $i++) {
    $archivo = $archivos_informes[$i]
    $numStr  = "$($i + 1)/$total_informes"

    $res = Procesar-Documento `
        -Archivo $archivo `
        -TipoDoc $TIPO_INFORME `
        -NumStr $numStr `
        -FaseLabel "FASE 1 - INFORME" `
        -ExitososRef $exitosos `
        -FallidosRef $fallidos `
        -SaltadosRef $saltados `
        -ProcesadosPrevios $procesados_previos

    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    switch ($res.resultado) {
        "exitoso" {
            $exitosos++
            $costo_total += $res.costo_usd
            $tokens_in   += $res.tokens_input
            $tokens_out  += $res.tokens_output
            $d = $res.detalle
            "Fase1,$($i+1),$archivo,exitoso,$($d.caso_id),$($d.documento_id),$($d.validacion.es_valido),$($d.validacion.inconsistencias),$($res.costo_usd),$($res.tokens_input),$($res.tokens_output),$ts," |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "exitoso" }
        }
        "ya_procesado" {
            $saltados++
            "Fase1,$($i+1),$archivo,ya_procesado,,,,,,,,$ts,Procesado en sesión anterior" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "exitoso" }
        }
        "saltado" {
            $saltados++
            "Fase1,$($i+1),$archivo,saltado,,,,,,,,$ts,Saltado manualmente" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "saltado" }
        }
        default {
            $fallidos++
            $msg = if ($res.mensaje) { $res.mensaje } else { $res.resultado }
            "Fase1,$($i+1),$archivo,$($res.resultado),,,,,,,,$ts,$msg" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "error" }
        }
    }

    $progreso | ConvertTo-Json | Out-File -FilePath $PROGRESO_PATH -Encoding UTF8

    if ($i -lt ($archivos_informes.Count - 1)) {
        Write-Host "`n⏳ Preparando siguiente documento..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

# Resumen Fase 1
Write-Host ""
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "  ✅ FASE 1 COMPLETADA" -ForegroundColor Magenta
Write-Host "     Exitosos: $exitosos | Fallidos: $fallidos | Saltados: $saltados" -ForegroundColor White
Write-Host "     Costo acumulado: `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "========================================================`n" -ForegroundColor Magenta

# Pausa entre fases
Write-Host "🔄 Las peticiones razonadas requieren que sus informes estén en BD." -ForegroundColor Yellow
Write-Host "   Si todos los informes se procesaron, puedes continuar.`n" -ForegroundColor White
$continuar = Read-Host "¿Continuar con FASE 2 - Peticiones Razonadas? (SI/NO)"
if ($continuar -ne "SI") {
    Write-Host "`n⏸️  Sesión pausada. El progreso está guardado en $PROGRESO_PATH" -ForegroundColor Yellow
    Write-Host "   Vuelve a ejecutar el script para continuar con la Fase 2.`n" -ForegroundColor White
    Read-Host "Presiona ENTER para salir"
    exit 0
}

# ----------------------------------------------
# FASE 2: PETICIONES RAZONADAS
# ----------------------------------------------

Write-Host ""
Write-Host "========================================================" -ForegroundColor Blue
Write-Host "  FASE 2: PETICIONES RAZONADAS ($total_peticiones documentos)" -ForegroundColor Blue
Write-Host "========================================================`n" -ForegroundColor Blue

$exitosos_f2 = 0
$fallidos_f2 = 0
$saltados_f2 = 0

for ($i = 0; $i -lt $archivos_peticiones.Count; $i++) {
    $archivo = $archivos_peticiones[$i]
    $numStr  = "$($i + 1)/$total_peticiones"

    $res = Procesar-Documento `
        -Archivo $archivo `
        -TipoDoc $TIPO_PETICION `
        -NumStr $numStr `
        -FaseLabel "FASE 2 - PETICIÓN" `
        -ExitososRef $exitosos_f2 `
        -FallidosRef $fallidos_f2 `
        -SaltadosRef $saltados_f2 `
        -ProcesadosPrevios $procesados_previos

    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    switch ($res.resultado) {
        "exitoso" {
            $exitosos++
            $exitosos_f2++
            $costo_total += $res.costo_usd
            $tokens_in   += $res.tokens_input
            $tokens_out  += $res.tokens_output
            $d = $res.detalle
            "Fase2,$($i+1),$archivo,exitoso,$($d.caso_id),$($d.documento_id),$($d.validacion.es_valido),$($d.validacion.inconsistencias),$($res.costo_usd),$($res.tokens_input),$($res.tokens_output),$ts," |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "exitoso" }
        }
        "ya_procesado" {
            $saltados++
            $saltados_f2++
            "Fase2,$($i+1),$archivo,ya_procesado,,,,,,,,$ts,Procesado en sesión anterior" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "exitoso" }
        }
        "saltado" {
            $saltados++
            $saltados_f2++
            "Fase2,$($i+1),$archivo,saltado,,,,,,,,$ts,Saltado manualmente" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "saltado" }
        }
        default {
            $fallidos++
            $fallidos_f2++
            $msg = if ($res.mensaje) { $res.mensaje } else { $res.resultado }
            "Fase2,$($i+1),$archivo,$($res.resultado),,,,,,,,$ts,$msg" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            $progreso += [PSCustomObject]@{ archivo = $archivo; estado = "error" }
        }
    }

    $progreso | ConvertTo-Json | Out-File -FilePath $PROGRESO_PATH -Encoding UTF8

    if ($i -lt ($archivos_peticiones.Count - 1)) {
        Write-Host "`n⏳ Preparando siguiente documento..." -ForegroundColor Gray
        Start-Sleep -Seconds 2
    }
}

# ----------------------------------------------
# REPORTE FINAL
# ----------------------------------------------

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ✅ PROCESAMIENTO COMPLETO" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

$total_procesados = $exitosos + $fallidos
$tasa = if ($total_procesados -gt 0) {
    [Math]::Round(($exitosos / $total_procesados) * 100, 1)
} else { 0 }

Write-Host "📊 RESUMEN GLOBAL:" -ForegroundColor Cyan
Write-Host "   Total documentos  : $total_docs" -ForegroundColor White
Write-Host "   ✅ Exitosos        : $exitosos" -ForegroundColor Green
Write-Host "   ❌ Fallidos        : $fallidos" -ForegroundColor $(if ($fallidos -eq 0) {"Green"} else {"Red"})
Write-Host "   ⏭️  Saltados        : $saltados" -ForegroundColor Gray
Write-Host "   📈 Tasa de éxito   : $tasa%" -ForegroundColor $(if ($tasa -ge 90) {"Green"} elseif ($tasa -ge 70) {"Yellow"} else {"Red"})
Write-Host "   💰 Costo total     : `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "   🔢 Tokens input    : $($tokens_in.ToString('N0'))" -ForegroundColor White
Write-Host "   🔢 Tokens output   : $($tokens_out.ToString('N0'))" -ForegroundColor White

Write-Host ""
Write-Host "📊 RESUMEN POR FASE:" -ForegroundColor Cyan
Write-Host "   Fase 1 (Informes)  : exitosos=$($exitosos - $exitosos_f2) fallidos=$($fallidos - $fallidos_f2)" -ForegroundColor White
Write-Host "   Fase 2 (Peticiones): exitosos=$exitosos_f2 fallidos=$fallidos_f2" -ForegroundColor White

Write-Host ""
Write-Host "📊 CUMPLIMIENTO LOPDP:" -ForegroundColor Cyan
Write-Host "   ✅ Cada documento validado visualmente de forma individual" -ForegroundColor Green
Write-Host "   ✅ Confirmación explícita requerida por documento" -ForegroundColor Green
Write-Host "   ✅ Datos reales almacenados solo en BD local" -ForegroundColor Green

Write-Host ""
Write-Host "📁 ARCHIVOS:" -ForegroundColor Cyan
Write-Host "   Reporte CSV : $REPORTE_PATH" -ForegroundColor White
Write-Host "   Progreso    : $PROGRESO_PATH" -ForegroundColor White

# Limpiar progreso si todo completado
if ($saltados -eq 0 -and ($exitosos + $fallidos) -eq $total_docs) {
    Remove-Item $PROGRESO_PATH -ErrorAction SilentlyContinue
    Write-Host "   ✅ Sesión completada - progreso eliminado" -ForegroundColor Green
}

Write-Host ""
Read-Host "Presiona ENTER para finalizar"
