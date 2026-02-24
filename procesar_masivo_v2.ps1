# ==================================================
# PROCESAMIENTO MASIVO: 22 Informes + 22 Peticiones
# ARCOTEL PAS v4.0 - Validación Individual LOPDP
# CON CAPTURA AUTOMÁTICA DE MÉTRICAS (VP + FN)
# ==================================================
# SALIDAS GENERADAS:
#   reporte_YYYYMMDD_HHMMSS.csv   → estado de procesamiento por documento
#   vp_conteos.csv                → VP por documento y tipo (para métricas)
#   fn_anotaciones.csv            → FN con capa (para métricas)
#   progreso_sesion.json          → reanudación de sesión
# ==================================================

$ErrorActionPreference = "Continue"

# ----------------------------------------------
# CONFIGURACIÓN
# ----------------------------------------------
$BACKEND_URL    = "http://localhost:8000"
$REPORTE_PATH   = "./reporte_$(Get-Date -Format 'yyyyMMdd_HHmmss').csv"
$PROGRESO_PATH  = "./progreso_sesion.json"
$VP_CSV_PATH    = "./vp_conteos.csv"
$FN_CSV_PATH    = "./fn_anotaciones.csv"

$DIR_INFORMES   = "informes_tecnicos"
$DIR_PETICIONES = "peticiones_razonadas"
$TIPO_INFORME   = "informe_tecnico"
$TIPO_PETICION  = "peticion_razonada"


$TIPOS_ENTIDAD_VALIDOS = @("NOMBRE", "EMAIL", "TELEFONO", "DIRECCION", "RUC", "CEDULA")

# ----------------------------------------------
# INICIALIZAR CSVs DE MÉTRICAS
# (solo si no existen para permitir reanudar)
# ----------------------------------------------
if (-not (Test-Path $VP_CSV_PATH)) {
    "documento,tipo_doc,RUC,CEDULA,EMAIL,TELEFONO,DIRECCION,NOMBRE,total_vp,timestamp" |
        Out-File -FilePath $VP_CSV_PATH -Encoding UTF8
    Write-Host "📊 Creado: $VP_CSV_PATH" -ForegroundColor Cyan
}

if (-not (Test-Path $FN_CSV_PATH)) {
    "documento,tipo_doc,entidad_valor,tipo_entidad,capa,resultado" |
        Out-File -FilePath $FN_CSV_PATH -Encoding UTF8
    Write-Host "📊 Creado: $FN_CSV_PATH" -ForegroundColor Cyan
}

