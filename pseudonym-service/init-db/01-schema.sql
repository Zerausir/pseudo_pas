-- =====================================================
-- SCHEMA: BASE DE DATOS DE PSEUDONIMIZACIÓN
-- Propósito: Almacenar mapeos pseudónimo ↔ valor real (cifrados)
-- Autor: Ivan - ARCOTEL PAS
-- Fecha: 2026-02-09
-- =====================================================

-- ADVERTENCIA: Este schema se ejecuta AUTOMÁTICAMENTE la primera vez
-- que PostgreSQL inicia con volumen vacío.
-- NO incluye DROP CASCADE por seguridad.

-- =====================================================
-- EXTENSIONES
-- =====================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =====================================================
-- TABLA: pseudonym_sessions
-- Propósito: Agrupar pseudónimos por sesión de procesamiento
-- =====================================================

CREATE TABLE IF NOT EXISTS pseudonym_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    purpose VARCHAR(100) NOT NULL,  -- 'CLAUDE_API_EXTRACTION'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- Constraints
    CONSTRAINT chk_purpose CHECK (purpose IN ('CLAUDE_API_EXTRACTION', 'TESTING', 'AUDIT'))
);

CREATE INDEX idx_sessions_session_id ON pseudonym_sessions(session_id);
CREATE INDEX idx_sessions_expires_at ON pseudonym_sessions(expires_at);
CREATE INDEX idx_sessions_is_active ON pseudonym_sessions(is_active);

-- =====================================================
-- TABLA: pseudonym_mappings
-- Propósito: Mapeos pseudónimo ↔ valor real (CIFRADO con Vault)
-- =====================================================

CREATE TABLE IF NOT EXISTS pseudonym_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES pseudonym_sessions(id) ON DELETE CASCADE,
    pseudonym VARCHAR(255) UNIQUE NOT NULL,  -- 'PSN_001', 'PSN_002', etc.
    encrypted_value TEXT NOT NULL,  -- Cifrado con Vault Transit Engine
    value_type VARCHAR(50) NOT NULL,  -- 'RUC', 'NOMBRE', 'EMAIL', 'DIRECCION'
    vault_key_version INTEGER,  -- Versión de la clave en Vault
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    accessed_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP WITH TIME ZONE,
    
    -- Constraints
    CONSTRAINT chk_value_type CHECK (value_type IN ('RUC', 'NOMBRE', 'EMAIL', 'DIRECCION', 'TELEFONO', 'OTRO'))
);

CREATE INDEX idx_mappings_pseudonym ON pseudonym_mappings(pseudonym);
CREATE INDEX idx_mappings_session_id ON pseudonym_mappings(session_id);
CREATE INDEX idx_mappings_value_type ON pseudonym_mappings(value_type);

-- =====================================================
-- TABLA: pseudonym_access_log
-- Propósito: Auditoría completa de accesos (LOPDP Art. 68)
-- =====================================================

CREATE TABLE IF NOT EXISTS pseudonym_access_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES pseudonym_sessions(id) ON DELETE SET NULL,
    operation VARCHAR(50) NOT NULL,  -- 'PSEUDONYMIZE', 'DEPSEUDONYMIZE', 'CREATE_SESSION', 'DELETE_SESSION'
    user_id VARCHAR(100) NOT NULL,
    pseudonym VARCHAR(255),
    value_type VARCHAR(50),
    success BOOLEAN NOT NULL,
    error_message TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    request_metadata JSONB DEFAULT '{}'::jsonb,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT chk_operation CHECK (operation IN (
        'PSEUDONYMIZE', 
        'DEPSEUDONYMIZE', 
        'CREATE_SESSION', 
        'DELETE_SESSION',
        'CLEANUP_EXPIRED',
        'VAULT_ENCRYPT',
        'VAULT_DECRYPT'
    ))
);

CREATE INDEX idx_audit_timestamp ON pseudonym_access_log(timestamp DESC);
CREATE INDEX idx_audit_user_id ON pseudonym_access_log(user_id);
CREATE INDEX idx_audit_operation ON pseudonym_access_log(operation);
CREATE INDEX idx_audit_session_id ON pseudonym_access_log(session_id);

