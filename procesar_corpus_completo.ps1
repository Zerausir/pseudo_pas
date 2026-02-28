# ==================================================
# PROCESAMIENTO CORPUS COMPLETO: 35 Informes + 35 Peticiones
# ARCOTEL PAS v5.0 - Re-ejecución completa
# CON CAPTURA DE MÉTRICAS VP/FN (una fila FN = una ocurrencia)
# ==================================================
# SALIDAS:
#   reporte_YYYYMMDD_HHMMSS.csv  → estado por documento
#   vp_conteos.csv               → VP por documento y tipo (AGREGA)
#   fn_anotaciones.csv           → FN por ocurrencia (AGREGA, SIN deduplicar)
#   progreso_sesion.json         → reanudación de sesión
# ==================================================
# NOTA METODOLÓGICA:
#   FN = una fila por CADA OCURRENCIA no pseudonimizada en el texto.
#   Si "JUAN" aparece 4 veces sin pseudonimizar → 4 filas en fn_anotaciones.csv
#   VP = conteo devuelto por la API (verificar que sean ocurrencias, no valores únicos)
# ==================================================

$ErrorActionPreference = "Continue"

# ----------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------
$BACKEND_URL   = "http://localhost:8000"
$REPORTE_PATH  = "./reporte_corpus_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
$PROGRESO_PATH = "./progreso_corpus_completo.json"
$VP_CSV_PATH   = "./vp_conteos.csv"
$FN_CSV_PATH   = "./fn_anotaciones.csv"

$TIPO_INFORME  = "informe_tecnico"
$TIPO_PETICION = "peticion_razonada"

# ----------------------------------------------
# CORPUS COMPLETO: 35 informes + 35 peticiones
# ----------------------------------------------
$archivos_informes = @(
    "CTDG-2024-GE-0032.pdf",
    "CTDG-2024-GE-0048.pdf",
    "CTDG-2024-GE-0051.pdf",
    "CTDG-2025-GE-0335.pdf",
    "CTDG-2025-GE-0589.pdf",
    "CTDG-2025-GE-0592.pdf",
    "CTDG-2025-GE-0607.pdf",
    "CTDG-2025-GE-0691.pdf",
    "CTDG-GE-2021-0192.pdf",
    "CTDG-GE-2021-0303.pdf",
    "CTDG-GE-2021-0307.pdf",
    "CTDG-GE-2021-0370.pdf",
    "CTDG-GE-2021-0371.pdf",
    "CTDG-GE-2022-0169.pdf",
    "CTDG-GE-2022-0299.pdf",
    "CTDG-GE-2022-0382.pdf",
    "CTDG-GE-2022-0392.pdf",
    "CTDG-GE-2022-0435.pdf",
    "CTDG-GE-2022-0449.pdf",
    "CTDG-GE-2022-0456.pdf",
    "CTDG-GE-2022-0461.pdf",
    "CTDG-GE-2022-0473.pdf",
    "CTDG-GE-2022-0480.pdf",
    "CTDG-GE-2022-0483.pdf",
    "CTDG-GE-2022-0485.pdf",
    "CTDG-GE-2022-0487.pdf",
    "CTDG-GE-2022-0488.pdf",
    "CTDG-GE-2022-0490.pdf",
    "CTDG-GE-2023-0041.pdf",
    "CTDG-GE-2023-0096.pdf",
    "CTDG-GE-2023-0197.pdf",
    "CTDG-GE-2023-0255.pdf",
    "CTDG-GE-2023-0277.pdf",
    "CTDG-GE-2023-0497.pdf",
    "CTDG-GE-2024-0148.pdf"
)

