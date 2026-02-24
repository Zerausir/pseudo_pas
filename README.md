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

| 🎯 F1 Extracción | 🔐 F1 Pseudonimización | ⚡ Tiempo/doc | 💰 Costo/doc | 📄 Docs procesados |
|:---:|:---:|:---:|:---:|:---:|
| **97.8%** | **99.3%** | **~18 seg** | **$0.018 USD** | **42 reales** |

</div>

---

## 📌 Descripción del Proyecto

**ARCOTEL PAS** automatiza la generación de documentación legal del **Procedimiento Administrativo Sancionador (PAS)** para infracciones del sector de telecomunicaciones en Ecuador, abordando un problema institucional crítico: casos simples que hoy demoran **34+ meses** en completarse.

> 💡 Este proyecto es el Trabajo Final de Estudios (TFE) de la **Universidad Internacional de La Rioja (UNIR)**, desarrollado en colaboración con **ARCOTEL Ecuador**.

### El Problema

ARCOTEL Ecuador detecta infracciones de prestadores de servicios de telecomunicaciones (e.g., renovación tardía de Garantía de Fiel Cumplimiento) y debe tramitar un PAS que involucra 8 documentos legales secuenciales, coordinación entre 4 áreas institucionales (CTDG, CCON, CZ2, DEDA), y generación **manual** de documentos altamente estandarizados.

### La Solución

Sistema híbrido que combina extracción LLM, validación determinística y pseudonimización LOPDP-compliant:

```
PDF Informe Técnico → Pseudonimización → Claude API → Datos Estructurados → Validación → PostgreSQL
```

---

## ✨ Características Principales

- 🤖 **Extracción automática con LLM** — Claude API (`claude-sonnet-4-20250514`) con prompt engineering avanzado (few-shot, chain-of-thought, negative examples)
- ⚖️ **Validación basada en reglas** — Motor determinístico ROTH Art. 204: calcula fechas tope, días de retraso, clasifica severidad
- 🔐 **Pseudonimización 4 capas** — Regex + Header parser + spaCy NER + Firmantes; F1 = 99.3%, 0 falsos positivos
- 🛡️ **Cumplimiento LOPDP Ecuador** — Validación visual obligatoria antes de cualquier envío a Claude API
- 🐳 **Docker-first** — Un solo `docker-compose up -d` levanta 7 servicios configurados y listos
- 📊 **Métricas automáticas** — Gold standard Excel con F1-score por campo, por documento y global
- 🔑 **Seguridad por diseño** — AES-256-GCM, HashiCorp Vault KMS, TTL automático 1h, red interna aislada

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
```

### Procesar tu primer documento

```bash
# Copiar PDF al directorio correspondiente
cp mi_informe.pdf data/informes_tecnicos/CTDG-GE-2024-0001.pdf

# Previsualizar pseudonimización (OBLIGATORIO - LOPDP)
SESSION=$(curl -s -X POST http://localhost:8000/api/validacion/previsualizar \
  -H "Content-Type: application/json" \
  -d '{"archivo":"CTDG-GE-2024-0001.pdf","tipo_documento":"informes_tecnicos"}' \
  | jq -r '.session_id')

# Revisar HTML generado → http://localhost:8000/outputs/

# Procesar (tras confirmar que pseudonimización es correcta)
curl -X POST http://localhost:8000/api/archivos/procesar \
  -H "Content-Type: application/json" \
  -d "{\"archivos\":[\"CTDG-GE-2024-0001.pdf\"],\"session_id\":\"$SESSION\",\"confirmado\":true}"
