# ==================================================
# REPROCESAMIENTO: 5 documentos fallidos
# ARCOTEL PAS v4.0 - Validación Individual LOPDP
# CON CAPTURA AUTOMÁTICA DE MÉTRICAS (VP + FN)
# ==================================================
# Documentos a reprocesar:
#   FASE 1 (1 informe):
#     - CTDG-GE-2024-0148.pdf       → Era 404 (nombre incorrecto en lista anterior)
#   FASE 2 (4 peticiones):
#     - CCDE-PR-2021-194.pdf        → Fix prefijo IT-
#     - CCDE-PR-2021-203.pdf        → Fix prefijo IT-
#     - PR-CCDS-2024-0129.pdf       → Dependía de CTDG-GE-2024-0148
#     - PR-CTDG-2025-GE-0607.pdf    → Fix RUC con espacio OCR
#
# ORDEN OBLIGATORIO: el informe CTDG-GE-2024-0148 debe procesarse
# antes que PR-CCDS-2024-0129 (que lo referencia)
# ==================================================

$ErrorActionPreference = "Continue"

$BACKEND_URL  = "http://localhost:8000"
$REPORTE_PATH = "./reporte_reproceso_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
$VP_CSV_PATH  = "./vp_conteos.csv"
$FN_CSV_PATH  = "./fn_anotaciones.csv"

$TIPO_INFORME  = "informe_tecnico"
$TIPO_PETICION = "peticion_razonada"

# ----------------------------------------------
# DOCUMENTOS A REPROCESAR (orden es crítico)
# ----------------------------------------------
$archivos_informes = @(
    "CTDG-GE-2024-0148.pdf"
)

$archivos_peticiones = @(
    "CCDE-PR-2021-194.pdf",
    "CCDE-PR-2021-203.pdf",
    "PR-CCDS-2024-0129.pdf",
    "PR-CTDG-2025-GE-0607.pdf"
)

$total_informes   = $archivos_informes.Count
$total_peticiones = $archivos_peticiones.Count
$total_docs       = $total_informes + $total_peticiones

# CSVs de métricas: solo agrega, nunca sobreescribe
if (-not (Test-Path $VP_CSV_PATH)) {
    "documento,tipo_doc,RUC,CEDULA,EMAIL,TELEFONO,DIRECCION,NOMBRE,total_vp,timestamp" |
        Out-File -FilePath $VP_CSV_PATH -Encoding UTF8
    Write-Host "📊 Creado: $VP_CSV_PATH" -ForegroundColor Cyan
} else {
    Write-Host "📊 Agregando a existente: $VP_CSV_PATH" -ForegroundColor Cyan
}

if (-not (Test-Path $FN_CSV_PATH)) {
    "documento,tipo_doc,entidad_valor,tipo_entidad,capa,resultado" |
        Out-File -FilePath $FN_CSV_PATH -Encoding UTF8
    Write-Host "📊 Creado: $FN_CSV_PATH" -ForegroundColor Cyan
} else {
    Write-Host "📊 Agregando a existente: $FN_CSV_PATH" -ForegroundColor Cyan
}