-- =====================================================
-- TABLA: pseudonym_stats
-- Propósito: Estadísticas agregadas para monitoreo
-- =====================================================

CREATE TABLE IF NOT EXISTS pseudonym_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL UNIQUE,
    total_sessions INTEGER DEFAULT 0,
    total_pseudonyms INTEGER DEFAULT 0,
    total_pseudonymize_ops INTEGER DEFAULT 0,
    total_depseudonymize_ops INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    avg_session_duration_seconds NUMERIC(10,2),
    metadata JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_stats_date ON pseudonym_stats(date DESC);

-- =====================================================
-- FUNCIONES DE UTILIDAD
-- =====================================================

-- Función: Auto-limpieza de sesiones expiradas
CREATE OR REPLACE FUNCTION delete_expired_mappings()
RETURNS TABLE(deleted_sessions INTEGER, deleted_mappings INTEGER) AS $$
DECLARE
    v_deleted_sessions INTEGER;
    v_deleted_mappings INTEGER;
BEGIN
    -- Registrar operación de limpieza
    INSERT INTO pseudonym_access_log (operation, user_id, success)
    VALUES ('CLEANUP_EXPIRED', 'SYSTEM', TRUE);
    
    -- Contar sesiones a eliminar
    SELECT COUNT(*) INTO v_deleted_sessions
    FROM pseudonym_sessions
    WHERE expires_at < NOW() AND is_active = TRUE;
    
    -- Contar mapeos a eliminar (vía CASCADE)
    SELECT COUNT(*) INTO v_deleted_mappings
    FROM pseudonym_mappings m
    INNER JOIN pseudonym_sessions s ON m.session_id = s.id
    WHERE s.expires_at < NOW();
    
    -- Marcar sesiones como inactivas
    UPDATE pseudonym_sessions
    SET is_active = FALSE
    WHERE expires_at < NOW() AND is_active = TRUE;
    
    -- Eliminar sesiones expiradas (CASCADE eliminará mapeos)
    DELETE FROM pseudonym_sessions
    WHERE expires_at < NOW();
    
    RETURN QUERY SELECT v_deleted_sessions, v_deleted_mappings;
END;
$$ LANGUAGE plpgsql;

-- Función: Actualizar estadísticas diarias
CREATE OR REPLACE FUNCTION update_daily_stats()
RETURNS VOID AS $$
DECLARE
    v_date DATE := CURRENT_DATE;
BEGIN
    INSERT INTO pseudonym_stats (
        date,
        total_sessions,
        total_pseudonyms,
        total_pseudonymize_ops,
        total_depseudonymize_ops,
        total_errors
    )
    SELECT
        v_date,
        COUNT(DISTINCT s.id),
        COUNT(DISTINCT m.id),
        COUNT(*) FILTER (WHERE l.operation = 'PSEUDONYMIZE'),
        COUNT(*) FILTER (WHERE l.operation = 'DEPSEUDONYMIZE'),
        COUNT(*) FILTER (WHERE l.success = FALSE)
    FROM pseudonym_sessions s
    LEFT JOIN pseudonym_mappings m ON s.id = m.session_id
    LEFT JOIN pseudonym_access_log l ON s.id = l.session_id
    WHERE DATE(s.created_at) = v_date
    ON CONFLICT (date) DO UPDATE SET
        total_sessions = EXCLUDED.total_sessions,
        total_pseudonyms = EXCLUDED.total_pseudonyms,
        total_pseudonymize_ops = EXCLUDED.total_pseudonymize_ops,
        total_depseudonymize_ops = EXCLUDED.total_depseudonymize_ops,
        total_errors = EXCLUDED.total_errors,
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VISTAS ÚTILES
-- =====================================================

-- Vista: Sesiones activas
CREATE OR REPLACE VIEW v_active_sessions AS
SELECT 
    s.session_id,
    s.user_id,
    s.purpose,
    s.created_at,
    s.expires_at,
    EXTRACT(EPOCH FROM (s.expires_at - NOW())) / 3600 AS hours_remaining,
    COUNT(m.id) AS total_pseudonyms