$archivos_peticiones = @(
    "CCDE-PR-2021-194.pdf",
    "CCDE-PR-2021-203.pdf",
    "CCDS-PR-2021-0283.pdf",
    "CCDS-PR-2021-0303.pdf",
    "CCDS-PR-2021-0304.pdf",
    "CCDS-PR-2022-0212.pdf",
    "CCDS-PR-2022-0377.pdf",
    "CCDS-PR-2022-0386.pdf",
    "CCDS-PR-2022-269.pdf",
    "CCDS-PR-2022-272.pdf",
    "CCDS-PR-2022-412.pdf",
    "CCDS-PR-2022-414.pdf",
    "CCDS-PR-2023-0005.pdf",
    "CCDS-PR-2023-0008.pdf",
    "CCDS-PR-2023-0011.pdf",
    "CCDS-PR-2023-0012.pdf",
    "CCDS-PR-2023-0018.pdf",
    "CCDS-PR-2023-0021.pdf",
    "CCDS-PR-2023-0022.pdf",
    "CCDS-PR-2023-0030.pdf",
    "CCDS-PR-2023-0036.pdf",
    "CCDS-PR-2023-0090.pdf",
    "CCDS-PR-2023-0156.pdf",
    "CCDS-PR-2023-0194.pdf",
    "CCDS-PR-2023-0255.pdf",
    "PR-CCDS-2024-0050.pdf",
    "PR-CCDS-2024-0129.pdf",
    "PR-CTDG-2024-GE-0032.pdf",
    "PR-CTDG-2024-GE-0048.pdf",
    "PR-CTDG-2024-GE-0051.pdf",
    "PR-CTDG-2025-GE-0335.pdf",
    "PR-CTDG-2025-GE-0589.pdf",
    "PR-CTDG-2025-GE-0592.pdf",
    "PR-CTDG-2025-GE-0607.pdf",
    "PR-CTDG-2025-GE-0691.pdf"
)

$total_informes   = $archivos_informes.Count
$total_peticiones = $archivos_peticiones.Count
$total_docs       = $total_informes + $total_peticiones