# ----------------------------------------------
# FUNCIÓN: Capturar FN interactivamente
# ----------------------------------------------
function Capturar-FN {
    param([string]$Archivo, [string]$TipoDoc)

    $fn_lista = @()

    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────┐" -ForegroundColor Red
    Write-Host "│  📝 REGISTRO DE DATOS NO PSEUDONIMIZADOS (FN)       │" -ForegroundColor Red
    Write-Host "│  Ingresa CADA dato que quedó expuesto               │" -ForegroundColor Red
    Write-Host "└─────────────────────────────────────────────────────┘" -ForegroundColor Red

    $TIPO_A_CAPA = @{
        "RUC"       = "1_regex"
        "CEDULA"    = "1_regex"
        "EMAIL"     = "1_regex"
        "TELEFONO"  = "1.5_contextual"
        "DIRECCION" = "1.5_contextual"
        "NOMBRE"    = "2_spacy"
    }

    $continuar = $true
    while ($continuar) {
        Write-Host ""
        $valor = Read-Host "  Dato expuesto (texto exacto)"
        if ([string]::IsNullOrWhiteSpace($valor)) {
            Write-Host "  ⚠️  Valor vacío. Intenta de nuevo." -ForegroundColor Yellow
            continue
        }

        Write-Host "  Tipo de entidad:"
        Write-Host "    1) NOMBRE    2) EMAIL    3) TELEFONO"
        Write-Host "    4) DIRECCION 5) RUC      6) CEDULA"
        $tipo_opt     = Read-Host "  Opción (1-6)"
        $tipo_map     = @{"1"="NOMBRE";"2"="EMAIL";"3"="TELEFONO";"4"="DIRECCION";"5"="RUC";"6"="CEDULA"}
        $tipo_entidad = $tipo_map[$tipo_opt]
        if (-not $tipo_entidad) {
            Write-Host "  ⚠️  Opción inválida. Usando NOMBRE por defecto." -ForegroundColor Yellow
            $tipo_entidad = "NOMBRE"
        }

        $capa = $TIPO_A_CAPA[$tipo_entidad]
        Write-Host "  🔍 Capa asignada automáticamente: $capa" -ForegroundColor Gray

        $fn_lista += [PSCustomObject]@{
            documento     = $Archivo -replace '\.pdf$', ''
            tipo_doc      = $TipoDoc
            entidad_valor = $valor
            tipo_entidad  = $tipo_entidad
            capa          = $capa
            resultado     = "FN"
        }

        Write-Host "  ✅ Registrado: '$valor' ($tipo_entidad / $capa)" -ForegroundColor Green
        $otro     = Read-Host "  ¿Hay otro dato no pseudonimizado? (SI/NO)"
        $continuar = ($otro -eq "SI")
    }

    foreach ($fn in $fn_lista) {
        "$($fn.documento),$($fn.tipo_doc),$($fn.entidad_valor),$($fn.tipo_entidad),$($fn.capa),$($fn.resultado)" |
            Out-File -FilePath $FN_CSV_PATH -Append -Encoding UTF8
    }

    Write-Host "  💾 $($fn_lista.Count) FN guardados en $FN_CSV_PATH" -ForegroundColor Cyan
    return $fn_lista.Count
}

# ----------------------------------------------
# FUNCIÓN: Guardar VP en CSV
# ----------------------------------------------
function Guardar-VP {
    param([string]$Archivo, [string]$TipoDoc, [object]$PseudonimosPorTipo)

    $doc_id = $Archivo -replace '\.pdf$', ''
    $tipo   = if ($TipoDoc -eq "informe_tecnico") { "informe" } else { "peticion" }
    $ts     = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    $ruc      = if ($PseudonimosPorTipo.PSObject.Properties["RUC"])       { $PseudonimosPorTipo.RUC }       else { 0 }
    $cedula   = if ($PseudonimosPorTipo.PSObject.Properties["CEDULA"])    { $PseudonimosPorTipo.CEDULA }    else { 0 }
    $email    = if ($PseudonimosPorTipo.PSObject.Properties["EMAIL"])     { $PseudonimosPorTipo.EMAIL }     else { 0 }
    $telefono = if ($PseudonimosPorTipo.PSObject.Properties["TELEFONO"])  { $PseudonimosPorTipo.TELEFONO }  else { 0 }
    $dir      = if ($PseudonimosPorTipo.PSObject.Properties["DIRECCION"]) { $PseudonimosPorTipo.DIRECCION } else { 0 }
    $nombre   = if ($PseudonimosPorTipo.PSObject.Properties["NOMBRE"])    { $PseudonimosPorTipo.NOMBRE }    else { 0 }
    $total    = $ruc + $cedula + $email + $telefono + $dir + $nombre

    "$doc_id,$tipo,$ruc,$cedula,$email,$telefono,$dir,$nombre,$total,$ts" |
        Out-File -FilePath $VP_CSV_PATH -Append -Encoding UTF8

    Write-Host "   💾 VP guardados: RUC=$ruc CED=$cedula EMAIL=$email TEL=$telefono DIR=$dir NOM=$nombre (Total=$total)" -ForegroundColor Gray
}