FROM pseudonym_sessions s
LEFT JOIN pseudonym_mappings m ON s.id = m.session_id
WHERE s.is_active = TRUE AND s.expires_at > NOW()
GROUP BY s.id;

-- Vista: Auditoría reciente
CREATE OR REPLACE VIEW v_recent_audit AS
SELECT 
    l.timestamp,
    l.operation,
    l.user_id,
    l.pseudonym,
    l.success,
    l.error_message,
    s.session_id
FROM pseudonym_access_log l
LEFT JOIN pseudonym_sessions s ON l.session_id = s.id
ORDER BY l.timestamp DESC
LIMIT 100;

-- Vista: Estadísticas de hoy
CREATE OR REPLACE VIEW v_today_stats AS
SELECT 
    COUNT(DISTINCT s.id) AS active_sessions,
    COUNT(DISTINCT m.id) AS total_pseudonyms,
    COUNT(*) FILTER (WHERE l.operation = 'PSEUDONYMIZE' AND l.timestamp::date = CURRENT_DATE) AS pseudonymize_today,
    COUNT(*) FILTER (WHERE l.operation = 'DEPSEUDONYMIZE' AND l.timestamp::date = CURRENT_DATE) AS depseudonymize_today,
    COUNT(*) FILTER (WHERE l.success = FALSE AND l.timestamp::date = CURRENT_DATE) AS errors_today
FROM pseudonym_sessions s
LEFT JOIN pseudonym_mappings m ON s.id = m.session_id AND m.created_at::date = CURRENT_DATE
LEFT JOIN pseudonym_access_log l ON s.id = l.session_id;

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Trigger: Incrementar accessed_count en pseudonym_mappings
CREATE OR REPLACE FUNCTION increment_access_count()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.operation = 'DEPSEUDONYMIZE' AND NEW.pseudonym IS NOT NULL THEN
        UPDATE pseudonym_mappings
        SET accessed_count = accessed_count + 1,
            last_accessed_at = NOW()
        WHERE pseudonym = NEW.pseudonym;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_increment_access_count
AFTER INSERT ON pseudonym_access_log
FOR EACH ROW
EXECUTE FUNCTION increment_access_count();

-- =====================================================
-- PERMISOS (si usas roles específicos)
-- =====================================================

-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pseudonym_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO pseudonym_user;

-- =====================================================
-- COMENTARIOS EN TABLAS
-- =====================================================

COMMENT ON TABLE pseudonym_sessions IS 'Sesiones de pseudonimización con TTL';
COMMENT ON TABLE pseudonym_mappings IS 'Mapeos cifrados: pseudónimo ↔ valor real';
COMMENT ON TABLE pseudonym_access_log IS 'Auditoría completa de accesos (LOPDP Art. 68)';
COMMENT ON TABLE pseudonym_stats IS 'Estadísticas agregadas diarias';

COMMENT ON COLUMN pseudonym_mappings.encrypted_value IS 'Valor cifrado con Vault Transit Engine';
COMMENT ON COLUMN pseudonym_mappings.vault_key_version IS 'Versión de clave para rotación';

-- =====================================================
-- DATOS INICIALES (OPCIONAL)
-- =====================================================

-- Insertar estadística inicial para hoy
INSERT INTO pseudonym_stats (date)
VALUES (CURRENT_DATE)
ON CONFLICT (date) DO NOTHING;

-- =====================================================
-- FIN DEL SCHEMA
-- =====================================================

-- Mensaje de confirmación
DO $$
BEGIN
    RAISE NOTICE '✅ Schema de pseudonimización creado exitosamente';
    RAISE NOTICE '📊 Tablas: pseudonym_sessions, pseudonym_mappings, pseudonym_access_log, pseudonym_stats';
    RAISE NOTICE '🔧 Funciones: delete_expired_mappings(), update_daily_stats()';
    RAISE NOTICE '👁️ Vistas: v_active_sessions, v_recent_audit, v_today_stats';
END $$;