```

---

## 🏗️ Arquitectura del Sistema

El sistema implementa una **arquitectura de microservicios de dos capas** con aislamiento técnico de datos personales, cumpliendo LOPDP Ecuador Arts. 10.e, 33 y 37.

```
                ┌─────────────────────────────────────────────┐
                │           USUARIO / OPERADOR                │
                │   (Analista CTDG — curl / PowerShell)       │
                └──────────────────┬──────────────────────────┘
                                   │ HTTP :8000
                ┌──────────────────▼─────────────────────────┐
                │       SERVICIO 1: BACKEND PRINCIPAL         │
                │                                             │
                │  FastAPI · SQLAlchemy 2.0 · Python 3.13     │
                │                                             │
                │  • Extracción texto PDFs (PyPDF2/pdfplumber)│
                │  • Solicita pseudonimización (API interna)  │
                │  • Envía a Claude API (solo pseudónimos)    │
                │  • Validación ROTH Art.204 determinística   │
                │  • Almacena datos reales en BD principal    │
                └────────┬────────────────────────────────────┘
                         │ JWT / HTTP                │ HTTPS
                         │ :8001                     │ Claude API
                ┌────────▼──────────────┐   ┌────────▼──────────────┐
                │  SERVICIO 2:          │   │  Claude API           │
                │  PSEUDONIMIZACIÓN     │   │  (Anthropic, EEUU)    │
                │                      │   │                       │
                │  spaCy NER           │   │  Nunca recibe datos   │
                │  HashiCorp Vault KMS │   │  personales reales    │
                │  Redis (TTL 1h)      │   └───────────────────────┘
                │  AES-256-GCM         │
                │  Puerto 127.0.0.1    │
                └──────────────────────┘

  ┌─────────────────┐  ┌──────────────────────┐  ┌──────────┐  ┌────────────┐
  │  postgres_main  │  │  postgres_pseudonym   │  │  Redis   │  │   Vault    │
  │  :5432          │  │  :5433                │  │  :6379   │  │   :8200    │
  │  Datos negocio  │  │  Mapeos cifrados TTL  │  │  Cache   │  │  KMS keys  │
  └─────────────────┘  └──────────────────────┘  └──────────┘  └────────────┘