# ----------------------------------------------
# FUNCIÓN: Capturar FN interactivamente
# Se llama cuando el usuario dice MAL en la validación
# ----------------------------------------------
function Capturar-FN {
    param(
        [string]$Archivo,
        [string]$TipoDoc
    )

    $fn_lista = @()

    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────┐" -ForegroundColor Red
    Write-Host "│  📝 REGISTRO DE DATOS NO PSEUDONIMIZADOS (FN)       │" -ForegroundColor Red
    Write-Host "│  Ingresa CADA dato que quedó expuesto               │" -ForegroundColor Red
    Write-Host "└─────────────────────────────────────────────────────┘" -ForegroundColor Red

    # Mapa tipo → capa responsable (determinístico, no se pregunta al usuario)
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
        $tipo_opt = Read-Host "  Opción (1-6)"
        $tipo_map = @{"1"="NOMBRE";"2"="EMAIL";"3"="TELEFONO";"4"="DIRECCION";"5"="RUC";"6"="CEDULA"}
        $tipo_entidad = $tipo_map[$tipo_opt]
        if (-not $tipo_entidad) {
            Write-Host "  ⚠️  Opción inválida. Usando NOMBRE por defecto." -ForegroundColor Yellow
            $tipo_entidad = "NOMBRE"
        }

        # Capa inferida automáticamente del tipo — sin preguntar al usuario
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

        $otro = Read-Host "  ¿Hay otro dato no pseudonimizado? (SI/NO)"
        $continuar = ($otro -eq "SI")
    }

    # Guardar en CSV
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
    param(
        [string]$Archivo,
        [string]$TipoDoc,
        [object]$PseudonimosPorTipo
    )

    $doc_id  = $Archivo -replace '\.pdf$', ''
    $tipo    = if ($TipoDoc -eq "informe_tecnico") { "informe" } else { "peticion" }
    $ts      = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    # Extraer conteos por tipo (0 si no existe)
    $ruc      = if ($PseudonimosPorTipo.PSObject.Properties["RUC"])      { $PseudonimosPorTipo.RUC }      else { 0 }
    $cedula   = if ($PseudonimosPorTipo.PSObject.Properties["CEDULA"])   { $PseudonimosPorTipo.CEDULA }   else { 0 }
    $email    = if ($PseudonimosPorTipo.PSObject.Properties["EMAIL"])    { $PseudonimosPorTipo.EMAIL }    else { 0 }
    $telefono = if ($PseudonimosPorTipo.PSObject.Properties["TELEFONO"]) { $PseudonimosPorTipo.TELEFONO } else { 0 }
    $dir      = if ($PseudonimosPorTipo.PSObject.Properties["DIRECCION"]){ $PseudonimosPorTipo.DIRECCION }else { 0 }
    $nombre   = if ($PseudonimosPorTipo.PSObject.Properties["NOMBRE"])   { $PseudonimosPorTipo.NOMBRE }   else { 0 }
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
        [string]$FaseLabel,
        [int]$ExitososRef,
        [int]$FallidosRef,
        [int]$SaltadosRef,
        [hashtable]$ProcesadosPrevios
    )

    $num   = $NumStr.Split('/')[0]
    $total = $NumStr.Split('/')[1]

    Write-Host ""
    Write-Host "========================================================" -ForegroundColor Cyan
    Write-Host "  $FaseLabel  |  $num / $total" -ForegroundColor Cyan
    Write-Host "  ✅ $ExitososRef  ❌ $FallidosRef  ⏭️  $SaltadosRef" -ForegroundColor Cyan
    Write-Host "  📄 $Archivo" -ForegroundColor White
    Write-Host "========================================================`n" -ForegroundColor Cyan

    # Verificar sesión previa
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

        # ── GUARDAR VP INMEDIATAMENTE ──────────────────────────────
        Guardar-VP -Archivo $Archivo `
                   -TipoDoc $TipoDoc `
                   -PseudonimosPorTipo $validacion.pseudonyms_by_type

    } catch {
        Write-Host "❌ Error en previsualización: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message -ForegroundColor Red }
        return @{ resultado = "error_previo"; session_id = $null }
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

    # ── PASO 3: Validación con captura de FN ─────────────────────
    Write-Host ""
    Write-Host "┌─────────────────────────────────────────────────────┐" -ForegroundColor Yellow
    Write-Host "│  ⚠️  VALIDACIÓN OBLIGATORIA - LOPDP Arts. 8, 10.e  │" -ForegroundColor Yellow
    Write-Host "│  Verifica que NO aparezca ningún dato personal real │" -ForegroundColor Yellow
    Write-Host "│  NOMBRE_XX · CEDULA_XX · EMAIL_XX · DIRECCION_XX   │" -ForegroundColor Yellow
    Write-Host "└─────────────────────────────────────────────────────┘" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  OK     → Pseudonimización completa, procesar con Claude" -ForegroundColor Green
    Write-Host "  MAL    → Hay datos expuestos, registrar FN y saltar" -ForegroundColor Red
    Write-Host "  SALTAR → Omitir sin registrar" -ForegroundColor Gray
    Write-Host ""

    $confirmacion = Read-Host "[$NumStr] ¿Resultado de validación? (OK / MAL / SALTAR)"

    if ($confirmacion -eq "SALTAR") {
        Write-Host "⏭️  Saltado manualmente.`n" -ForegroundColor Gray
        return @{ resultado = "saltado"; session_id = $null }
    }

    if ($confirmacion -eq "MAL") {
        # Capturar FN de forma guiada
        $tipo_doc_corto = if ($TipoDoc -eq "informe_tecnico") { "informe" } else { "peticion" }
        $archivo_sin_pdf = $Archivo -replace '\.pdf$', ''
        $fn_count = Capturar-FN -Archivo $archivo_sin_pdf -TipoDoc $tipo_doc_corto
        Write-Host ""
        Write-Host "⏭️  Documento NO enviado a Claude API (LOPDP: pseudonimización incompleta)." -ForegroundColor Yellow
        Write-Host "   $fn_count FN registrados para métricas.`n" -ForegroundColor Yellow
        return @{ resultado = "rechazado_fn"; fn_count = $fn_count; session_id = $null }
    }

    if ($confirmacion -ne "OK") {
        Write-Host "❌ Respuesta no reconocida. Documento saltado.`n" -ForegroundColor Red
        return @{ resultado = "saltado"; session_id = $null }
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
                tokens        = [int]$resultado.tokens_total
                tokens_input  = [int]$resultado.tokens_total_input
                tokens_output = [int]$resultado.tokens_total_output
                session_id    = $session_id
            }
        } else {
            $msg = if ($detalle.mensaje) { $detalle.mensaje } else { "Error desconocido" }
            Write-Host "❌ Error procesamiento: $msg" -ForegroundColor Red
            return @{ resultado = $detalle.estado; mensaje = $msg; session_id = $null }
        }

    } catch {
        $err = $_.Exception.Message
        Write-Host "❌ Error HTTP: $err" -ForegroundColor Red
        if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message -ForegroundColor Red }
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
Write-Host "  Con captura de métricas VP/FN por documento" -ForegroundColor Cyan
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

