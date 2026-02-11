#!/bin/bash
# =====================================================
# SCRIPT DE INICIALIZACIÓN AUTOMÁTICA DE POSTGRESQL
# =====================================================
# 
# Este script se ejecuta AUTOMÁTICAMENTE la primera vez
# que PostgreSQL inicia con un volumen vacío.
# 
# Ubicación: /docker-entrypoint-initdb.d/01-init.sh
# 
# IMPORTANTE: Solo se ejecuta UNA VEZ en la creación inicial
# Si el volumen ya tiene datos, NO se ejecuta
# 
# =====================================================

set -e

echo "================================================="
echo "ARCOTEL PAS - Inicialización de Base de Datos"
echo "================================================="
echo ""
echo "Usuario: $POSTGRES_USER"
echo "Base de datos: $POSTGRES_DB"
echo "Fecha: $(date)"
echo ""

# Verificar que la base de datos existe
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'Base de datos verificada: ' || current_database();
EOSQL

echo ""
echo "✅ Inicialización completada exitosamente"
echo "================================================="
echo ""