# ----------------------------------------------
# FUNCIÓN PRINCIPAL: Procesar documento
# ----------------------------------------------
function Procesar-Documento {
    param(
        [string]$Archivo,
        [string]$TipoDoc,
        [string]$NumStr,
        [string]$FaseLabel
    )

    $num   = $NumStr.Split('/')[0]
    $total = $NumStr.Split('/')[1]

    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  $FaseLabel  |  $num / $total" -ForegroundColor Cyan
    Write-Host "  📄 $Archivo" -ForegroundColor White
    Write-Host "========================================================`n" -ForegroundColor Cyan

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

        Guardar-VP -Archivo $Archivo -TipoDoc $TipoDoc -PseudonimosPorTipo $validacion.pseudonyms_by_type

    } catch {
        Write-Host "❌ Error en previsualización: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message -ForegroundColor Red }
        return @{ resultado = "error_previo" }
    }

    # ── PASO 2: Abrir HTML ────────────────────────────────────────
    Write-Host "`n🌐 Abriendo en navegador para revisión..." -ForegroundColor Yellow
    try {
        $html_local = "./$html_file"
        Invoke-WebRequest -Uri "$BACKEND_URL/outputs/$html_file" -OutFile $html_local
        Start-Process $html_local
        Start-Sleep -Seconds 2
    } catch {
        Write-Host "⚠️  No se pudo abrir automáticamente. URL: $BACKEND_URL/outputs/$html_file" -ForegroundColor Yellow
    }

    # ── PASO 3: Validación ────────────────────────────────────────
    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│  ⚠️  VALIDACIÓN OBLIGATORIA - LOPDP Arts. 8, 10.e  │" -ForegroundColor Yellow
    Write-Host "│  Verifica que NO aparezca ningún dato personal real │" -ForegroundColor Yellow
    Write-Host "│  NOMBRE_XX · CEDULA_XX · EMAIL_XX · DIRECCION_XX   │" -ForegroundColor Yellow
    Write-Host "└─────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  OK     → Pseudonimización completa, procesar con Claude" -ForegroundColor Green
    Write-Host "  MAL    → Hay datos expuestos, registrar FN y saltar"     -ForegroundColor Red
    Write-Host "  SALTAR → Omitir sin registrar"                           -ForegroundColor Gray
    Write-Host ""

    $confirmacion = Read-Host "[$NumStr] ¿Resultado de validación? (OK / MAL / SALTAR)"

    if ($confirmacion -eq "SALTAR") {
        Write-Host "⏭️  Saltado manualmente.`n" -ForegroundColor Gray
        return @{ resultado = "saltado" }
    }

    if ($confirmacion -eq "MAL") {
        $tipo_doc_corto  = if ($TipoDoc -eq "informe_tecnico") { "informe" } else { "peticion" }
        $archivo_sin_pdf = $Archivo -replace '\.pdf$', ''
        $fn_count = Capturar-FN -Archivo $archivo_sin_pdf -TipoDoc $tipo_doc_corto
        Write-Host ""
        Write-Host "⏭️  Documento NO enviado a Claude API (LOPDP: pseudonimización incompleta)." -ForegroundColor Yellow
        Write-Host "   $fn_count FN registrados para métricas.`n" -ForegroundColor Yellow
        return @{ resultado = "rechazado_fn"; fn_count = $fn_count }
    }

    if ($confirmacion -ne "OK") {
        Write-Host "❌ Respuesta no reconocida. Documento saltado.`n" -ForegroundColor Red
        return @{ resultado = "saltado" }
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
                resultado     = "exitoso"
                detalle       = $detalle
                costo_usd     = [double]$resultado.costo_total_usd
                tokens_input  = [int]$resultado.tokens_total_input
                tokens_output = [int]$resultado.tokens_total_output
            }
        } else {
            $msg = if ($detalle.mensaje) { $detalle.mensaje } else { "Error desconocido" }
            Write-Host "❌ Error procesamiento: $msg" -ForegroundColor Red
            return @{ resultado = $detalle.estado; mensaje = $msg }
        }

    } catch {
        Write-Host "❌ Error HTTP: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message -ForegroundColor Red }
        return @{ resultado = "error_http" }
    }
}