# Leer archivos
$archivos_informes   = Get-ChildItem ".\data\$DIR_INFORMES\*.pdf" |
    Select-Object -ExpandProperty Name | Sort-Object
$archivos_peticiones = Get-ChildItem ".\data\$DIR_PETICIONES\*.pdf" |
    Select-Object -ExpandProperty Name | Sort-Object

$total_informes   = $archivos_informes.Count
$total_peticiones = $archivos_peticiones.Count
$total_docs       = $total_informes + $total_peticiones

Write-Host "📂 Archivos detectados:" -ForegroundColor Cyan
Write-Host "   Informes técnicos   : $total_informes" -ForegroundColor White
Write-Host "   Peticiones razonadas: $total_peticiones" -ForegroundColor White
Write-Host "   Total               : $total_docs documentos`n" -ForegroundColor White

if ($total_informes -eq 0 -or $total_peticiones -eq 0) {
    Write-Host "❌ No se encontraron archivos." -ForegroundColor Red
    Read-Host "Presiona ENTER para salir"
    exit 1
}

# Sesión previa
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

# Inicializar CSV de reporte
"Fase,Numero,Archivo,Estado,CasoID,DocumentoID,EsValido,Inconsistencias,CostoUSD,TokensInput,TokensOutput,FN_Count,Timestamp,Mensaje" |
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
# FUNCIÓN: Registrar resultado en CSV y progreso
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
            "$Fase,$Idx,$Archivo,exitoso,$($d.caso_id),$($d.documento_id),$($d.validacion.es_valido),$($d.validacion.inconsistencias),$($Res.costo_usd),$($Res.tokens_input),$($Res.tokens_output),0,$TsStr," |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "exitoso" }
        }
        "ya_procesado" {
            $script:saltados++
            "$Fase,$Idx,$Archivo,ya_procesado,,,,,,,, 0,$TsStr,Sesion anterior" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "exitoso" }
        }
        "saltado" {
            $script:saltados++
            "$Fase,$Idx,$Archivo,saltado,,,,,,,,0,$TsStr,Saltado manualmente" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "saltado" }
        }
        "rechazado_fn" {
            $script:rechazados++
            $script:fn_total += $Res.fn_count
            "$Fase,$Idx,$Archivo,rechazado_fn,,,,,,,,$($Res.fn_count),$TsStr,FN registrados" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "rechazado_fn" }
        }
        default {
            $script:fallidos++
            $msg = if ($Res.mensaje) { $Res.mensaje } else { $Res.resultado }
            "$Fase,$Idx,$Archivo,$($Res.resultado),,,,,,,,0,$TsStr,$msg" |
                Out-File -FilePath $REPORTE_PATH -Append -Encoding UTF8
            return [PSCustomObject]@{ archivo = $Archivo; estado = "error" }
        }
    }
}

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

    $ts     = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $entry  = Registrar-Resultado "Fase1" ($i+1) $archivo $res $ts
    $progreso += $entry
    $progreso | ConvertTo-Json | Out-File -FilePath $PROGRESO_PATH -Encoding UTF8

    if ($i -lt ($archivos_informes.Count - 1)) {
        Write-Host "`n⏳ Preparando siguiente documento..." -ForegroundColor Gray
        Start-Sleep -Seconds 1
    }
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Magenta
Write-Host "  ✅ FASE 1 COMPLETADA" -ForegroundColor Magenta
Write-Host "     Exitosos: $exitosos | Rechazados (FN): $rechazados | Saltados: $saltados" -ForegroundColor White
Write-Host "     FN totales registrados: $fn_total" -ForegroundColor Yellow
Write-Host "     Costo acumulado: `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "========================================================`n" -ForegroundColor Magenta

$continuar = Read-Host "¿Continuar con FASE 2 - Peticiones Razonadas? (SI/NO)"
if ($continuar -ne "SI") {
    Write-Host "`n⏸️  Sesión pausada. Progreso guardado en $PROGRESO_PATH`n" -ForegroundColor Yellow
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

$exitosos_f2   = 0
$rechazados_f2 = 0

for ($i = 0; $i -lt $archivos_peticiones.Count; $i++) {
    $archivo = $archivos_peticiones[$i]
    $numStr  = "$($i + 1)/$total_peticiones"

    $res = Procesar-Documento `
        -Archivo $archivo -TipoDoc $TIPO_PETICION -NumStr $numStr `
        -FaseLabel "FASE 2 - PETICIÓN" `
        -ExitososRef ($exitosos - ($total_informes - $rechazados - $saltados)) `
        -FallidosRef $fallidos -SaltadosRef $saltados `
        -ProcesadosPrevios $procesados_previos

    $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    if ($res.resultado -eq "exitoso")      { $exitosos_f2++ }
    if ($res.resultado -eq "rechazado_fn") { $rechazados_f2++ }

    $entry  = Registrar-Resultado "Fase2" ($i+1) $archivo $res $ts
    $progreso += $entry
    $progreso | ConvertTo-Json | Out-File -FilePath $PROGRESO_PATH -Encoding UTF8

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
Write-Host "  ✅ PROCESAMIENTO COMPLETO" -ForegroundColor Cyan
Write-Host "========================================================`n" -ForegroundColor Cyan