# ----------------------------------------------
# INICIALIZAR CSVs (solo crea si NO existen)
# ----------------------------------------------
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
# IMPORTANTE: una entrada = una OCURRENCIA en el texto
# Si el mismo nombre aparece 4 veces → ingresar 4 veces
# ----------------------------------------------
function Capturar-FN {
    param(
        [string]$Archivo,
        [string]$TipoDoc
    )

    $fn_lista = @()

    Write-Host ""
    Write-Host "┌──────────────────────────────────────────────────────────┐" -ForegroundColor Red
    Write-Host "│  📝 REGISTRO DE DATOS NO PSEUDONIMIZADOS (FN)            │" -ForegroundColor Red
    Write-Host "│  Registra cada valor único UNA SOLA VEZ                  │" -ForegroundColor Red
    Write-Host "│  Si 'JUAN PEREZ' aparece N veces sin pseudonimizar       │" -ForegroundColor Red
    Write-Host "│  → ingrésalo UNA vez (no importa cuántas veces aparezca) │" -ForegroundColor Red
    Write-Host "└──────────────────────────────────────────────────────────┘" -ForegroundColor Red

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
        $valor = Read-Host "  Dato expuesto (texto exacto de esta ocurrencia)"
        if ([string]::IsNullOrWhiteSpace($valor)) {
            Write-Host "  ⚠️  Valor vacío. Intenta de nuevo." -ForegroundColor Yellow
            continue
        }

        Write-Host "  Tipo de entidad:"
        Write-Host "    1) NOMBRE    2) EMAIL    3) TELEFONO"
        Write-Host "    4) DIRECCION 5) RUC      6) CEDULA"
        $tipo_opt = Read-Host "  Opción (1-6)"
        $tipo_map = @{"1"="NOMBRE";"2"="EMAIL";"3"="TELEFONO";"4"="DIRECCION";"5"="RUC";"6"="CEDULA"}
        $tipo_entidad = $tipo_map[$tipo_opt]
        if (-not $tipo_entidad) {
            Write-Host "  ⚠️  Opción inválida. Usando NOMBRE por defecto." -ForegroundColor Yellow
            $tipo_entidad = "NOMBRE"
        }

        $capa = $TIPO_A_CAPA[$tipo_entidad]
        Write-Host "  🔍 Capa: $capa" -ForegroundColor Gray

        $fn_lista += [PSCustomObject]@{
            documento     = $Archivo -replace '\.pdf$', ''
            tipo_doc      = $TipoDoc
            entidad_valor = $valor
            tipo_entidad  = $tipo_entidad
            capa          = $capa
            resultado     = "FN"
        }

        Write-Host "  ✅ Valor único registrado: '$valor' ($tipo_entidad)" -ForegroundColor Green
        Write-Host "  Total valores únicos FN para este doc: $($fn_lista.Count)" -ForegroundColor Gray

        $otro = Read-Host "  ¿Hay otra ocurrencia sin pseudonimizar? (SI/NO)"
        $continuar = ($otro.Trim().ToUpper() -eq "SI")
    }

    foreach ($fn in $fn_lista) {
        # Escapar comas en el valor para no romper el CSV
        $valor_csv = $fn.entidad_valor -replace '"', '""'
        if ($valor_csv -match ',') { $valor_csv = "`"$valor_csv`"" }
        "$($fn.documento),$($fn.tipo_doc),$valor_csv,$($fn.tipo_entidad),$($fn.capa),$($fn.resultado)" |
            Out-File -FilePath $FN_CSV_PATH -Append -Encoding UTF8
    }

    Write-Host "  💾 $($fn_lista.Count) FN guardados en $FN_CSV_PATH" -ForegroundColor Cyan
    return $fn_lista.Count
}

# ----------------------------------------------
# FUNCIÓN: Guardar VP
# ----------------------------------------------
function Guardar-VP {
    param(
        [string]$Archivo,
        [string]$TipoDoc,
        [object]$PseudonimosPorTipo
    )

    $doc_id   = $Archivo -replace '\.pdf$', ''
    $tipo     = if ($TipoDoc -eq "informe_tecnico") { "informe" } else { "peticion" }
    $ts       = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    $ruc      = if ($PseudonimosPorTipo.PSObject.Properties["RUC"])       { $PseudonimosPorTipo.RUC }       else { 0 }
    $cedula   = if ($PseudonimosPorTipo.PSObject.Properties["CEDULA"])    { $PseudonimosPorTipo.CEDULA }    else { 0 }
    $email    = if ($PseudonimosPorTipo.PSObject.Properties["EMAIL"])     { $PseudonimosPorTipo.EMAIL }     else { 0 }
    $telefono = if ($PseudonimosPorTipo.PSObject.Properties["TELEFONO"])  { $PseudonimosPorTipo.TELEFONO }  else { 0 }
    $dir      = if ($PseudonimosPorTipo.PSObject.Properties["DIRECCION"]) { $PseudonimosPorTipo.DIRECCION } else { 0 }
    $nombre   = if ($PseudonimosPorTipo.PSObject.Properties["NOMBRE"])    { $PseudonimosPorTipo.NOMBRE }    else { 0 }
    $total    = $ruc + $cedula + $email + $telefono + $dir + $nombre

    "$doc_id,$tipo,$ruc,$cedula,$email,$telefono,$dir,$nombre,$total,$ts" |
        Out-File -FilePath $VP_CSV_PATH -Append -Encoding UTF8

    Write-Host "   💾 VP: RUC=$ruc CED=$cedula EMAIL=$email TEL=$telefono DIR=$dir NOM=$nombre (Total=$total)" -ForegroundColor Gray
}

# ----------------------------------------------
# FUNCIÓN PRINCIPAL: Procesar un documento
# ----------------------------------------------
function Procesar-Documento {
    param(
        [string]$Archivo,
        [string]$TipoDoc,
        [string]$NumStr,
        [string]$FaseLabel,
        [int]$ExitososRef,
        [int]$FallidosRef,
        [int]$SaltadosRef,
        [hashtable]$ProcesadosPrevios
    )

    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  $FaseLabel  |  $NumStr" -ForegroundColor Cyan
    Write-Host "  ✅ $ExitososRef  ❌ $FallidosRef  ⏭️  $SaltadosRef" -ForegroundColor Cyan
    Write-Host "  📄 $Archivo" -ForegroundColor White
    Write-Host "========================================================`n" -ForegroundColor Cyan

    if ($ProcesadosPrevios.ContainsKey($Archivo) -and
        $ProcesadosPrevios[$Archivo] -ne "saltado") {
        Write-Host "⏭️  Ya procesado. Saltando...`n" -ForegroundColor Gray
        return @{ resultado = "ya_procesado"; session_id = $null }
    }

    # PASO 1: Previsualización
    Write-Host "🔍 Generando previsualización..." -ForegroundColor Yellow
    $previoBody = @{
        archivo        = $Archivo
        tipo_documento = $TipoDoc
    } | ConvertTo-Json

    try {
        $validacion = Invoke-RestMethod `
            -Uri "$BACKEND_URL/api/validacion/previsualizar" `
            -Method POST -ContentType "application/json" -Body $previoBody

        $desglose = $validacion.pseudonyms_by_type.PSObject.Properties |
            ForEach-Object { "$($_.Name):$($_.Value)" }
        Write-Host "✅ Pseudónimos generados: $($validacion.pseudonyms_count) ($($desglose -join ', '))" -ForegroundColor Green

        $session_id = $validacion.session_id
        $html_file  = $validacion.html_filename

        # Guardar VP (ocurrencias pseudonimizadas)
        Guardar-VP -Archivo $Archivo -TipoDoc $TipoDoc `
                   -PseudonimosPorTipo $validacion.pseudonyms_by_type

    } catch {
        Write-Host "❌ Error en previsualización: $($_.Exception.Message)" -ForegroundColor Red
        return @{ resultado = "error_previo"; session_id = $null }
    }

    # PASO 2: Abrir HTML
    Write-Host "`n🌐 Abriendo en navegador..." -ForegroundColor Yellow
    try {
        $html_local = "./$html_file"
        Invoke-WebRequest -Uri "$BACKEND_URL/outputs/$html_file" -OutFile $html_local
        Start-Process $html_local
        Start-Sleep -Seconds 2
    } catch {
        Write-Host "⚠️  No se pudo abrir. URL manual: $BACKEND_URL/outputs/$html_file" -ForegroundColor Yellow
    }

    # PASO 3: Validación
    Write-Host ""
    Write-Host "┌──────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│  ⚠️  VALIDACIÓN LOPDP                               │" -ForegroundColor Yellow
    Write-Host "│  Verifica que NO aparezca ningún dato personal real  │" -ForegroundColor Yellow
    Write-Host "└──────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host "  OK     → Pseudonimización completa" -ForegroundColor Green
    Write-Host "  MAL    → Hay ocurrencias expuestas (registrar FN)" -ForegroundColor Red
    Write-Host "  SALTAR → Omitir" -ForegroundColor Gray
    Write-Host ""

    $confirmacion = Read-Host "[$NumStr] ¿Resultado? (OK / MAL / SALTAR)"
    $confirmacion = $confirmacion.Trim().ToUpper()

    if ($confirmacion -eq "SALTAR") {
        Write-Host "⏭️  Saltado.`n" -ForegroundColor Gray
        return @{ resultado = "saltado"; session_id = $null }
    }

    if ($confirmacion -eq "MAL") {
        $tipo_corto     = if ($TipoDoc -eq "informe_tecnico") { "informe" } else { "peticion" }
        $archivo_sin_pdf = $Archivo -replace '\.pdf$', ''
        $fn_count = Capturar-FN -Archivo $archivo_sin_pdf -TipoDoc $tipo_corto
        Write-Host "`n⏭️  Documento NO enviado a Claude API. $fn_count FN registrados.`n" -ForegroundColor Yellow
        return @{ resultado = "rechazado_fn"; fn_count = $fn_count; session_id = $null }
    }

    if ($confirmacion -ne "OK") {
        Write-Host "❌ Respuesta no reconocida. Saltando.`n" -ForegroundColor Red
        return @{ resultado = "saltado"; session_id = $null }
    }

    # PASO 4: Procesar con Claude API
    Write-Host "`n🚀 Enviando a Claude API..." -ForegroundColor Yellow
    $procesoBody = @{
        archivos   = @($Archivo)
        session_id = $session_id
        confirmado = $true
    } | ConvertTo-Json

    try {
        $resultado = Invoke-RestMethod `
            -Uri "$BACKEND_URL/api/archivos/procesar" `
            -Method POST -ContentType "application/json" `
            -Body $procesoBody -TimeoutSec 180

        $detalle = $resultado.detalles[0]

        if ($detalle.estado -eq "exitoso") {
            $validIcon = if ($detalle.validacion.es_valido) { "✅ Válido" } else { "⚠️  Con advertencias" }
            Write-Host "✅ Procesado: Caso=$($detalle.caso_id) | $validIcon" -ForegroundColor Green
            Write-Host "   Costo: `$$($resultado.costo_total_usd) | Tokens: $($resultado.tokens_total)" -ForegroundColor White
            return @{
                resultado     = "exitoso"
                detalle       = $detalle
                costo_usd     = [double]$resultado.costo_total_usd
                tokens        = [int]$resultado.tokens_total
                tokens_input  = [int]$resultado.tokens_total_input
                tokens_output = [int]$resultado.tokens_total_output
                session_id    = $session_id
            }
        } else {
            Write-Host "❌ Error: $($detalle.mensaje)" -ForegroundColor Red
            return @{ resultado = $detalle.estado; mensaje = $detalle.mensaje; session_id = $null }
        }
    } catch {
        Write-Host "❌ Error HTTP: $($_.Exception.Message)" -ForegroundColor Red
        return @{ resultado = "error_http"; mensaje = $_.Exception.Message; session_id = $null }
    }
}

# ----------------------------------------------
# FUNCIÓN: Registrar en reporte y progreso
# ----------------------------------------------
function Registrar-Resultado {
    param($Fase, $Idx, $Archivo, $Res, $TsStr)
    switch ($Res.resultado) {
        "exitoso" {
            $script:exitosos++
            $script:costo_total += $Res.costo_usd
            $script:tokens_in   += $Res.tokens_input
            $script:tokens_out  += $Res.tokens_output
            $d = $Res.detalle
            "$Fase,$Idx,$Archivo,exitoso,$($d.caso_id),$($d.validacion.es_valido),$($d.validacion.inconsistencias),$($Res.costo_usd),$($Res.tokens_input),$($Res.tokens_output),0,$TsStr," |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "exitoso" }
        }
        "ya_procesado" {
            $script:saltados++
            "$Fase,$Idx,$Archivo,ya_procesado,,,,,,0,$TsStr,Sesion anterior" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "exitoso" }
        }
        "saltado" {
            $script:saltados++
            "$Fase,$Idx,$Archivo,saltado,,,,,,0,$TsStr,Saltado" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "saltado" }
        }
        "rechazado_fn" {
            $script:rechazados++
            $script:fn_total += $Res.fn_count
            "$Fase,$Idx,$Archivo,rechazado_fn,,,,,,$($Res.fn_count),$TsStr,FN registrados" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "rechazado_fn" }
        }
        default {
            $script:fallidos++
            "$Fase,$Idx,$Archivo,$($Res.resultado),,,,,,0,$TsStr,$($Res.mensaje)" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "error" }
        }
    }
}

