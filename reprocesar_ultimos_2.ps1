# ==================================================
# REPROCESAMIENTO FINAL: 2 documentos restantes
# CTDG-2025-GE-0607 (informe) + PR-CTDG-2025-GE-0607 (petición)
# ==================================================

$ErrorActionPreference = "Continue"
$BACKEND_URL = "http://localhost:8000"
$VP_CSV_PATH = "./vp_conteos.csv"
$FN_CSV_PATH = "./fn_anotaciones.csv"

function Procesar-Uno {
    param([string]$Archivo, [string]$TipoDoc, [string]$Label)

    Write-Host "`n========================================================" -ForegroundColor Cyan
    Write-Host "  $Label" -ForegroundColor Cyan
    Write-Host "  📄 $Archivo" -ForegroundColor White
    Write-Host "========================================================`n" -ForegroundColor Cyan

    # Previsualización
    Write-Host "🔍 Pseudonimizando..." -ForegroundColor Yellow
    try {
        $prev = Invoke-RestMethod -Uri "$BACKEND_URL/api/validacion/previsualizar" `
            -Method POST -ContentType "application/json" `
            -Body (@{ archivo = $Archivo; tipo_documento = $TipoDoc } | ConvertTo-Json)

        Write-Host "✅ Pseudónimos: $($prev.pseudonyms_count)" -ForegroundColor Green
        $desglose = $prev.pseudonyms_by_type.PSObject.Properties | ForEach-Object { "$($_.Name):$($_.Value)" }
        Write-Host "   ($($desglose -join ', '))" -ForegroundColor Gray

        # Guardar VP
        $doc_id = $Archivo -replace '\.pdf$', ''
        $tipo   = if ($TipoDoc -eq "informe_tecnico") { "informe" } else { "peticion" }
        $p      = $prev.pseudonyms_by_type
        $ruc    = if ($p.PSObject.Properties["RUC"])       { $p.RUC }       else { 0 }
        $ced    = if ($p.PSObject.Properties["CEDULA"])    { $p.CEDULA }    else { 0 }
        $eml    = if ($p.PSObject.Properties["EMAIL"])     { $p.EMAIL }     else { 0 }
        $tel    = if ($p.PSObject.Properties["TELEFONO"])  { $p.TELEFONO }  else { 0 }
        $dir    = if ($p.PSObject.Properties["DIRECCION"]) { $p.DIRECCION } else { 0 }
        $nom    = if ($p.PSObject.Properties["NOMBRE"])    { $p.NOMBRE }    else { 0 }
        "$doc_id,$tipo,$ruc,$ced,$eml,$tel,$dir,$nom,$($ruc+$ced+$eml+$tel+$dir+$nom),$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" |
            Out-File -FilePath $VP_CSV_PATH -Append -Encoding UTF8

    } catch {
        Write-Host "❌ Error previsualización: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }

    # Abrir HTML
    try {
        Invoke-WebRequest -Uri "$BACKEND_URL/outputs/$($prev.html_filename)" -OutFile "./$($prev.html_filename)"
        Start-Process "./$($prev.html_filename)"
        Start-Sleep -Seconds 2
    } catch {
        Write-Host "⚠️  Abre manualmente: $BACKEND_URL/outputs/$($prev.html_filename)" -ForegroundColor Yellow
    }

    # Validación
    Write-Host ""
    Write-Host "  OK / MAL / SALTAR" -ForegroundColor Yellow
    $conf = Read-Host "¿Resultado?"

    if ($conf -eq "MAL") {
        Write-Host "Ingresa el dato expuesto:" -ForegroundColor Red
        $valor = Read-Host "  Dato"
        "$($Archivo -replace '\.pdf$',''),$tipo,$valor,NOMBRE,2_spacy,FN" |
            Out-File -FilePath $FN_CSV_PATH -Append -Encoding UTF8
        Write-Host "FN registrado. Documento NO enviado a Claude." -ForegroundColor Yellow
        return $false
    }
    if ($conf -ne "OK") {
        Write-Host "Saltado." -ForegroundColor Gray
        return $false
    }

    # Procesar
    Write-Host "`n🚀 Enviando a Claude API..." -ForegroundColor Yellow
    try {
        $res = Invoke-RestMethod -Uri "$BACKEND_URL/api/archivos/procesar" `
            -Method POST -ContentType "application/json" -TimeoutSec 180 `
            -Body (@{ archivos = @($Archivo); session_id = $prev.session_id; confirmado = $true } | ConvertTo-Json)

        $d = $res.detalles[0]
        if ($d.estado -eq "exitoso") {
            $v = if ($d.validacion.es_valido) { "✅ Válido" } else { "⚠️ Con inconsistencias" }
            Write-Host "✅ Exitoso — Caso: $($d.caso_id) | Doc: $($d.documento_id) | $v" -ForegroundColor Green
            Write-Host "   Costo: `$$($res.costo_total_usd) | Tokens: $($res.tokens_total)" -ForegroundColor White
            return $true
        } else {
            Write-Host "❌ Error: $($d.mensaje)" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "❌ Error HTTP: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
}

# ----------------------------------------------
Clear-Host
Write-Host "========================================================"  -ForegroundColor Cyan
Write-Host "  REPROCESAMIENTO FINAL — 2 documentos"                    -ForegroundColor Cyan
Write-Host "========================================================"  -ForegroundColor Cyan

# Verificar backend
try {
    Invoke-RestMethod -Uri "$BACKEND_URL/health" -TimeoutSec 5 | Out-Null
    Write-Host "✅ Backend UP`n" -ForegroundColor Green
} catch {
    Write-Host "❌ Backend no responde. Ejecuta: docker-compose up -d" -ForegroundColor Red
    Read-Host "ENTER para salir"; exit 1
}

# PASO 1: Informe (obligatorio antes de la petición)
$informe_ok = Procesar-Uno -Archivo "CTDG-2025-GE-0607.pdf" `
                           -TipoDoc "informe_tecnico" `
                           -Label "1/2 — INFORME TÉCNICO"

if (-not $informe_ok) {
    Write-Host "`n⚠️  El informe no se procesó. La petición no puede continuar." -ForegroundColor Red
    Read-Host "ENTER para salir"; exit 1
}

Write-Host "`n⏳ Preparando petición..." -ForegroundColor Gray
Start-Sleep -Seconds 1

# PASO 2: Petición
Procesar-Uno -Archivo "PR-CTDG-2025-GE-0607.pdf" `
             -TipoDoc "peticion_razonada" `
             -Label "2/2 — PETICIÓN RAZONADA"

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "  ✅ LISTO — Ejecuta calcular_metricas_pseudonimizacion.py" -ForegroundColor Cyan
Write-Host "========================================================`n"  -ForegroundColor Cyan
Read-Host "ENTER para finalizar"