# ----------------------------------------------
# INICIALIZACIÓN
# ----------------------------------------------
Clear-Host
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ARCOTEL PAS v4.0 — REPROCESAMIENTO DE 5 FALLIDOS" -ForegroundColor Cyan
Write-Host "  1 Informe Técnico + 4 Peticiones Razonadas" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

Write-Host "📡 Verificando backend..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$BACKEND_URL/health" -TimeoutSec 5
    Write-Host "✅ Backend UP — Version: $($health.version)`n" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend NO responde. Ejecuta: docker-compose up -d`n" -ForegroundColor Red
    Read-Host "Presiona ENTER para salir"
    exit 1
}

# Inicializar CSV de reporte
"Fase,Numero,Archivo,Estado,CasoID,DocumentoID,EsValido,Inconsistencias,CostoUSD,TokensInput,TokensOutput,FN_Count,Timestamp,Mensaje" |
    Out-File -FilePath $REPORTE_PATH -Encoding UTF8

$exitosos    = 0
$fallidos    = 0
$rechazados  = 0
$fn_total    = 0
$costo_total = 0.0
$tokens_in   = 0
$tokens_out  = 0

# ----------------------------------------------
# FASE 1: INFORME (1 documento)
# ----------------------------------------------
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "  FASE 1: INFORME TÉCNICO (1 documento)" -ForegroundColor Magenta
Write-Host "========================================================`n" -ForegroundColor Magenta