```

### Redes Docker y Aislamiento

| Red | Servicios | Internet |
|---|---|:---:|
| `main_network` | backend, postgres, adminer | ✅ |
| `pseudonym_network` | pseudonym-api, postgres_pseudonym, vault, redis | ❌ |
| `internal_api` | backend ↔ pseudonym-api | — |

> 🔒 El servicio de pseudonimización **no tiene acceso a internet**. Solo el backend puede llamarlo, y únicamente a través de `internal_api` con JWT.

---

## 🔄 Flujo de Procesamiento

```
┌─────────────────────────────────────────────────────────────────┐
│  FASE 1: VALIDACIÓN OBLIGATORIA (LOPDP)                        │
│                                                                 │
│  POST /api/validacion/previsualizar                             │
│    ├── Extrae texto PDF                                         │
│    ├── Pseudonimiza (4 capas: regex + header + spaCy + firmas) │
│    ├── Genera HTML con pseudónimos resaltados                   │
│    └── Retorna session_id                                       │
│                                                                 │
│  👁️  Operador descarga HTML → revisa manualmente → confirma    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  FASE 2: EXTRACCIÓN Y ALMACENAMIENTO                           │
│                                                                 │
│  POST /api/archivos/procesar {confirmado: true}                 │
│    ├── [HTTP 403] si confirmado=false → instrucciones LOPDP    │
│    ├── Detecta tipo doc (informes_tecnicos / peticiones)        │
│    ├── Pseudonimiza → envía a Claude API                        │
│    ├── Claude extrae JSON estructurado                          │
│    ├── Des-pseudonimiza → datos reales                          │
│    ├── Calcula campos derivados (dias_retraso, fecha_max_gfc)   │
│    ├── Valida reglas ROTH Art.204 (R1, R2, R3)                 │
│    └── Guarda en PostgreSQL (casos, documentos, validaciones)   │
└─────────────────────────────────────────────────────────────────┘
```

**Ordenamiento automático garantizado:** Informes Técnicos → Peticiones Razonadas → Otros (integridad referencial BD).

---

## 🛠️ Stack Tecnológico

<details>
<summary><b>Backend Principal</b></summary>

| Componente | Versión | Uso |
|---|---|---|
| Python | 3.13.11 | Lenguaje base |
| FastAPI | 0.128.0 | Framework API REST |
| SQLAlchemy | 2.0.46 | ORM estilo 2.0 |
| PostgreSQL | 18-alpine | Base de datos principal |
| Anthropic SDK | 0.76.0 | Cliente Claude API |
| PyPDF2 | 3.0.1 | Extracción texto PDFs |
| pdfplumber | 0.11.9 | PDFs con layout complejo |
| pytesseract | 0.3.13 | OCR PDFs escaneados |
| python-docx | 1.2.0 | Generación documentos Word |
| Pydantic v2 | 2.12.5 | Validación schemas |
| pandas | 3.0.0 | Análisis métricas |
| scikit-learn | 1.8.0 | Cálculo F1-score |
| structlog | 25.5.0 | Logging estructurado |

</details>

<details>
<summary><b>Servicio de Pseudonimización</b></summary>

| Componente | Versión | Uso |
|---|---|---|
| FastAPI | 0.128.0 | API interna (red privada) |
| spaCy + es_core_news_lg | 3.8.11 | NER detección personas (PER) |
| cryptography | 46.0.4 | AES-256-GCM cifrado local |
| hvac | 2.4.0 | Cliente HashiCorp Vault KMS |
| redis | 7.1.1 | Cache sesiones TTL |
| python-jose | 3.5.0 | JWT autenticación interna |
| HashiCorp Vault | latest | Gestión claves cifrado |
| Redis | 8.4.0-alpine | Cache (TTL 1h) |

</details>

<details>
<summary><b>Testing y Calidad de Código</b></summary>

| Herramienta | Versión | Uso |
|---|---|---|
| pytest | 9.0.2 | Testing unitario e integración |
| pytest-asyncio | 1.3.0 | Tests async |
| pytest-cov | 7.0.0 | Cobertura de código |
| black | 26.1.0 | Formateo código |
| isort | 7.0.0 | Orden imports |
| flake8 | 7.3.0 | Linting |
| mypy | 1.19.1 | Type checking estático |

</details>

---

## 📁 Estructura del Repositorio

```
arcotel-pas/
│
├── 🖥️  backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI v4.0 + StaticFiles
│   │   ├── database.py                      # SQLAlchemy engine + get_db()
│   │   ├── api/
│   │   │   ├── procesador.py                # POST /api/archivos/procesar
│   │   │   └── validacion.py                # POST /api/validacion/previsualizar
│   │   ├── extractors/
│   │   │   ├── informe_tecnico_extractor.py # Claude API + Pydantic + retry
│   │   │   └── peticion_razonada_extractor.py
│   │   ├── services/
│   │   │   ├── pseudonym_client.py          # Cliente HTTP inter-servicios
│   │   │   └── caso_service.py              # CRUD casos PAS
│   │   ├── validators/
│   │   │   └── validador_informe.py         # Motor reglas ROTH Art.204
│   │   └── models/                          # SQLAlchemy ORM models
│   ├── init-db/                             # Auto-init PostgreSQL en Docker
│   ├── Dockerfile
│   └── requirements.txt
│
├── 🔐  pseudonym-service/
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
│   ├── informes_tecnicos/                   # CTDG-GE-YYYY-XXXX.pdf
│   └── peticiones_razonadas/                # XXXX-PR-YYYY-ZZZZ.pdf
│
├── 📜  procesar_masivo_v2.ps1               # Batch processing con validación interactiva
├── 🐳  docker-compose.yml                   # Orquestación 7 servicios
├── 📋  .env.example                         # Plantilla de configuración
├── 🔐  PSEUDONIMIZACION_ARQUITECTURA.md     # Documentación seguridad completa
└── ⚖️   LICENSE                              # MIT
```

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
  "TELECOMUNICACIONES WRXXXXXX, RUC: 179XXXXXXXXXX
   Rep. Legal: MOXXX UNXXXXX KLXXXX AXXXX, correo@empresa.com"

                    ↓ CAPA 1: Regex (datos estructurados)
  RUC: 1792554136001      →  RUC_A3F7B2C1
  correo@empresa.com      →  EMAIL_D4E8F2A1

                    ↓ CAPA 1.5: Header Parser (encabezado del documento)
  TELECOMUNICACIONES WRX ...  →  NOMBRE_B9C3D7E5

                    ↓ CAPA 2: spaCy NER (es_core_news_lg)
  MOXXX UNXXXXX ...       →  NOMBRE_F2C9D6E3
  (normaliza MAYÚSCULAS → Title Case antes de NER; re.IGNORECASE para reemplazos)

                    ↓ CAPA 3: Firmantes (regex sección de firmas)
  Elaborado por: Ing. ...  →  NOMBRE_G7H1I4J2

Texto enviado a Claude API:
  "NOMBRE_B9C3D7E5, RUC: RUC_A3F7B2C1
   Rep. Legal: NOMBRE_F2C9D6E3, EMAIL_D4E8F2A1"
```

### Métricas de Pseudonimización (44 documentos reales)

| Tipo Entidad | Total Real | Detectados | Perdidos | Precision | Recall | F1 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| RUC | 12 | 12 | 0 | 100.0% | 100.0% | **100.0%** |
| CEDULA | 11 | 11 | 0 | 100.0% | 100.0% | **100.0%** |
| EMAIL | 30 | 30 | 0 | 100.0% | 100.0% | **100.0%** |
| TELEFONO | 1 | 1 | 0 | 100.0% | 100.0% | **100.0%** |
| DIRECCION | 21 | 20 | 1 | 100.0% | 95.2% | **97.6%** |
| NOMBRE | 232 | 229 | 3 | 100.0% | 98.7% | **99.3%** |
| **GLOBAL** | **307** | **303** | **4** | **100.0%** | **98.7%** | **99.3%** |

