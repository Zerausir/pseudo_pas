-- =====================================================
-- ARCOTEL PAS - AUTO-INICIALIZACIÓN DE SCHEMA
-- =====================================================
--
-- Este archivo se ejecuta AUTOMÁTICAMENTE por PostgreSQL
-- cuando el contenedor inicia con un volumen vacío.
--
-- Ubicación: /docker-entrypoint-initdb.d/02-schema.sql
--
-- CARACTERÍSTICAS:
-- - Sin DROP TABLE (no es necesario, BD está vacía)
-- - Idempotente (CREATE IF NOT EXISTS)
-- - Seguro para ejecución automática
--
-- =====================================================

\echo '=====================================================';
\echo 'ARCOTEL PAS - Creando Schema v1.6';
\echo '=====================================================';
\echo '';

-- =====================================================
-- EXTENSIONES (Comentadas - no se usan actualmente)
-- =====================================================
-- CREATE EXTENSION IF NOT EXISTS postgis;
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- TABLA: prestadores
-- =====================================================
CREATE TABLE IF NOT EXISTS prestadores (
    ruc VARCHAR(13) PRIMARY KEY
        CHECK (ruc ~ '^\d{10}$|^\d{13}$'),
    razon_social VARCHAR(255) NOT NULL,
    representante_legal VARCHAR(255),
    direccion TEXT,
    ciudad VARCHAR(100),
    provincia VARCHAR(100),
    emails TEXT[] CHECK (
        emails IS NULL OR
        array_length(emails, 1) IS NULL OR
        array_to_string(emails, ',') ~ '@'
    ),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prestadores_razon_social ON prestadores(razon_social);
CREATE INDEX IF NOT EXISTS idx_prestadores_provincia ON prestadores(provincia);
CREATE INDEX IF NOT EXISTS idx_prestadores_emails ON prestadores USING GIN (emails);

COMMENT ON TABLE prestadores IS 'Prestadores de servicios de telecomunicaciones';

-- =====================================================
-- TABLA: titulos_habilitantes
-- =====================================================
CREATE TABLE IF NOT EXISTS titulos_habilitantes (
    id SERIAL PRIMARY KEY,
    prestador_ruc VARCHAR(13) NOT NULL
        REFERENCES prestadores(ruc) ON DELETE CASCADE,
    tipo VARCHAR(100) NOT NULL,
    tomo_foja VARCHAR(50),
    resolucion VARCHAR(50),
    fecha_registro DATE,
    fecha_vigencia DATE,
    estado VARCHAR(20) DEFAULT 'vigente'
        CHECK (estado IN ('vigente', 'suspendido', 'revocado', 'cancelado')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_th_prestador ON titulos_habilitantes(prestador_ruc);
CREATE INDEX IF NOT EXISTS idx_th_estado ON titulos_habilitantes(estado);
CREATE INDEX IF NOT EXISTS idx_th_tipo ON titulos_habilitantes(tipo);

COMMENT ON TABLE titulos_habilitantes IS 'Títulos habilitantes otorgados por ARCOTEL';

-- =====================================================
-- TABLA: casos_pas
-- =====================================================
CREATE TABLE IF NOT EXISTS casos_pas (
    id SERIAL PRIMARY KEY,
    prestador_ruc VARCHAR(13) NOT NULL
        REFERENCES prestadores(ruc) ON DELETE RESTRICT,
    titulo_habilitante_id INTEGER
        REFERENCES titulos_habilitantes(id) ON DELETE SET NULL,
    infraccion_tipo VARCHAR(300) NOT NULL,
    fecha_infraccion DATE,
    estado VARCHAR(50) DEFAULT 'extraido'
        CHECK (estado IN (
            'extraido',
            'informe_tecnico',
            'peticion_razonada',
            'actuacion_previa',
            'acto_inicio',
            'pruebas',
            'dictamen',
            'resolucion',
            'cerrado',
            'validado',
            'procesado',
            'error'
        )),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_casos_prestador ON casos_pas(prestador_ruc);
CREATE INDEX IF NOT EXISTS idx_casos_estado ON casos_pas(estado);
CREATE INDEX IF NOT EXISTS idx_casos_fecha ON casos_pas(fecha_infraccion);
CREATE INDEX IF NOT EXISTS idx_casos_tipo ON casos_pas(infraccion_tipo);

COMMENT ON TABLE casos_pas IS 'Casos PAS detectados por el sistema';

-- =====================================================
-- TABLA: documentos_pas
-- =====================================================
CREATE TABLE IF NOT EXISTS documentos_pas (
    id SERIAL PRIMARY KEY,
    caso_id INTEGER NOT NULL
        REFERENCES casos_pas(id) ON DELETE CASCADE,
    tipo VARCHAR(50) NOT NULL
        CHECK (tipo IN ('informe_tecnico', 'peticion_razonada', 'acto_inicio',
                        'dictamen', 'resolucion', 'otro')),
    numero VARCHAR(50),
    fecha DATE NOT NULL,
    contenido_json JSONB NOT NULL,
    archivo_path TEXT,
    archivo_nombre VARCHAR(255),
    confianza_extraccion DECIMAL(3,2)
        CHECK (confianza_extraccion IS NULL OR
               (confianza_extraccion >= 0.00 AND confianza_extraccion <= 1.00)),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_docs_caso ON documentos_pas(caso_id);
CREATE INDEX IF NOT EXISTS idx_docs_tipo ON documentos_pas(tipo);
CREATE INDEX IF NOT EXISTS idx_docs_fecha ON documentos_pas(fecha);
CREATE INDEX IF NOT EXISTS idx_docs_archivo_nombre ON documentos_pas(archivo_nombre);
CREATE INDEX IF NOT EXISTS idx_docs_contenido_json ON documentos_pas USING GIN (contenido_json);

COMMENT ON TABLE documentos_pas IS 'Documentos del PAS procesados';

-- =====================================================
-- TABLA: validaciones_informe
-- =====================================================
CREATE TABLE IF NOT EXISTS validaciones_informe (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER NOT NULL
        REFERENCES documentos_pas(id) ON DELETE CASCADE,
    es_valido BOOLEAN NOT NULL DEFAULT FALSE,
    total_inconsistencias INTEGER DEFAULT 0 CHECK (total_inconsistencias >= 0),
    num_info INTEGER DEFAULT 0 CHECK (num_info >= 0),
    num_warnings INTEGER DEFAULT 0 CHECK (num_warnings >= 0),
    num_errors INTEGER DEFAULT 0 CHECK (num_errors >= 0),
    num_critical INTEGER DEFAULT 0 CHECK (num_critical >= 0),
    inconsistencias JSONB,
    validador_version VARCHAR(20) DEFAULT '1.0',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validaciones_documento ON validaciones_informe(documento_id);
CREATE INDEX IF NOT EXISTS idx_validaciones_valido ON validaciones_informe(es_valido);
CREATE INDEX IF NOT EXISTS idx_validaciones_errors ON validaciones_informe(num_errors);
CREATE INDEX IF NOT EXISTS idx_validaciones_critical ON validaciones_informe(num_critical);
CREATE INDEX IF NOT EXISTS idx_validaciones_inconsistencias ON validaciones_informe USING GIN (inconsistencias);

COMMENT ON TABLE validaciones_informe IS 'Validaciones automáticas de informes';

-- =====================================================
-- TABLA: validaciones_gold_standard
-- =====================================================
CREATE TABLE IF NOT EXISTS validaciones_gold_standard (
    id SERIAL PRIMARY KEY,
    documento_id INTEGER REFERENCES documentos_pas(id) ON DELETE CASCADE,
    validador VARCHAR(100) NOT NULL,
    fecha_validacion TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    datos_correctos JSONB NOT NULL,
    errores_encontrados TEXT[],
    notas TEXT,
    precision_ruc DECIMAL(3,2)
        CHECK (precision_ruc IS NULL OR (precision_ruc >= 0.00 AND precision_ruc <= 1.00)),
    precision_fechas DECIMAL(3,2)
        CHECK (precision_fechas IS NULL OR (precision_fechas >= 0.00 AND precision_fechas <= 1.00)),
    precision_articulos DECIMAL(3,2)
        CHECK (precision_articulos IS NULL OR (precision_articulos >= 0.00 AND precision_articulos <= 1.00)),
    f1_score_global DECIMAL(3,2)
        CHECK (f1_score_global IS NULL OR (f1_score_global >= 0.00 AND f1_score_global <= 1.00))
);

CREATE INDEX IF NOT EXISTS idx_validaciones_doc ON validaciones_gold_standard(documento_id);
CREATE INDEX IF NOT EXISTS idx_validaciones_validador ON validaciones_gold_standard(validador);
CREATE INDEX IF NOT EXISTS idx_validaciones_f1 ON validaciones_gold_standard(f1_score_global);

COMMENT ON TABLE validaciones_gold_standard IS 'Gold standard para evaluar precisión (P1)';

-- =====================================================
-- TABLA: experimento_impacto
-- =====================================================
CREATE TABLE IF NOT EXISTS experimento_impacto (
    id SERIAL PRIMARY KEY,
    analista VARCHAR(100) NOT NULL,
    documento_id INTEGER REFERENCES documentos_pas(id) ON DELETE SET NULL,
    metodo VARCHAR(20) NOT NULL CHECK (metodo IN ('manual', 'llm')),
    tiempo_segundos INTEGER NOT NULL CHECK (tiempo_segundos > 0),
    satisfaccion INTEGER
        CHECK (satisfaccion IS NULL OR (satisfaccion >= 1 AND satisfaccion <= 5)),
    observaciones TEXT,
    fecha_experimento TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experimento_analista ON experimento_impacto(analista);
CREATE INDEX IF NOT EXISTS idx_experimento_metodo ON experimento_impacto(metodo);
CREATE INDEX IF NOT EXISTS idx_experimento_fecha ON experimento_impacto(fecha_experimento);

COMMENT ON TABLE experimento_impacto IS 'Resultados experimento impacto (P2)';

-- =====================================================
-- VISTAS
-- =====================================================

CREATE OR REPLACE VIEW v_casos_resumen AS
SELECT
    c.id, p.razon_social AS prestador, p.ruc,
    c.infraccion_tipo, c.fecha_infraccion, c.estado,
    COUNT(d.id) AS num_documentos,
    MAX(d.fecha) AS ultimo_documento,
    MAX(d.created_at) AS ultima_actualizacion
FROM casos_pas c
JOIN prestadores p ON c.prestador_ruc = p.ruc
LEFT JOIN documentos_pas d ON c.id = d.caso_id
GROUP BY c.id, p.razon_social, p.ruc, c.infraccion_tipo, c.fecha_infraccion, c.estado
ORDER BY c.fecha_infraccion DESC;

CREATE OR REPLACE VIEW v_metricas_validacion AS
SELECT
    COUNT(*) AS total_validaciones,
    ROUND(AVG(precision_ruc), 4) AS precision_ruc_promedio,
    ROUND(AVG(precision_fechas), 4) AS precision_fechas_promedio,
    ROUND(AVG(precision_articulos), 4) AS precision_articulos_promedio,
    ROUND(AVG(f1_score_global), 4) AS f1_global_promedio,
    ROUND(STDDEV(f1_score_global), 4) AS f1_desviacion_std,
    MIN(f1_score_global) AS f1_minimo,
    MAX(f1_score_global) AS f1_maximo
FROM validaciones_gold_standard
WHERE f1_score_global IS NOT NULL;

CREATE OR REPLACE VIEW v_experimento_resultados AS
SELECT
    metodo, COUNT(*) AS num_experimentos,
    ROUND(AVG(tiempo_segundos), 2) AS tiempo_promedio_seg,
    ROUND(AVG(tiempo_segundos) / 60.0, 2) AS tiempo_promedio_min,
    ROUND(AVG(satisfaccion), 2) AS satisfaccion_promedio,
    ROUND(STDDEV(tiempo_segundos), 2) AS desviacion_std_tiempo,
    MIN(tiempo_segundos) AS tiempo_minimo,
    MAX(tiempo_segundos) AS tiempo_maximo
FROM experimento_impacto
WHERE satisfaccion IS NOT NULL
GROUP BY metodo;

CREATE OR REPLACE VIEW v_validaciones_estadisticas AS
SELECT
    COUNT(*) AS total_validaciones,
    COUNT(*) FILTER (WHERE es_valido = true) AS documentos_validos,
    COUNT(*) FILTER (WHERE es_valido = false) AS documentos_con_errores,
    ROUND(100.0 * COUNT(*) FILTER (WHERE es_valido = true) / NULLIF(COUNT(*), 0), 2)
        AS porcentaje_validos,
    ROUND(AVG(total_inconsistencias), 2) AS promedio_inconsistencias,
    ROUND(AVG(num_errors), 2) AS promedio_errores,
    SUM(num_info) AS total_info,
    SUM(num_warnings) AS total_warnings,
    SUM(num_errors) AS total_errors,
    SUM(num_critical) AS total_critical
FROM validaciones_informe;

-- =====================================================
-- FUNCIONES
-- =====================================================

CREATE OR REPLACE FUNCTION calcular_reduccion_tiempo()
RETURNS TABLE (
    tiempo_manual_promedio NUMERIC,
    tiempo_llm_promedio NUMERIC,
    reduccion_segundos NUMERIC,
    reduccion_porcentaje NUMERIC,
    es_significativo BOOLEAN
) AS $$
DECLARE
    t_manual NUMERIC;
    t_llm NUMERIC;
    reduccion_seg NUMERIC;
    reduccion_pct NUMERIC;
BEGIN
    SELECT AVG(tiempo_segundos) INTO t_manual FROM experimento_impacto WHERE metodo = 'manual';
    SELECT AVG(tiempo_segundos) INTO t_llm FROM experimento_impacto WHERE metodo = 'llm';

    reduccion_seg := COALESCE(t_manual, 0) - COALESCE(t_llm, 0);
    reduccion_pct := CASE
        WHEN t_manual > 0 THEN ((t_manual - t_llm) / t_manual) * 100
        ELSE 0
    END;

    RETURN QUERY SELECT
        ROUND(COALESCE(t_manual, 0), 2),
        ROUND(COALESCE(t_llm, 0), 2),
        ROUND(reduccion_seg, 2),
        ROUND(COALESCE(reduccion_pct, 0), 2),
        (COALESCE(reduccion_pct, 0) >= 50)::BOOLEAN;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VERIFICACIÓN
-- =====================================================

\echo '';
\echo 'Tablas creadas:';
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

\echo '';
\echo 'Vistas creadas:';
SELECT COUNT(*) FROM information_schema.views WHERE table_schema = 'public';

\echo '';
\echo 'Funciones creadas:';
SELECT COUNT(*) FROM information_schema.routines
WHERE routine_schema = 'public' AND routine_type = 'FUNCTION';

\echo '';
\echo '✅ Schema v1.6 creado exitosamente';
\echo '=====================================================';