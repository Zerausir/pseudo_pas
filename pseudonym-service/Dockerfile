# =====================================================
# DOCKERFILE - SERVICIO DE PSEUDONIMIZACIÓN
# =====================================================

FROM python:3.13.11-bookworm

# Metadatos
LABEL maintainer="Ivan - ARCOTEL PAS"
LABEL description="Servicio de pseudonimización híbrida (Regex + spaCy) con Vault KMS"

# Variables de entorno para Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    curl \
    postgresql-client \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root (SEGURIDAD)
RUN groupadd -r pseudonym && useradd -r -g pseudonym pseudonym

# Directorio de trabajo
WORKDIR /app

# Copiar requirements y instalar dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ========== NUEVO: DESCARGAR MODELO SPACY ==========
# IMPORTANTE: Esto debe hacerse ANTES de cambiar a usuario no-root
RUN echo "Descargando modelo spaCy español (es_core_news_lg)..." && \
    python -m spacy download es_core_news_lg && \
    echo "✅ Modelo spaCy descargado correctamente"

# Verificar que el modelo se descargó correctamente
RUN python -c "import spacy; nlp = spacy.load('es_core_news_lg'); print('✅ Modelo spaCy verificado')"
# ===================================================

# Copiar código de la aplicación
COPY ./app /app/app

# Cambiar ownership a usuario no-root
RUN chown -R pseudonym:pseudonym /app

# Cambiar a usuario no-root
USER pseudonym

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Exponer puerto
EXPOSE 8001

# Comando de inicio
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]