# ----------------------------------------------
# INICIO
# ----------------------------------------------
Clear-Host
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  ARCOTEL PAS v5.0 — RE-EJECUCIÓN CORPUS COMPLETO" -ForegroundColor Cyan
Write-Host "  $total_informes Informes Técnicos + $total_peticiones Peticiones Razonadas" -ForegroundColor Cyan
Write-Host "  Total: $total_docs documentos" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

# Verificar backend
Write-Host "📡 Verificando backend..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$BACKEND_URL/health" -TimeoutSec 5
    Write-Host "✅ Backend UP — Version: $($health.version)`n" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend NO responde. Ejecuta: docker compose up -d`n" -ForegroundColor Red
    Read-Host "Presiona ENTER para salir"
    exit 1
}

# Sesión previa
$procesados_previos = @{}
if (Test-Path $PROGRESO_PATH) {
    Write-Host "⚠️  Se encontró sesión previa." -ForegroundColor Yellow
    $reanudar = Read-Host "¿Reanudar desde donde quedaste? (SI/NO)"
    if ($reanudar.Trim().ToUpper() -eq "SI") {
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

# Inicializar reporte
"Fase,Numero,Archivo,Estado,CasoID,EsValido,Inconsistencias,CostoUSD,TokensInput,TokensOutput,FN_Count,Timestamp,Mensaje" |
    Out-File -FilePath $REPORTE_PATH -Encoding UTF8

# Contadores
$exitosos    = 0
$fallidos    = 0
$saltados    = 0
$rechazados  = 0
$fn_total    = 0
$costo_total = 0.0
$tokens_in   = 0
$tokens_out  = 0
$progreso    = @()

# ----------------------------------------------
# FASE 1: INFORMES TÉCNICOS
# ----------------------------------------------
Write-Host ""
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "  FASE 1: INFORMES TÉCNICOS ($total_informes documentos)" -ForegroundColor Magenta
Write-Host "========================================================`n" -ForegroundColor Magenta