> ✅ **0 falsos positivos** — ningún dato no-personal fue pseudonimizado incorrectamente.

---

## 📡 API Reference

### Backend Principal (`:8000`)

<details>
<summary><b>GET /health</b> — Estado del sistema</summary>

```json
{
  "status": "ok",
  "database": "connected",
  "version": "4.0.0",
  "features": {
    "pseudonymization": true,
    "validation_required": true,
    "static_files": true
  }
}
```
</details>

<details>
<summary><b>POST /api/validacion/previsualizar</b> — Generar HTML de validación (paso obligatorio)</summary>

**Request:**
```json
{
  "archivo": "CTDG-GE-2022-0487.pdf",
  "tipo_documento": "informes_tecnicos"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "html_filename": "preview_CTDG-GE-2022-0487_20260224.html",
  "pseudonyms_count": 12,
  "pseudonyms_by_type": {
    "NOMBRE": 8,
    "RUC": 2,
    "EMAIL": 1,
    "DIRECCION": 1
  }
}
```

El HTML se sirve en `/outputs/{html_filename}`.
</details>

<details>
<summary><b>POST /api/archivos/procesar</b> — Extraer y guardar datos (requiere confirmación previa)</summary>

**Request:**
```json
{
  "archivos": ["CTDG-GE-2022-0487.pdf"],
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "confirmado": true,
  "forzar_reprocesar": false
}
```

> ⚠️ Si `confirmado: false` → **HTTP 403** con instrucciones de cumplimiento LOPDP.

**Response (éxito):**
```json
{
  "procesados": 1,
  "errores": 0,
  "resultados": [{
    "archivo": "CTDG-GE-2022-0487.pdf",
    "caso_id": 42,
    "numero_doc": "CTDG-GE-2022-0487",
    "prestador": "TELECOMUNICACIONES WRIVERA RED S.A.",
    "estado": "extraido",
    "validacion": { "es_valido": true, "num_errors": 0, "num_warnings": 1 }
  }]
}
```
</details>

<details>
<summary><b>GET /api/archivos/listar</b> — Listar PDFs disponibles</summary>

Retorna PDFs organizados por subdirectorio con estado de procesamiento (`ya_procesado`, `numero_documento`, `caso_id`).
</details>

### Servicio Pseudonimización (`:8001`, solo localhost)

| Endpoint | Método | Descripción |
|---|---|---|
| `/internal/pseudonymize` | POST | Pseudonimiza texto (JWT requerido) |
| `/internal/depseudonymize` | POST | Recupera valores originales |
| `/session/{session_id}` | DELETE | Limpia mapeos de sesión |
| `/health` · `/ready` · `/live` | GET | Health checks Docker/K8s |

---

## 📊 Métricas de Rendimiento

### Extracción de Datos (42 documentos reales ARCOTEL 2022–2025)

| Campo Extraído | F1-Score |
|---|:---:|
| numero_documento | 100.0% |
| fecha | 100.0% |
| prestador_ruc | 100.0% |
| tipo_infraccion | 100.0% |
| fecha_real_entrega | 100.0% |
| prestador_nombre | 97.6% |
| representante_legal | 95.2% |
| fecha_maxima_entrega | 97.1% |
| dias_retraso | 97.1% |
| articulos_violados | 85.7% ¹ |
| **F1 GLOBAL** | **97.8%** |

> ¹ Variación en numeración de secciones entre formularios FO-DEAR-47 (2022 vs 2025). El prompt busca por título de sección en lugar de número.

### Performance por Documento

| Métrica | Valor |
|---|---|
| Tokens input promedio | ~3,500 tokens |
| Tokens output promedio | ~800 tokens |
| Costo por documento | $0.018 USD |
| Tiempo de procesamiento | ~18 segundos |
| Modelo LLM | `claude-sonnet-4-20250514` |
| Temperatura | 0.0 (determinístico) |
| Reintentos ante error 529 | 3 (backoff 5s → 10s → 20s) |

---

## ⚙️ Configuración

### Variables de Entorno (`.env`)

