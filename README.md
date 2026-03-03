# 🏛️ Piloto Experimental — Automatización de Procedimientos Administrativos Sancionadores ARCOTEL

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.13.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Claude API](https://img.shields.io/badge/Claude-Sonnet_4-D97706?style=for-the-badge&logo=anthropic&logoColor=white)](https://www.anthropic.com/)
[![spaCy](https://img.shields.io/badge/spaCy-3.8.11-09A3D5?style=for-the-badge&logo=spacy&logoColor=white)](https://spacy.io/)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

**Sistema inteligente de extracción y validación automática de datos para Procedimientos Administrativos Sancionadores (PAS) en telecomunicaciones**

[Características](#-características-principales) •
[Inicio Rápido](#-inicio-rápido) •
[Arquitectura](#-arquitectura-del-sistema) •
[API](#-api-reference) •
[Métricas](#-métricas-de-rendimiento) •
[Documentación](#-documentación-adicional)

---

| 🎯 F1 Extracción | 🔐 F1 Pseudonimización | ⚡ Tiempo/doc | 💰 Costo/doc | 📄 Corpus evaluado |
|:---:|:---:|:---:|:---:|:---:|
| **97.4%** | **97.2%** | **~18 seg** | **$0.018 USD** | **70 documentos** |

</div>

---

## 📌 Descripción del Proyecto

**ARCOTEL PAS** automatiza la extracción, validación y pseudonimización de datos del **Procedimiento Administrativo Sancionador (PAS)** para infracciones del sector de telecomunicaciones en Ecuador, abordando un problema institucional crítico: casos simples que hoy demoran **34+ meses** en completarse.

> 💡 Este proyecto es el Trabajo Final de Estudios (TFE) de la **Universidad Internacional de La Rioja (UNIR)**, desarrollado en colaboración con **ARCOTEL Ecuador**.

### El Problema

ARCOTEL Ecuador detecta infracciones de prestadores de servicios de telecomunicaciones (e.g., renovación tardía de Garantía de Fiel Cumplimiento) y debe tramitar un PAS que involucra 8 documentos legales secuenciales, coordinación entre 4 áreas institucionales (CTDG, CCON, CZ2, DEDA), y generación **manual** de documentos altamente estandarizados.

### La Solución

Sistema híbrido que combina extracción LLM, validación determinística y pseudonimización LOPDP-conforme:

```
PDF IT/PR → [Pseudonimización 4 Capas] → Claude API → JSON estructurado → Validador → PostgreSQL
```

---

## ✨ Características Principales

- 🤖 **Extracción automática con LLM** — Claude API (`claude-sonnet-4-20250514`) con prompt engineering avanzado (few-shot, chain-of-thought, negative examples). F1 global = **97.4%** sobre 47 documentos gold standard.
- ⚖️ **Validación basada en reglas** — Motor determinístico ROTH Art. 204: calcula fechas tope, días de retraso, clasifica severidad. **100% detección, 0% falsos positivos.**
- 🔐 **Pseudonimización 4 capas** — Regex + Header parser + spaCy NER + Firmantes. F1 = **97.2%** sobre corpus de 70 documentos, **0 falsos positivos**, Precisión = 100%.
- 🛡️ **Cumplimiento LOPDP Ecuador** — Validación visual obligatoria antes de cualquier envío a Claude API. Claude API recibe exclusivamente pseudónimos (`NOMBRE_A3F7B2C1`).
- 🐳 **Docker-first** — Un solo `docker-compose up -d` levanta 7 servicios configurados y listos.
- 📊 **Gold standard validado** — Evaluación sobre 47 documentos (extracción) y 70 documentos (pseudonimización).
- 🔑 **Seguridad por diseño** — AES-256-GCM, HashiCorp Vault KMS, TTL automático 1h, red interna Docker aislada.

---

## 🚀 Inicio Rápido

### Prerrequisitos

- Docker Desktop 4.x+ con Docker Compose v2
- API Key de Anthropic (`sk-ant-...`)
- PowerShell 7+ *(opcional, para procesamiento batch)*

### Instalación en 4 pasos

```bash
# 1. Clonar repositorio
git clone https://github.com/<usuario>/arcotel-pas.git
cd arcotel-pas

# 2. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales (ver sección Configuración)

# 3. Crear directorios de datos
mkdir -p data/informes_tecnicos data/peticiones_razonadas

# 4. Levantar todos los servicios
docker-compose up -d
```

### Verificar instalación

```bash
curl http://localhost:8000/health
# → {"status": "ok", "database": "connected", "version": "4.0.0"}

curl http://localhost:8001/health
# → {"status": "healthy", "vault": "connected", "redis": "connected", "db": "connected"}
```

### Procesar tu primer documento

```bash
# Copiar PDF al directorio correspondiente
cp mi_informe.pdf data/informes_tecnicos/CTDG-GE-2025-0001.pdf

# 1. Previsualizar pseudonimización (OBLIGATORIO — LOPDP)
SESSION=$(curl -s -X POST http://localhost:8000/api/validacion/previsualizar \
  -H "Content-Type: application/json" \
  -d '{"archivo":"CTDG-GE-2025-0001.pdf","tipo_documento":"informes_tecnicos"}' \
  | jq -r '.session_id')

# 2. Revisar HTML generado en http://localhost:8000/outputs/
#    Verificar que todos los datos personales están reemplazados por pseudónimos

# 3. Confirmar y procesar
curl -X POST http://localhost:8000/api/archivos/procesar \
  -H "Content-Type: application/json" \
  -d "{\"archivos\":[\"CTDG-GE-2025-0001.pdf\"],\"session_id\":\"$SESSION\",\"confirmado\":true}"
```

### Procesamiento batch (PowerShell)

```powershell
# Procesar corpus completo con validación interactiva
.\procesar_masivo_v2.ps1
```

---

## 🏗️ Arquitectura del Sistema

El sistema implementa una **arquitectura de microservicios de dos capas** con aislamiento técnico de datos personales, cumpliendo LOPDP Ecuador Arts. 10.e, 33 y 37.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CAPA DE PROCESAMIENTO                           │
│                                                                         │
│  PDF IT/PR                                                              │
│     │                                                                   │
│     ▼                                                                   │
│  ┌─────────────────────────────────────────────────┐                   │
│  │        SERVICIO PSEUDONIMIZACIÓN (puerto 8001)  │                   │
│  │   Capa 1: Regex   → RUC, Cédula, Email, Tfno    │                   │
│  │   Capa 1.5: Header→ Nombre empresa, Dirección   │                   │
│  │   Capa 2: spaCy   → Nombres de personas (NER)   │                   │
│  │   Capa 3: Firmas  → Firmantes del documento     │                   │
│  │                                                  │                   │
│  │   postgres_pseudonym ← Vault AES-256-GCM        │                   │
│  │   Redis TTL 1h                                   │                   │
│  └─────────────────────────────────────────────────┘                   │
│     │ texto con PSEUDÓNIMOS (nunca datos reales)                       │
│     ▼                                                                   │
│  ┌──────────────────────────────────────────┐                         │
│  │     CLAUDE API (claude-sonnet-4-20250514)│                         │
│  │     Few-shot prompting, temperatura 0.0  │                         │
│  └──────────────────────────────────────────┘                         │
│     │ JSON estructurado                                                │
│     ▼                                                                   │
│  ┌──────────────────────────────────────────┐                         │
│  │  VALIDADOR ROTH Art. 204 (determinístico)│                         │
│  │  → Fechas tope, días retraso, severidad  │                         │
│  └──────────────────────────────────────────┘                         │
│     │                                                                   │
│     ▼                                                                   │
│  postgres_main (datos de negocio)                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Servicios Docker (7 contenedores)

| Servicio | Puerto | Descripción |
|---|---|---|
| `backend` | 8000 | FastAPI — API principal y lógica de negocio |
| `pseudonym-api` | 8001 | Servicio de pseudonimización (4 capas) |
| `postgres_main` | 5432 | Base de datos principal (casos PAS) |
| `postgres_pseudonym` | 5433 | Mapeos cifrados (exclusivo para pseudonimización) |
| `vault` | 8200 | HashiCorp Vault — KMS con AES-256-GCM |
| `redis` | 6379 | TTL de sesiones (expiración automática 1h) |
| `adminer` | 8080 | UI de administración de bases de datos |

---

## 🔐 Pseudonimización y Cumplimiento LOPDP

### El Problema Legal

El sistema procesa PDFs con **datos personales de ciudadanos ecuatorianos** que deben enviarse a **Claude API (Anthropic, EEUU)** — una transferencia internacional regulada por la LOPDP:

| Artículo LOPDP | Principio | Implementación |
|---|---|---|
| Art. 10.e | Minimización de datos | Solo pseudónimos llegan a Claude |
| Art. 33 | Transferencia con garantías | Datos reales nunca salen del sistema local |
| Art. 37 | Medidas de seguridad técnicas | AES-256-GCM + Vault KMS |
| Arts. 55-60 | Transferencia internacional | Arquitectura de separación técnica real |

### Arquitectura de 4 Capas

```
Texto original:
  "TELECOMUNICACIONES EJEMPLO S.A., RUC: 1792554136001
   Rep. Legal: JUAN PÉREZ GARCÍA, correo@empresa.com
   Dirección: AV. NAPO S/N Y BOMBEROS"

                    ↓ CAPA 1: Regex (datos estructurados)
  RUC: 1792554136001      →  RUC_A3F7B2C1
  correo@empresa.com      →  EMAIL_D4E8F2A1
  AV. NAPO S/N Y BOMBEROS →  DIRECCION_G7H1I4J2   ← Intersecciones
  1719710830              →  CEDULA_B9C3D7E5
  0999079807              →  TELEFONO_F2C9D6E3

                    ↓ CAPA 1.5: Header Parser (encabezado del documento)
  TELECOMUNICACIONES EJEMPLO S.A.  →  NOMBRE_K5L8M2N9
  AV. EJEMPLO S58F-93 CASA 12     →  DIRECCION_H4I7J1K3   ← Sin intersección

                    ↓ CAPA 2: spaCy NER (es_core_news_lg, re.IGNORECASE)
  JUAN PÉREZ GARCÍA       →  NOMBRE_P6Q9R3S7

                    ↓ CAPA 3: Firmantes (regex títulos académicos)
  Ing. DAVID CHÁVEZ       →  NOMBRE_T2U5V8W1
  (Elaborado/Revisado/Aprobado por)
```

> ⚠️ **Limitación metodológica**: La Capa 3 (Firmantes) detecta nombres en la sección de firmas del documento. En el corpus evaluado registró 0 VP y 0 FN porque los nombres de firmantes ya habían sido capturados previamente por la Capa 2 (spaCy NER).

### Métricas de Pseudonimización (corpus 70 documentos)

| Tipo | Total | VP | FN | Precision | Recall | F1 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| RUC | 23 | 23 | 0 | 100.0% | 100.0% | **100.0%** |
| CEDULA | 13 | 13 | 0 | 100.0% | 100.0% | **100.0%** |
| EMAIL | 45 | 45 | 0 | 100.0% | 100.0% | **100.0%** |
| TELEFONO | 2 | 2 | 0 | 100.0% | 100.0% | **100.0%** |
| DIRECCION | 35 | 32 | 3 | 100.0% | 91.4% | **95.5%** |
| NOMBRE | 397 | 372 | 25 | 100.0% | 93.7% | **96.7%** |
| **GLOBAL** | **515** | **487** | **28** | **100.0%** | **94.6%** | **97.2%** |

- **45/70 documentos (64.3%)** — Pseudonimización completa
- **25/70 documentos (35.7%)** — Pseudonimización parcial (≥1 FN, típicamente nombre fragmentado por OCR)
- **0 falsos positivos** — El sistema nunca pseudonimizó texto institucional por error

> Ver [`PSEUDONIMIZACION_ARQUITECTURA.md`](PSEUDONIMIZACION_ARQUITECTURA.md) para documentación técnica completa.

---

## 📊 Métricas de Rendimiento

### OE1 — Extracción de entidades (gold standard: 47 documentos)

| Campo | IT F1 | PR F1 | Notas |
|---|:---:|:---:|---|
| numero_documento | 100.0% | 100.0% | — |
| fecha | 100.0% | 100.0% | — |
| prestador_ruc | 100.0% | 100.0% | Campo crítico |
| tipo_infraccion | 100.0% | 100.0% | Campo crítico |
| fecha_real_entrega | 100.0% | 100.0% | Campo crítico |
| prestador_nombre | 96.4% | 100.0% | FN por truncamiento OCR |
| representante_legal | 92.9% | 100.0% | FN por formato atípico |
| fecha_maxima_entrega | 85.7% | 100.0% | FN en docs 2021 sin tabla de fechas |
| dias_retraso | 85.7% | 100.0% | Campo derivado — FN cascada |
| articulos_violados | — | 100.0% | ¹ |
| informe_base | — | 100.0% | Solo en PR |

> ¹ `articulos_violados` solo aplica a IT. FN por variación en numeración de sección entre formularios FO-DEAR-47 v2022 y v2025.

**Resumen por tipo de documento:**

| Grupo | Docs | Evaluaciones | FN | F1 global |
|---|:---:|:---:|:---:|:---:|
| Informes Técnicos (9 campos) | 28 | 252 | 10 | **96.0%** |
| Peticiones Razonadas (7 campos) | 19 | 133 | 0 | **100.0%** |
| **★ GLOBAL** | **47** | **385** | **10** | **97.4%** |

### OE2 — Pseudonimización LOPDP (corpus: 70 documentos)

| Métrica | Valor | Meta | ✓ |
|---|:---:|:---:|:---:|
| Precisión | 100.0% | = 100% | ✅ |
| Recall | 94.6% | ≥ 95% | ⚠️ |
| F1-Score global | **97.2%** | ≥ 95% | ✅ |
| Falsos positivos | 0 | 0 | ✅ |
| Cobertura completa | 45/70 (64.3%) | ≥ 90% | ⚠️ |

> **Nota**: El Recall de 94.6% y la cobertura de 64.3% reflejan la limitación de OCR fragmentado en el corpus de 70 documentos. Los 28 FN corresponden exclusivamente a texto fragmentado por pypdf (e.g., `CHAVE Z SALAS`, `OSTAIZA CEDEÑO LUISA ESPERANZA`), no a fallas del modelo NER en sí. El sistema mantiene Precisión = 100% (cero datos institucionales pseudonimizados por error).

### OE3 — Impacto operacional

| Métrica | Manual | Automático | Mejora |
|---|:---:|:---:|:---:|
| Tiempo por par IT+PR | 15 min | 3.5 min | **↓ 76.7%** |
| Costo por caso | — | $0.036 USD | ✅ vs límite $5.00 |
| Tokens input promedio | — | ~3,500 | — |
| Tokens output promedio | — | ~800 | — |
| Tiempo por documento | — | ~18 seg | — |

### Resultados vs. Criterios de Éxito

| OE | Métrica | Meta | Resultado | Estado | Diferencia |
|---|---|---|---|---|---|
| OE1 | F1-Score global | ≥ 85% | **97.4%** | ✅ | +12.4 pp |
| OE1 | F1 entidades críticas | ≥ 90% | **100.0%** | ✅ | +10.0 pp |
| OE1 | Detección inconsistencias | ≥ 80% | **100.0%** | ✅ | +20.0 pp |
| OE1 | FP validador | < 10% | **0.0%** | ✅ | −10.0 pp |
| OE2 | Precisión pseudonimización | = 100% | **100.0%** | ✅ | 0.0 pp |
| OE2 | F1 pseudonimización | ≥ 95% | **97.2%** | ✅ | +2.2 pp |
| OE3 | Reducción tiempo | ≥ 60% | **76.7%** | ✅ | +16.7 pp |
| OE3 | Costo por caso | < $5.00 | **$0.036** | ✅ | −99.3% |

---

## 🏗️ Estructura del Repositorio

```
arcotel-pas/
│
├── 🐍  backend/                             # Servicio principal FastAPI
│   ├── app/
│   │   ├── main.py                          # App FastAPI + routers
│   │   ├── config.py                        # Settings desde variables de entorno
│   │   ├── database.py                      # SQLAlchemy 2.0 + URL.create()
│   │   ├── models/                          # SQLAlchemy ORM models
│   │   │   ├── caso_pas.py
│   │   │   ├── documento_pas.py
│   │   │   └── prestador.py
│   │   ├── schemas/                         # Pydantic v2 schemas
│   │   │   ├── informe_tecnico.py
│   │   │   └── peticion_razonada.py
│   │   ├── extractors/                      # Claude API extractors (few-shot)
│   │   │   ├── informe_tecnico_extractor.py
│   │   │   └── peticion_razonada_extractor.py
│   │   ├── validators/                      # Validador ROTH Art. 204
│   │   │   └── validador_informe.py
│   │   ├── services/                        # Lógica de negocio
│   │   │   └── caso_service.py
│   │   └── api/                             # Endpoints REST
│   │       ├── archivos.py                  # /api/archivos/listar + /procesar
│   │       ├── procesador.py                # Lógica de procesamiento controlado
│   │       ├── validacion.py                # /api/validacion/previsualizar
│   │       └── casos.py                     # /api/casos/*
│   ├── init-db/                             # SQL auto-ejecución en docker-entrypoint
│   ├── Dockerfile                           # Multi-stage build Python 3.13.11
│   └── requirements.txt
│
├── 🔐  pseudonym-service/                   # Servicio de pseudonimización (LOPDP)
│   ├── app/
│   │   ├── main.py                          # FastAPI (solo red interna)
│   │   ├── api/
│   │   │   ├── internal.py                  # /internal/pseudonymize + /depseudonymize
│   │   │   └── health.py                    # /health, /ready, /live
│   │   └── services/
│   │       ├── pseudonymization.py          # Lógica 4 capas completa
│   │       └── spacy_detector.py            # NER + normalización MAYÚSCULAS
│   ├── init-db/
│   ├── Dockerfile
│   └── requirements.txt
│
├── 📂  data/                                # PDFs de entrada (bind mount Docker)
│   ├── informes_tecnicos/                   # CTDG-GE-YYYY-XXXX.pdf / CTDG-YYYY-GE-XXXX.pdf
│   └── peticiones_razonadas/                # CCDS-PR-YYYY-ZZZZ.pdf / PR-CTDG-YYYY-GE-XXXX.pdf
│
├── 📜  procesar_masivo_v2.ps1               # Batch processing con validación interactiva
├── 📜  procesar_corpus_completo.ps1         # Script para corpus completo de evaluación
├── 🐳  docker-compose.yml                   # Orquestación 7 servicios
├── 📋  .env.example                         # Plantilla de configuración
├── 🔐  PSEUDONIMIZACION_ARQUITECTURA.md     # Documentación técnica completa de seguridad
└── ⚖️   LICENSE                              # MIT
```

---

## ⚙️ Configuración

### Variables de Entorno (.env)

```bash
# ============================================
# ANTHROPIC — Requerido para extracción LLM
# ============================================
ANTHROPIC_API_KEY=sk-ant-...

# ============================================
# POSTGRESQL — Base de datos principal
# ============================================
POSTGRES_USER=arcotel_user
POSTGRES_PASSWORD=tu_password_seguro
POSTGRES_DB=arcotel_pas

# ============================================
# POSTGRESQL — Base de datos pseudonimización
# ============================================
POSTGRES_PSEUDONYM_PASSWORD=tu_password_pseudonim

# ============================================
# HASHICORP VAULT — KMS cifrado AES-256-GCM
# ============================================
VAULT_DEV_ROOT_TOKEN_ID=root-token-dev-only   # ⚠️ SOLO DESARROLLO
VAULT_TOKEN=root-token-dev-only

# ============================================
# REDIS — TTL de sesiones de pseudonimización
# ============================================
REDIS_PASSWORD=redis_password_123

# ============================================
# JWT — Autenticación interna entre servicios
# ============================================
JWT_SECRET=tu_jwt_secret_256_bits_minimo

# ============================================
# APLICACIÓN
# ============================================
ENV=development
DEBUG=false
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
TTL_HOURS=1
MAX_UPLOAD_SIZE=52428800
```

> ⚠️ El archivo `.env` está en `.gitignore`. Nunca comitear credenciales reales.

---

## 🗄️ Base de Datos

### Esquema (`postgres_main`)

```
prestadores ──< casos_pas ──< documentos_pas
                    └──< validaciones_informe
```

**Estados del flujo PAS:**
```
informe_tecnico → peticion_razonada → actuacion_previa →
acto_inicio → pruebas → dictamen → resolucion → cerrado
```

### Consultas útiles

```sql
-- Casos activos con días transcurridos
SELECT * FROM v_casos_activos;

-- Pipeline de documentos por caso
SELECT * FROM v_pipeline_documentos;

-- Resultados de validación ROTH Art. 204
SELECT numero_doc, es_valido, num_errors, num_warnings
FROM documentos ORDER BY fecha_doc DESC;

-- Estadísticas del corpus procesado
SELECT tipo_doc, COUNT(*) AS total, AVG(num_errors) AS avg_errores
FROM documentos GROUP BY tipo_doc;
```

---

## 🔒 Seguridad

### Principios de Diseño

| Principio | Implementación |
|---|---|
| **Defense in Depth** | 4 capas pseudonimización + red aislada + cifrado + TTL |
| **Zero Trust interno** | JWT obligatorio entre backend ↔ pseudonym-api |
| **Separación técnica** | `postgres_main` y `postgres_pseudonym` en contenedores aislados |
| **Least Privilege** | Usuarios no-root en Docker (`arcotel`, `pseudonym`) |
| **Secrets externalizados** | `.env` en `.gitignore`, sin valores en código fuente |
| **TTL automático** | Mapeos de pseudonimización expiran en 1 hora |
| **Logs sanitizados** | Errores no exponen detalles internos del cifrado |

### Matriz de Acceso por Red Docker

| Servicio | main_network | pseudonym_network | internal_api | Internet |
|---|:---:|:---:|:---:|:---:|
| backend | ✅ | ❌ | ✅ | ✅ (solo Anthropic API) |
| pseudonym-api | ❌ | ✅ | ✅ | ❌ |
| postgres_main | ✅ | ❌ | ❌ | ❌ |
| postgres_pseudonym | ❌ | ✅ | ❌ | ❌ |
| vault | ❌ | ✅ | ❌ | ❌ |
| redis | ❌ | ✅ | ✅ | ❌ |

---

## 🔌 API Reference

### Backend (puerto 8000)

| Endpoint | Método | Descripción |
|---|---|---|
| `GET /health` | GET | Estado del sistema y versión |
| `GET /api/archivos/listar` | GET | Lista PDFs disponibles con estado de procesamiento |
| `POST /api/validacion/previsualizar` | POST | Genera HTML con pseudonimización para validación visual |
| `POST /api/archivos/procesar` | POST | Procesa documentos (requiere session_id confirmado) |
| `GET /api/casos/` | GET | Lista todos los casos PAS |
| `GET /api/casos/{id}` | GET | Detalle de un caso específico |
| `GET /api/casos/{id}/documentos` | GET | Documentos de un caso |

### Pseudonym Service (puerto 8001 — solo red interna)

| Endpoint | Método | Auth | Descripción |
|---|---|---|---|
| `POST /internal/pseudonymize` | POST | JWT | Pseudonimiza texto (4 capas) |
| `POST /internal/depseudonymize` | POST | JWT | Recupera valores originales |
| `DELETE /session/{id}` | DELETE | JWT | Limpia mapeos de sesión |
| `GET /health` | GET | — | Estado del servicio |
| `GET /ready` | GET | — | Readiness (verifica Vault + Redis) |

### Ejemplo de flujo completo

```bash
# 1. Previsualizar (genera session_id)
curl -X POST http://localhost:8000/api/validacion/previsualizar \
  -H "Content-Type: application/json" \
  -d '{"archivo": "CTDG-GE-2025-0589.pdf", "tipo_documento": "informes_tecnicos"}'
# → {"session_id": "550e8400-e29b-41d4-a716-446655440000", "html_path": "..."}

# 2. Procesar (tras confirmar que pseudonimización es correcta)
curl -X POST http://localhost:8000/api/archivos/procesar \
  -H "Content-Type: application/json" \
  -d '{
    "archivos": ["CTDG-GE-2025-0589.pdf"],
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "confirmado": true
  }'
```

---

## ⚖️ Marco Legal

| Norma | Artículos | Cumplimiento |
|---|---|:---:|
| LOPDP Ecuador | Arts. 10.e, 33, 37, 55-60 | ✅ |
| LOT | Arts. 24.3, 117.b.16, 121-122, 130-131 | ✅ |
| COA | Arts. 186, 193, 202, 207 | ✅ |
| ROTH | Arts. 204 (GFC 15 días), 207 (renovación anual) | ✅ |

> ⚠️ **Aviso legal:** Este sistema acelera tareas repetitivas pero **no reemplaza el criterio legal humano**. Todas las salidas deben ser revisadas por personal jurídico antes de su uso oficial.

---

## 📚 Documentación Adicional

- [`PSEUDONIMIZACION_ARQUITECTURA.md`](PSEUDONIMIZACION_ARQUITECTURA.md) — Arquitectura técnica detallada del módulo de pseudonimización, flujo de datos, ciclo de vida, seguridad y métricas completas por capa y tipo de entidad.
- [`CLAUDE.md`](CLAUDE.md) — Reglas de desarrollo, patrones de código aprendidos y decisiones arquitectónicas del proyecto.

---

## 🗺️ Trabajo Futuro

El piloto cubre Módulos 1–3. El **Módulo 4 (Generación automática de documentos legales)** está fuera del alcance del presente TFE y constituye la principal línea de continuación:

- Generación automática de Acto de Inicio, Dictamen y Resolución mediante templates Jinja2 + LLM
- Integración con sistema de firma electrónica FirmaEC
- Pipeline PAS completo de 8 documentos

---

## 👤 Autor

**Iván Rodrigo Suárez Fabara**
TFE — Máster en Inteligencia Artificial
Universidad Internacional de La Rioja (UNIR)
Directora: Mariana Edith Miranda Varela
Período: Noviembre 2025 – Febrero 2026

---

*Generado con datos de: `gold_standard_validacion_v2.xlsx`, `metricas_pseudonimizacion.txt`, `vp_conteos.csv`, `fn_anotaciones.csv`*
*Última actualización: Marzo 2026*