for ($i = 0; $i -lt $archivos_informes.Count; $i++) {
    $archivo = $archivos_informes[$i]
    $numStr  = "$($i + 1)/$total_informes"

    $res = Procesar-Documento `
        -Archivo $archivo -TipoDoc $TIPO_INFORME -NumStr $numStr `
        -FaseLabel "FASE 1 - INFORME" `
        -ExitososRef $exitosos -FallidosRef $fallidos -SaltadosRef $saltados `
        -ProcesadosPrevios $procesados_previos

    $ts    = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $entry = Registrar-Resultado "Fase1" ($i + 1) $archivo $res $ts
    $progreso += $entry
    $progreso | ConvertTo-Json | Out-File -FilePath $PROGRESO_PATH -Encoding UTF8

    if ($i -lt ($archivos_informes.Count - 1)) {
        Start-Sleep -Seconds 1
    }
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "  FASE 1 COMPLETADA" -ForegroundColor Magenta
Write-Host "  Exitosos: $exitosos | Rechazados: $rechazados | Saltados: $saltados | FN: $fn_total" -ForegroundColor White
Write-Host "  Costo: `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "========================================================`n" -ForegroundColor Magenta

$continuar = Read-Host "¿Continuar con FASE 2 - Peticiones Razonadas? (SI/NO)"
if ($continuar.Trim().ToUpper() -ne "SI") {
    Write-Host "`n⏸️  Pausado. Progreso en $PROGRESO_PATH`n" -ForegroundColor Yellow
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

for ($i = 0; $i -lt $archivos_peticiones.Count; $i++) {
    $archivo = $archivos_peticiones[$i]
    $numStr  = "$($i + 1)/$total_peticiones"

    $res = Procesar-Documento `
        -Archivo $archivo -TipoDoc $TIPO_PETICION -NumStr $numStr `
        -FaseLabel "FASE 2 - PETICIÓN" `
        -ExitososRef $exitosos -FallidosRef $fallidos -SaltadosRef $saltados `
        -ProcesadosPrevios $procesados_previos

    $ts    = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $entry = Registrar-Resultado "Fase2" ($i + 1) $archivo $res $ts
    $progreso += $entry
    $progreso | ConvertTo-Json | Out-File -FilePath $PROGRESO_PATH -Encoding UTF8

    if ($i -lt ($archivos_peticiones.Count - 1)) {
        Start-Sleep -Seconds 1
    }
}

# ----------------------------------------------
# REPORTE FINAL
# ----------------------------------------------
Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  RE-EJECUCIÓN CORPUS COMPLETO — FINALIZADO" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan
Write-Host "  Total documentos         : $total_docs" -ForegroundColor White
Write-Host "  ✅ Exitosos (a Claude)    : $exitosos" -ForegroundColor Green
Write-Host "  ⚠️  Rechazados (con FN)  : $rechazados" -ForegroundColor Yellow
Write-Host "  ❌ Errores técnicos       : $fallidos" -ForegroundColor Red
Write-Host "  ⏭️  Saltados               : $saltados" -ForegroundColor Gray
Write-Host "  📝 FN totales registrados : $fn_total" -ForegroundColor Yellow
Write-Host "  💰 Costo total            : `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "  🔢 Tokens input           : $($tokens_in.ToString('N0'))" -ForegroundColor White
Write-Host "  🔢 Tokens output          : $($tokens_out.ToString('N0'))" -ForegroundColor White
Write-Host ""
Write-Host "  Reporte  : $REPORTE_PATH" -ForegroundColor White
Write-Host "  VP CSV   : $VP_CSV_PATH" -ForegroundColor Green
Write-Host "  FN CSV   : $FN_CSV_PATH" -ForegroundColor Green
Write-Host ""
Write-Host "▶️  SIGUIENTE PASO:" -ForegroundColor Cyan
Write-Host "   python calcular_metricas_pseudonimizacion.py" -ForegroundColor White

if ($saltados -eq 0 -and ($exitosos + $fallidos + $rechazados) -eq $total_docs) {
    Remove-Item $PROGRESO_PATH -ErrorAction SilentlyContinue
    Write-Host "`n✅ Sesión completa — progreso eliminado" -ForegroundColor Green
}

Write-Host ""
Read-Host "Presiona ENTER para finalizar"