```env
# ===== BASE DE DATOS PRINCIPAL =====
POSTGRES_DB=arcotel_pas
POSTGRES_USER=arcotel_user
POSTGRES_PASSWORD=<contraseña-segura>
POSTGRES_PORT=5432

# ===== BASE DE DATOS PSEUDONIMIZACIÓN =====
POSTGRES_PSEUDONYM_PASSWORD=<contraseña-segura-distinta>

# ===== HASHICORP VAULT =====
VAULT_DEV_ROOT_TOKEN_ID=<token-seguro>
VAULT_TOKEN=<mismo-token>

# ===== REDIS =====
REDIS_PASSWORD=<contraseña-redis>

# ===== AUTENTICACIÓN INTERNA =====
JWT_SECRET=<secreto-min-32-chars>

# ===== ANTHROPIC =====
ANTHROPIC_API_KEY=sk-ant-...

# ===== CONFIGURACIÓN =====
TTL_HOURS=1
ENV=development
DEBUG=false
BACKEND_PORT=8000
ADMINER_PORT=8080
```

> 🔒 **Nunca hagas commit** de tu `.env`. Está en `.gitignore` por defecto.

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

### Consultas Útiles

```sql
-- Casos activos con días transcurridos
SELECT * FROM v_casos_activos;

-- Pipeline de documentos por caso
SELECT * FROM v_pipeline_documentos;

-- Resultados de validación ROTH Art.204
SELECT numero_doc, es_valido, num_errors, num_warnings
FROM documentos ORDER BY fecha_doc DESC;
```

---

## 🔒 Seguridad

### Principios de Diseño

| Principio | Implementación |
|---|---|
| **Defense in Depth** | 4 capas pseudonimización + red aislada + cifrado + TTL |
| **Zero Trust interno** | JWT obligatorio entre backend ↔ pseudonym-service |
| **Separación técnica** | Datos personales y LLM en redes distintas sin intersección |
| **Least Privilege** | Usuarios no-root en Docker (`arcotel`, `pseudonym`) |
| **Secrets externalizados** | `.env` en `.gitignore`, sin valores en código fuente |
| **TTL automático** | Mapeos de pseudonimización expiran en 1 hora |
| **Logs sanitizados** | Errores no exponen detalles internos del cifrado |

### Matriz de Acceso por Red

| Servicio | main_network | pseudonym_network | internal_api | Internet |
|---|:---:|:---:|:---:|:---:|
| backend | ✅ | ❌ | ✅ | ✅ |
| pseudonym-api | ❌ | ✅ | ✅ | ❌ |
| postgres_main | ✅ | ❌ | ❌ | ❌ |
| postgres_pseudonym | ❌ | ✅ | ❌ | ❌ |
| vault | ❌ | ✅ | ❌ | ❌ |
| redis | ❌ | ✅ | ✅ | ❌ |

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

## 🧪 Desarrollo

```bash
# Ejecutar tests
pytest backend/tests/ -v --cov=backend/app

# Formatear código
black backend/app/ && isort backend/app/

# Linting y tipos
flake8 backend/app/ && mypy backend/app/

# Logs en tiempo real
docker-compose logs -f backend
docker-compose logs -f pseudonym-api | grep "ERROR\|WARNING"

# Acceder a BD
docker exec -it arcotel_main_db psql -U arcotel_user -d arcotel_pas

# Auditoría pseudonimización
docker exec -it arcotel_pseudonym_db psql -U pseudonym_user -d pseudonym_vault \
  -c "SELECT * FROM pseudonym_access_log ORDER BY timestamp DESC LIMIT 20;"
```

---

## 📖 Documentación Adicional

| Documento | Descripción |
|---|---|
| [PSEUDONIMIZACION_ARQUITECTURA.md](./PSEUDONIMIZACION_ARQUITECTURA.md) | Arquitectura completa de seguridad, justificación legal LOPDP, comandos de auditoría |
| `http://localhost:8000/docs` | Swagger UI — documentación interactiva de la API |
| `http://localhost:8080` | Adminer — gestión visual de bases de datos |

---

## 🤝 Contribuir

1. Fork el repositorio
2. Crea una rama: `git checkout -b feature/nueva-funcionalidad`
3. Ejecuta tests: `pytest backend/tests/ -v`
4. Abre un Pull Request

---

## 👨‍💻 Autor

**Iván Rodrigo Suárez Fabara**  
*TFE — Sistema Inteligente de Análisis y Priorización de Acciones de Control Técnico Regulatorio*  
Universidad Internacional de La Rioja (UNIR) · ARCOTEL Ecuador

---

<div align="center">

**MIT License** — Copyright (c) 2026 Iván Rodrigo Suárez Fabara

*Desarrollado para ARCOTEL Ecuador como Trabajo Final de Estudios (TFE)*

</div>