for ($i = 0; $i -lt $archivos_informes.Count; $i++) {
    $archivo = $archivos_informes[$i]
    $numStr  = "$($i + 1)/$total_informes"
    $ts      = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    $res = Procesar-Documento -Archivo $archivo -TipoDoc $TIPO_INFORME `
                              -NumStr $numStr -FaseLabel "FASE 1 - INFORME"

    switch ($res.resultado) {
        "exitoso" {
            $exitosos++
            $costo_total += $res.costo_usd
            $tokens_in   += $res.tokens_input
            $tokens_out  += $res.tokens_output
            $d = $res.detalle
            "Fase1,$($i+1),$archivo,exitoso,$($d.caso_id),$($d.documento_id),$($d.validacion.es_valido),$($d.validacion.inconsistencias),$($res.costo_usd),$($res.tokens_input),$($res.tokens_output),0,$ts," |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
        }
        "rechazado_fn" {
            $rechazados++
            $fn_total += $res.fn_count
            "Fase1,$($i+1),$archivo,rechazado_fn,,,,,,,,$($res.fn_count),$ts,FN registrados" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
        }
        default {
            $fallidos++
            $msg = if ($res.mensaje) { $res.mensaje } else { $res.resultado }
            "Fase1,$($i+1),$archivo,$($res.resultado),,,,,,,,0,$ts,$msg" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
        }
    }
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "  ✅ FASE 1 COMPLETADA" -ForegroundColor Magenta
Write-Host "     Costo acumulado: `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "========================================================`n" -ForegroundColor Magenta

# Advertencia si el informe falló — las peticiones que lo referencian fallarán también
$informe_ok = ($exitosos -gt 0)
if (-not $informe_ok) {
    Write-Host "⚠️  ADVERTENCIA: El informe CTDG-GE-2024-0148 NO se procesó correctamente." -ForegroundColor Red
    Write-Host "   PR-CCDS-2024-0129 fallará también al no encontrar su informe base." -ForegroundColor Red
    $continuar = Read-Host "`n¿Continuar de todas formas con las peticiones? (SI/NO)"
} else {
    $continuar = Read-Host "¿Continuar con FASE 2 - Peticiones Razonadas? (SI/NO)"
}

if ($continuar -ne "SI") {
    Write-Host "`n⏸️  Reprocesamiento pausado.`n" -ForegroundColor Yellow
    Read-Host "Presiona ENTER para salir"
    exit 0
}

# ----------------------------------------------
# FASE 2: PETICIONES (4 documentos)
# ----------------------------------------------
Write-Host ""
Write-Host "========================================================" -ForegroundColor Blue
Write-Host "  FASE 2: PETICIONES RAZONADAS (4 documentos)" -ForegroundColor Blue
Write-Host "========================================================`n" -ForegroundColor Blue

for ($i = 0; $i -lt $archivos_peticiones.Count; $i++) {
    $archivo = $archivos_peticiones[$i]
    $numStr  = "$($i + 1)/$total_peticiones"
    $ts      = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    $res = Procesar-Documento -Archivo $archivo -TipoDoc $TIPO_PETICION `
                              -NumStr $numStr -FaseLabel "FASE 2 - PETICIÓN"

    switch ($res.resultado) {
        "exitoso" {
            $exitosos++
            $costo_total += $res.costo_usd
            $tokens_in   += $res.tokens_input
            $tokens_out  += $res.tokens_output
            $d = $res.detalle
            "Fase2,$($i+1),$archivo,exitoso,$($d.caso_id),$($d.documento_id),$($d.validacion.es_valido),$($d.validacion.inconsistencias),$($res.costo_usd),$($res.tokens_input),$($res.tokens_output),0,$ts," |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
        }
        "rechazado_fn" {
            $rechazados++
            $fn_total += $res.fn_count
            "Fase2,$($i+1),$archivo,rechazado_fn,,,,,,,,$($res.fn_count),$ts,FN registrados" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
        }
        default {
            $fallidos++
            $msg = if ($res.mensaje) { $res.mensaje } else { $res.resultado }
            "Fase2,$($i+1),$archivo,$($res.resultado),,,,,,,,0,$ts,$msg" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
        }
    }

    if ($i -lt ($archivos_peticiones.Count - 1)) {
        Write-Host "`n⏳ Preparando siguiente documento..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
}

# ----------------------------------------------
# REPORTE FINAL
# ----------------------------------------------
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ✅ REPROCESAMIENTO COMPLETADO" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

Write-Host "📊 RESUMEN:" -ForegroundColor Cyan
Write-Host "   Total documentos        : $total_docs" -ForegroundColor White
Write-Host "   ✅ Exitosos (a Claude)   : $exitosos" -ForegroundColor Green
Write-Host "   ⚠️  Rechazados (FN reg.) : $rechazados" -ForegroundColor Yellow
Write-Host "   ❌ Errores técnicos      : $fallidos" -ForegroundColor $(if ($fallidos -eq 0) { "Green" } else { "Red" })
Write-Host "   📝 FN totales registrados: $fn_total" -ForegroundColor Yellow
Write-Host "   💰 Costo total           : `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow

Write-Host ""
Write-Host "📁 ARCHIVOS ACTUALIZADOS:" -ForegroundColor Cyan
Write-Host "   Reporte este lote : $REPORTE_PATH" -ForegroundColor White
Write-Host "   VP acumulados     : $VP_CSV_PATH" -ForegroundColor Green
Write-Host "   FN acumulados     : $FN_CSV_PATH" -ForegroundColor Green
Write-Host ""
Write-Host "▶️  SIGUIENTE PASO:" -ForegroundColor Cyan
Write-Host "   python calcular_metricas_pseudonimizacion.py" -ForegroundColor White

Write-Host ""
Read-Host "Presiona ENTER para finalizar"
