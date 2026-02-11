# ============================================
# DOCKERFILE PROYECTO ARCOTEL PAS
# Base: Python 3.13.11 en Debian Bookworm
# ============================================

# ============================================
# STAGE 1: Builder (para dependencias pesadas)
# ============================================
FROM python:3.13.11-bookworm AS builder

# Metadatos
LABEL maintainer="Ivan Suarez <ivan@arcotel.gob.ec>"
LABEL description="Sistema Inteligente de Análisis PAS - ARCOTEL Ecuador"
LABEL version="1.3"

# Variables de entorno para build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema necesarias para compilar paquetes Python
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Para psycopg2 (PostgreSQL)
    libpq-dev \
    gcc \
    g++ \
    # Para Pillow (procesamiento imágenes)
    libjpeg-dev \
    zlib1g-dev \
    # Para pytesseract (OCR)
    tesseract-ocr \
    tesseract-ocr-spa \
    # Utilidades
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio virtual environment
RUN python -m venv /opt/venv

# Activar venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar requirements
COPY requirements.txt /tmp/requirements.txt

# Instalar dependencias Python en venv
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /tmp/requirements.txt

# ============================================
# STAGE 2: Runtime (imagen final ligera)
# ============================================
FROM python:3.13.11-slim-bookworm

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# Instalar solo dependencias runtime (sin compiladores)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # PostgreSQL client library
    libpq5 \
    # Tesseract OCR runtime
    tesseract-ocr \
    tesseract-ocr-spa \
    # Utilidades
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar virtual environment del builder
COPY --from=builder /opt/venv /opt/venv

# Crear usuario no-root para seguridad
RUN useradd -m -u 1000 -s /bin/bash arcotel && \
    mkdir -p /app /app/data /app/resultados && \
    chown -R arcotel:arcotel /app

# Cambiar a usuario no-root
USER arcotel

# Directorio de trabajo
WORKDIR /app

# Copiar código de la aplicación
COPY --chown=arcotel:arcotel . /app/backend/

# Exponer puerto FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando por defecto
# Nota: En desarrollo, docker-compose sobrescribirá esto con --reload
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