$total_procesados = $exitosos + $fallidos + $rechazados
$tasa = if ($total_procesados -gt 0) {
    [Math]::Round(($exitosos / $total_docs) * 100, 1)
} else { 0 }

Write-Host "📊 RESUMEN GLOBAL:" -ForegroundColor Cyan
Write-Host "   Total documentos        : $total_docs" -ForegroundColor White
Write-Host "   ✅ Exitosos (a Claude)   : $exitosos" -ForegroundColor Green
Write-Host "   ⚠️  Rechazados (FN reg.) : $rechazados" -ForegroundColor Yellow
Write-Host "   ❌ Errores técnicos      : $fallidos" -ForegroundColor Red
Write-Host "   ⏭️  Saltados              : $saltados" -ForegroundColor Gray
Write-Host "   📝 FN totales registrados: $fn_total" -ForegroundColor Yellow
Write-Host "   💰 Costo total           : `$$([Math]::Round($costo_total, 4)) USD" -ForegroundColor Yellow
Write-Host "   🔢 Tokens input          : $($tokens_in.ToString('N0'))" -ForegroundColor White
Write-Host "   🔢 Tokens output         : $($tokens_out.ToString('N0'))" -ForegroundColor White

Write-Host ""
Write-Host "📁 ARCHIVOS GENERADOS:" -ForegroundColor Cyan
Write-Host "   Reporte procesamiento : $REPORTE_PATH" -ForegroundColor White
Write-Host "   VP por documento      : $VP_CSV_PATH" -ForegroundColor Green
Write-Host "   FN anotaciones        : $FN_CSV_PATH" -ForegroundColor Green
Write-Host ""
Write-Host "▶️  SIGUIENTE PASO:" -ForegroundColor Cyan
Write-Host "   python calcular_metricas_pseudonimizacion.py" -ForegroundColor White
Write-Host "   (Lee $VP_CSV_PATH y $FN_CSV_PATH automáticamente)" -ForegroundColor Gray

if ($saltados -eq 0 -and ($exitosos + $fallidos + $rechazados) -eq $total_docs) {
    Remove-Item $PROGRESO_PATH -ErrorAction SilentlyContinue
    Write-Host "`n✅ Sesión completada — progreso eliminado" -ForegroundColor Green
}

Write-Host ""
Read-Host "Presiona ENTER para finalizar"